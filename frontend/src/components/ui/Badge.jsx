import React from "react";
import { CheckCircle2, XCircle, HelpCircle, Clock } from "lucide-react";

export function Badge({
  children,
  variant = "default",
  size = "md",
  icon = true,
  className = "",
  ...props
}) {
  const sizeClasses = {
    sm: "text-xs px-2 py-0.5 gap-1",
    md: "text-xs px-2.5 py-1 gap-1.5 font-medium",
  };

  const variantMap = {
    default: "bg-slate-100 text-slate-700 border-slate-200",
    primary: "bg-blue-50 text-blue-800 border-blue-200",
    success: "bg-emerald-50 text-emerald-800 border-emerald-200",
    warning: "bg-amber-50 text-amber-800 border-amber-200",
    danger: "bg-rose-50 text-rose-800 border-rose-200",
    outline: "bg-transparent text-slate-700 border-slate-300",

    // Fact Verification Specific Categories
    supported: "bg-emerald-50 text-emerald-800 border-emerald-300 ring-1 ring-emerald-500/20",
    contradicted: "bg-rose-50 text-rose-800 border-rose-300 ring-1 ring-rose-500/20",
    unverified: "bg-amber-50 text-amber-800 border-amber-300 ring-1 ring-amber-500/20",
    outdated: "bg-purple-50 text-purple-800 border-purple-300 ring-1 ring-purple-500/20",
    mixed: "bg-indigo-50 text-indigo-800 border-indigo-300 ring-1 ring-indigo-500/20",
  };

  // Icon mapping for verification badges
  let StatusIcon = null;
  if (icon) {
    if (variant === "supported") StatusIcon = CheckCircle2;
    else if (variant === "contradicted") StatusIcon = XCircle;
    else if (variant === "unverified") StatusIcon = HelpCircle;
    else if (variant === "outdated") StatusIcon = Clock;
    else if (variant === "mixed") StatusIcon = HelpCircle;
  }

  const selectedVariant = variantMap[variant.toLowerCase()] || variantMap.default;

  return (
    <span
      className={`inline-flex items-center rounded-full border ${sizeClasses[size] || sizeClasses.md} ${selectedVariant} ${className}`}
      {...props}
    >
      {StatusIcon && <StatusIcon className="w-3.5 h-3.5 flex-shrink-0" />}
      <span>{children}</span>
    </span>
  );
}
