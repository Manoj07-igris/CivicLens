"""Image processing and validation service for Civic Grievance Assistant.

Enforces:
1. Strict magic byte validation (JPEG, PNG, WebP only; rejects GIF, SVG, HEIC).
2. Streaming size enforcement (never buffers beyond GRIEVANCE_MAX_IMAGE_MB).
3. Pillow decompression-bomb defense (Image.MAX_IMAGE_PIXELS limit).
4. EXIF/GPS/XMP metadata stripping via orientation transpose + RGB re-encoding to JPEG.
5. Max dimension downscaling (longest side <= GRIEVANCE_IMAGE_MAX_DIMENSION).
6. Secure storage under backend/data/grievances/<id>/image.jpg.
"""

import io
import logging
import re
from pathlib import Path
from typing import Optional, Tuple
from fastapi import UploadFile
from PIL import Image, ImageOps

from app.core.config import Settings, get_settings
from app.core.errors import DocumentProcessingError

logger = logging.getLogger("civiclens.grievance.images")


class GrievanceImageError(DocumentProcessingError):
  """Domain error for image validation or processing failures."""
  pass


def detect_image_format(header_bytes: bytes) -> str:
  """Inspect header magic bytes to detect image format.

  Returns 'jpeg', 'png', or 'webp' if valid.
  Raises GrievanceImageError for unsupported or rejected formats.
  """
  if len(header_bytes) < 12:
    raise GrievanceImageError("Uploaded file is too small to be a valid image.")

  # JPEG: FF D8 FF
  if header_bytes[:3] == b"\xff\xd8\xff":
    return "jpeg"

  # PNG: 89 50 4E 47 0D 0A 1A 0A
  if header_bytes[:8] == b"\x89PNG\r\n\x1a\n":
    return "png"

  # WebP: RIFF ... WEBP
  if header_bytes[:4] == b"RIFF" and header_bytes[8:12] == b"WEBP":
    return "webp"

  # GIF detection
  if header_bytes[:6] in (b"GIF87a", b"GIF89a"):
    raise GrievanceImageError(
        "GIF images are not supported. Please upload a standard photograph in JPEG, PNG, or WebP format."
    )

  # SVG detection
  trimmed = header_bytes[:64].lstrip().lower()
  if trimmed.startswith(b"<svg") or trimmed.startswith(b"<?xml"):
    raise GrievanceImageError(
        "SVG vector graphics are not supported. Please upload a standard photograph in JPEG, PNG, or WebP format."
    )

  # HEIC/HEIF detection
  if len(header_bytes) >= 12 and header_bytes[4:8] == b"ftyp":
    brand = header_bytes[8:12].lower()
    if brand in (b"heic", b"heix", b"hevc", b"mif1", b"msf1"):
      raise GrievanceImageError(
          "HEIC/HEIF images from iOS devices cannot be processed directly. "
          "Please convert your photo to JPEG or PNG before uploading."
      )

  raise GrievanceImageError(
      "Unsupported image format. Please upload a valid JPEG, PNG, or WebP photo."
  )


async def read_and_validate_upload_stream(
    upload_file: UploadFile,
    max_mb: int = 5,
) -> Tuple[bytes, str]:
  """Stream and read uploaded file with strict size enforcement.

  Stops streaming and discards bytes immediately if size exceeds limit.
  Returns (raw_bytes, detected_format).
  """
  max_bytes = max_mb * 1024 * 1024
  chunk_size = 64 * 1024  # 64 KB
  buffer = bytearray()
  detected_format: Optional[str] = None

  while True:
    chunk = await upload_file.read(chunk_size)
    if not chunk:
      break
    buffer.extend(chunk)

    if len(buffer) > max_bytes:
      buffer.clear()
      raise GrievanceImageError(
          f"Image file exceeds maximum allowed size of {max_mb} MB. Please upload a smaller photo."
      )

    # Check magic bytes on first chunk
    if detected_format is None and len(buffer) >= 12:
      detected_format = detect_image_format(bytes(buffer[:16]))

  if not buffer:
    raise GrievanceImageError("Uploaded file is empty.")

  if detected_format is None:
    detected_format = detect_image_format(bytes(buffer[:16]))

  return bytes(buffer), detected_format


def process_and_sanitize_image(
    raw_bytes: bytes,
    settings: Optional[Settings] = None,
) -> Tuple[bytes, int, int]:
  """Process image using Pillow with strict privacy and security guarantees.

  Guarantees:
  1. Image.MAX_IMAGE_PIXELS prevents decompression bombs.
  2. ImageOps.exif_transpose fixes camera rotation before metadata strip.
  3. All EXIF, GPS coordinates, camera specs, and XMP metadata are completely stripped.
  4. Animated images rejected.
  5. Converted to clean RGB JPEG.
  6. Longest dimension scaled down to GRIEVANCE_IMAGE_MAX_DIMENSION.

  Returns (sanitized_jpeg_bytes, width, height).
  """
  conf = settings or get_settings()
  max_pixels = conf.GRIEVANCE_MAX_PIXELS
  max_dim = conf.GRIEVANCE_IMAGE_MAX_DIMENSION

  # Set decompression-bomb defense
  Image.MAX_IMAGE_PIXELS = max_pixels

  try:
    with Image.open(io.BytesIO(raw_bytes)) as img:
      # Guard against animated images
      if getattr(img, "is_animated", False):
        raise GrievanceImageError(
            "Animated images are not supported. Please upload a single still photograph."
        )

      # 1. Fix orientation according to EXIF before stripping metadata
      transposed = ImageOps.exif_transpose(img)
      if transposed is None:
        transposed = img

      # 2. Convert to clean RGB mode (strips transparency, alpha channels, palettes)
      rgb_img = transposed.convert("RGB")

      # 3. Downscale if dimensions exceed max_dimension
      orig_w, orig_h = rgb_img.size
      longest_side = max(orig_w, orig_h)
      if longest_side > max_dim:
        scale = max_dim / float(longest_side)
        new_w = max(1, int(round(orig_w * scale)))
        new_h = max(1, int(round(orig_h * scale)))
        rgb_img = rgb_img.resize((new_w, new_h), Image.Resampling.LANCZOS)
        logger.info("Downscaled image from %dx%d to %dx%d", orig_w, orig_h, new_w, new_h)

      final_w, final_h = rgb_img.size

      # 4. Re-encode as clean JPEG without any metadata (exif=None, icc_profile=None)
      out_buffer = io.BytesIO()
      rgb_img.save(
          out_buffer,
          format="JPEG",
          quality=85,
          optimize=True,
      )
      sanitized_bytes = out_buffer.getvalue()

      return sanitized_bytes, final_w, final_h

  except Image.DecompressionBombError as bomb_err:
    logger.warning("Rejected decompression bomb image: %s", bomb_err)
    raise GrievanceImageError(
        "Image exceeds safe pixel density limits. Please upload a standard photograph."
    ) from bomb_err
  except GrievanceImageError:
    raise
  except Exception as exc:
    logger.error("Failed to process image with Pillow: %s", exc)
    raise GrievanceImageError("Invalid or corrupted image data. Could not process photo.") from exc


def save_grievance_image(
    grievance_id: str,
    jpeg_bytes: bytes,
    settings: Optional[Settings] = None,
) -> Path:
  """Store sanitized JPEG under backend/data/grievances/<grievance_id>/image.jpg."""
  clean_id = str(grievance_id).strip()
  if not clean_id or not re.match(r"^[a-zA-Z0-9_\-]+$", clean_id):
    raise ValueError(f"Invalid grievance ID format: '{grievance_id}'")

  conf = settings or get_settings()
  target_dir = (conf.grievances_dir / clean_id).resolve()
  try:
    if not target_dir.is_relative_to(conf.grievances_dir.resolve()):
      raise ValueError("Path traversal attempt detected")
  except ValueError as exc:
    raise ValueError("Path traversal attempt detected") from exc

  target_dir.mkdir(parents=True, exist_ok=True)
  image_path = target_dir / "image.jpg"
  image_path.write_bytes(jpeg_bytes)
  logger.info("Saved sanitized image for grievance %s (%d bytes)", clean_id, len(jpeg_bytes))
  return image_path


def get_grievance_image_path(
    grievance_id: str,
    settings: Optional[Settings] = None,
) -> Optional[Path]:
  """Return path to stored image if exists, else None."""
  clean_id = str(grievance_id).strip()
  if not clean_id or not re.match(r"^[a-zA-Z0-9_\-]+$", clean_id):
    return None

  conf = settings or get_settings()
  target_dir = (conf.grievances_dir / clean_id).resolve()
  try:
    if not target_dir.is_relative_to(conf.grievances_dir.resolve()):
      return None
  except ValueError:
    return None

  image_path = target_dir / "image.jpg"
  if image_path.is_file() and image_path.stat().st_size > 0:
    return image_path
  return None


def delete_grievance_image(
    grievance_id: str,
    settings: Optional[Settings] = None,
) -> bool:
  """Delete stored image if present."""
  path = get_grievance_image_path(grievance_id, settings)
  if path and path.exists():
    try:
      path.unlink()
      logger.info("Deleted image for grievance %s", grievance_id)
      return True
    except Exception as exc:
      logger.warning("Could not delete image %s: %s", path, exc)
  return False
