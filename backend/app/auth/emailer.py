"""Email delivery service using standard library smtplib with dev-mode console fallback."""

from email.mime.text import MIMEText
import logging
import smtplib
import threading

from app.core.config import get_settings

logger = logging.getLogger("civiclens.auth.emailer")


def _send_smtp(to_email: str, subject: str, body_text: str) -> None:
  settings = get_settings()
  msg = MIMEText(body_text, "plain", "utf-8")
  msg["Subject"] = subject
  msg["From"] = settings.SMTP_FROM_EMAIL
  msg["To"] = to_email

  try:
    if settings.SMTP_PORT == 465:
      server = smtplib.SMTP_SSL(settings.SMTP_HOST, settings.SMTP_PORT, timeout=10)
    else:
      server = smtplib.SMTP(settings.SMTP_HOST, settings.SMTP_PORT, timeout=10)
      if settings.SMTP_USE_TLS:
        server.starttls()

    if settings.SMTP_USER and settings.SMTP_PASSWORD:
      server.login(settings.SMTP_USER, settings.SMTP_PASSWORD)

    server.sendmail(settings.SMTP_FROM_EMAIL, [to_email], msg.as_string())
    server.quit()
    logger.info("Sent password reset email to %s", to_email)
  except Exception as exc:
    logger.error("Failed to send password reset email via SMTP: %s", exc)


def send_password_reset_email(to_email: str, raw_token: str, lang: str = "en") -> None:
  """Dispatch password reset instructions via configured SMTP or print to dev console.

  The reset link contains the token in the URL fragment (#token=) so that the token
  is not leaked in HTTP Referer headers to external links.
  """
  settings = get_settings()
  reset_url = f"{settings.FRONTEND_BASE_URL.rstrip('/')}/reset-password#token={raw_token}"

  if lang == "ta":
    subject = "CivicLens - கடவுச்சொல் மீட்டமைப்பு"
    body = (
        f"வணக்கம்,\n\n"
        f"உங்கள் CivicLens கணக்கிற்கான கடவுச்சொல் மீட்டமைப்பு கோரிக்கை பெறப்பட்டது.\n"
        f"கடவுச்சொல்லை மீட்டமைக்க கீழேயுள்ள இணைப்பைக் கிளிக் செய்யவும்:\n\n"
        f"{reset_url}\n\n"
        f"இந்த இணைப்பு 1 மணிநேரம் மட்டுமே செல்லுபடியாகும். இந்தக் கோரிக்கையை நீங்கள் செய்யவில்லை எனில், "
        f"இதை புறக்கணிக்கலாம்.\n\n"
        f"நன்றி,\nCivicLens குழு"
    )
  else:
    subject = "CivicLens - Password Reset Request"
    body = (
        f"Hello,\n\n"
        f"A password reset request was received for your CivicLens account.\n"
        f"Click the link below to set a new password:\n\n"
        f"{reset_url}\n\n"
        f"This link is valid for 1 hour. If you did not make this request, you can safely ignore this email.\n\n"
        f"Regards,\nCivicLens Team"
    )

  if settings.is_email_delivery_configured:
    # Send in a background thread to prevent blocking request loop
    thread = threading.Thread(
        target=_send_smtp,
        args=(to_email, subject, body),
        daemon=True,
    )
    thread.start()
  else:
    # Development mode: print clearly to console and logs
    if settings.AUTH_DEV_PRINT_RESET_LINKS or settings.APP_ENV == "development":
      print("\n" + "=" * 70)
      print(f"[AUTH DEV] Password Reset Link for {to_email}:")
      print(f"URL: {reset_url}")
      print("=" * 70 + "\n")
    logger.info("[AUTH DEV] Password reset link for %s: %s", to_email, reset_url)
