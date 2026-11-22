import React from "react";
import { Spinner } from "./Spinner";

export function Button({
  children,
  variant = "primary",
  size = "md",
  isLoading = false,
  loading,
  disabled = false,
  icon: Icon,
  iconPosition = "left",
  type = "button",
  className = "",
  onClick,
  ...props
}) {
  const baseClasses =
    "inline-flex items-center justify-center font-medium rounded-lg transition-colors duration-150 select-none cursor-pointer disabled:cursor-not-allowed disabled:opacity-60 focus-visible:ring-2 focus-visible:ring-blue-600 focus-visible:outline-none focus-visible:ring-offset-2";

  const sizeClasses = {
    sm: "text-xs px-2.5 py-1.5 gap-1.5",
    md: "text-sm px-4 py-2 gap-2",
    lg: "text-base px-5 py-2.5 gap-2.5",
  };

  const variantClasses = {
    primary:
      "bg-blue-700 hover:bg-blue-800 text-white shadow-xs border border-transparent active:bg-blue-900",
    secondary:
      "bg-slate-100 hover:bg-slate-200 text-slate-800 border border-slate-200 active:bg-slate-300",
    outline:
      "bg-transparent hover:bg-blue-50 text-blue-700 border border-blue-600 active:bg-blue-100",
    ghost:
      "bg-transparent hover:bg-slate-100 text-slate-700 active:bg-slate-200",
    danger:
      "bg-red-600 hover:bg-red-700 text-white shadow-xs border border-transparent active:bg-red-800",
  };

  const isButtonLoading = Boolean(loading ?? isLoading);
  const isDisabled = disabled || isButtonLoading;

  return (
    <button
      type={type}
      disabled={isDisabled}
      aria-busy={isButtonLoading ? "true" : undefined}
      onClick={onClick}
      className={`${baseClasses} ${sizeClasses[size] || sizeClasses.md} ${
        variantClasses[variant] || variantClasses.primary
      } ${className}`}
      {...props}
    >
      {isButtonLoading ? (
        <>
          <Spinner size={size === "lg" ? "md" : "sm"} color="currentColor" />
          <span>{children}</span>
        </>
      ) : (
        <>
          {Icon && iconPosition === "left" && <Icon className="w-4 h-4 flex-shrink-0" />}
          <span>{children}</span>
          {Icon && iconPosition === "right" && <Icon className="w-4 h-4 flex-shrink-0" />}
        </>
      )}
    </button>
  );
}

export default Button;
