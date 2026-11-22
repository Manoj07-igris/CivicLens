import React, { forwardRef } from "react";

export const Input = forwardRef(function Input(
  {
    label,
    error,
    helperText,
    id,
    type = "text",
    leftIcon: LeftIcon,
    rightIcon: RightIcon,
    className = "",
    disabled = false,
    required = false,
    ...props
  },
  ref
) {
  const inputId = id || (label ? label.toLowerCase().replace(/\s+/g, "-") : undefined);

  return (
    <div className="w-full flex flex-col gap-1.5 text-left">
      {label && (
        <label htmlFor={inputId} className="text-xs font-semibold text-slate-700 flex items-center gap-1">
          {label}
          {required && <span className="text-red-500">*</span>}
        </label>
      )}
      <div className="relative flex items-center">
        {LeftIcon && (
          <div className="absolute left-3 pointer-events-none text-slate-400">
            <LeftIcon className="w-4 h-4" />
          </div>
        )}
        <input
          ref={ref}
          id={inputId}
          type={type}
          disabled={disabled}
          required={required}
          className={`w-full rounded-lg border bg-white text-sm text-slate-900 transition-colors placeholder:text-slate-400 
            ${LeftIcon ? "pl-9" : "pl-3.5"} 
            ${RightIcon ? "pr-9" : "pr-3.5"} 
            py-2 
            ${
              error
                ? "border-red-400 focus:border-red-500 focus-visible:ring-red-200"
                : "border-slate-300 focus:border-blue-600 focus-visible:ring-blue-100"
            } 
            disabled:bg-slate-50 disabled:text-slate-400 disabled:border-slate-200 
            focus-visible:outline-none focus-visible:ring-3 ${className}`}
          {...props}
        />
        {RightIcon && (
          <div className="absolute right-3 pointer-events-none text-slate-400">
            <RightIcon className="w-4 h-4" />
          </div>
        )}
      </div>
      {error ? (
        <p className="text-xs text-red-600 font-medium">{error}</p>
      ) : helperText ? (
        <p className="text-xs text-slate-500">{helperText}</p>
      ) : null}
    </div>
  );
});
