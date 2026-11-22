import React, { useState, useRef } from "react";
import { UploadCloud, FileText, X } from "lucide-react";
import { useLanguage } from "../../hooks/useLanguage";

export function FileDropzone({
  onFileSelect,
  acceptedFormat = ".pdf",
  maxSizeMB = 25,
  className = "",
}) {
  const { t } = useLanguage();
  const [isDragging, setIsDragging] = useState(false);
  const [selectedFile, setSelectedFile] = useState(null);
  const fileInputRef = useRef(null);

  const formatFileSize = (bytes) => {
    if (!bytes || bytes === 0) return "0 Bytes";
    const k = 1024;
    const sizes = ["Bytes", "KB", "MB", "GB"];
    const i = Math.floor(Math.log(bytes) / Math.log(k));
    return parseFloat((bytes / Math.pow(k, i)).toFixed(2)) + " " + sizes[i];
  };

  const handleDragOver = (e) => {
    e.preventDefault();
    e.stopPropagation();
    setIsDragging(true);
  };

  const handleDragLeave = (e) => {
    e.preventDefault();
    e.stopPropagation();
    setIsDragging(false);
  };

  const handleDrop = (e) => {
    e.preventDefault();
    e.stopPropagation();
    setIsDragging(false);

    if (e.dataTransfer.files && e.dataTransfer.files.length > 0) {
      const file = e.dataTransfer.files[0];
      processFile(file);
    }
  };

  const handleFileInputChange = (e) => {
    if (e.target.files && e.target.files.length > 0) {
      const file = e.target.files[0];
      processFile(file);
    }
  };

  const processFile = (file) => {
    if (!file.name.toLowerCase().endsWith(".pdf")) {
      alert("Please select a PDF document.");
      return;
    }
    if (file.size > maxSizeMB * 1024 * 1024) {
      alert(`File size exceeds maximum allowed size of ${maxSizeMB} MB.`);
      return;
    }
    setSelectedFile(file);
    if (onFileSelect) {
      onFileSelect(file);
    }
  };

  const handleRemoveFile = (e) => {
    e.stopPropagation();
    setSelectedFile(null);
    if (fileInputRef.current) {
      fileInputRef.current.value = "";
    }
    if (onFileSelect) {
      onFileSelect(null);
    }
  };

  return (
    <div className={`w-full ${className}`}>
      <input
        ref={fileInputRef}
        type="file"
        accept={acceptedFormat}
        onChange={handleFileInputChange}
        className="hidden"
        id="civiclens-dropzone-input"
      />

      {!selectedFile ? (
        <div
          role="button"
          tabIndex={0}
          onClick={() => fileInputRef.current?.click()}
          onKeyDown={(e) => {
            if (e.key === "Enter" || e.key === " ") {
              e.preventDefault();
              fileInputRef.current?.click();
            }
          }}
          onDragOver={handleDragOver}
          onDragLeave={handleDragLeave}
          onDrop={handleDrop}
          className={`flex flex-col items-center justify-center p-8 rounded-2xl border-2 border-dashed transition-all cursor-pointer text-center 
            ${
              isDragging
                ? "border-blue-600 bg-blue-50/70"
                : "border-slate-300 bg-white hover:border-blue-400 hover:bg-slate-50/50"
            } 
            focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-blue-600 focus-visible:ring-offset-2`}
        >
          <div className="w-12 h-12 rounded-xl bg-blue-50 text-blue-700 flex items-center justify-center mb-3">
            <UploadCloud className="w-6 h-6" />
          </div>
          <p className="text-sm font-semibold text-slate-800 mb-1">
            {isDragging ? t("dropzone.dragActive") : t("dropzone.title")}
          </p>
          <p className="text-xs text-slate-500 mb-2">{t("dropzone.subtitle")}</p>
          <span className="text-[11px] text-slate-400 font-medium">
            {t("dropzone.supportedFormats")}
          </span>
        </div>
      ) : (
        <div className="flex items-center justify-between p-4 bg-blue-50/60 rounded-xl border border-blue-200">
          <div className="flex items-center gap-3 min-w-0">
            <div className="w-10 h-10 rounded-lg bg-blue-600 text-white flex items-center justify-center flex-shrink-0">
              <FileText className="w-5 h-5" />
            </div>
            <div className="min-w-0">
              <p className="text-xs font-medium text-blue-900 truncate max-w-xs sm:max-w-md">
                {selectedFile.name}
              </p>
              <p className="text-[11px] text-blue-700 font-medium">
                {formatFileSize(selectedFile.size)}
              </p>
            </div>
          </div>
          <button
            type="button"
            onClick={handleRemoveFile}
            className="p-1.5 rounded-lg text-slate-400 hover:text-red-600 hover:bg-white transition-colors focus-visible:ring-2 focus-visible:ring-blue-600"
            aria-label={t("dropzone.removeFile")}
          >
            <X className="w-4 h-4" />
          </button>
        </div>
      )}
    </div>
  );
}
