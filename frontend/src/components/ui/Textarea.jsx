import React, { forwardRef } from "react";

export const Textarea = forwardRef(function Textarea(
  {
    label,
    error,
    helperText,
    id,
    rows = 4,
    className = "",
    disabled = false,
    required = false,
    ...props
  },
  ref
) {
  const textareaId = id || (label ? label.toLowerCase().replace(/\s+/g, "-") : undefined);

  return (
    <div className="w-full flex flex-col gap-1.5 text-left">
      {label && (
        <label htmlFor={textareaId} className="text-xs font-semibold text-slate-700 flex items-center gap-1">
          {label}
          {required && <span className="text-red-500">*</span>}
        </label>
      )}
      <textarea
        ref={ref}
        id={textareaId}
        rows={rows}
        disabled={disabled}
        required={required}
        className={`w-full rounded-lg border bg-white p-3 text-sm text-slate-900 transition-colors placeholder:text-slate-400 
          ${
            error
              ? "border-red-400 focus:border-red-500 focus-visible:ring-red-200"
              : "border-slate-300 focus:border-blue-600 focus-visible:ring-blue-100"
          } 
          disabled:bg-slate-50 disabled:text-slate-400 disabled:border-slate-200 
          focus-visible:outline-none focus-visible:ring-3 ${className}`}
        {...props}
      />
      {error ? (
        <p className="text-xs text-red-600 font-medium">{error}</p>
      ) : helperText ? (
        <p className="text-xs text-slate-500">{helperText}</p>
      ) : null}
    </div>
  );
});
