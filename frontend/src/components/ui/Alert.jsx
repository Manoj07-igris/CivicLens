import React from "react";
import { Info, CheckCircle2, AlertTriangle, AlertCircle, X } from "lucide-react";
import { useLanguage } from "../../hooks/useLanguage";

export function Alert({
  variant,
  type,
  title,
  message,
  children,
  dismissible = false,
  onDismiss,
  className = "",
  id,
}) {
  const { language } = useLanguage();

  // Normalize variant aliases across codebase (type vs variant, danger vs error)
  const rawVariant = (variant || type || "info").toLowerCase();
  const normalizedVariant =
    rawVariant === "danger"
      ? "error"
      : rawVariant === "warn"
      ? "warning"
      : ["info", "success", "warning", "error"].includes(rawVariant)
      ? rawVariant
      : "info";

  const variantStyles = {
    info: {
      container: "bg-blue-50 border-blue-200 text-blue-900",
      icon: Info,
      iconColor: "text-blue-600",
    },
    success: {
      container: "bg-emerald-50 border-emerald-200 text-emerald-900",
      icon: CheckCircle2,
      iconColor: "text-emerald-600",
    },
    warning: {
      container: "bg-amber-50 border-amber-200 text-amber-900",
      icon: AlertTriangle,
      iconColor: "text-amber-600",
    },
    error: {
      container: "bg-rose-50 border-rose-200 text-rose-900",
      icon: AlertCircle,
      iconColor: "text-rose-600",
    },
  };

  const current = variantStyles[normalizedVariant] || variantStyles.info;
  const Icon = current.icon;

  // Resolve content from children or message prop
  let content = children !== undefined && children !== null ? children : message;

  // If content is an object with a message property, extract string
  if (content && typeof content === "object" && !React.isValidElement(content)) {
    content = content.message || content.error || JSON.stringify(content);
  }

  // Defensive fallback: An alert must never be completely blank
  const hasTitle = Boolean(title && String(title).trim());
  const hasContent = Boolean(content && (React.isValidElement(content) || String(content).trim()));

  if (!hasTitle && !hasContent) {
    if (import.meta.env?.DEV) {
      console.warn("[CivicLens Alert] Alert rendered with empty or missing message/children.");
    }
    content =
      language === "ta"
        ? "ஏதோ தவறு நிகழ்ந்துவிட்டது. மீண்டும் முயற்சிக்கவும்."
        : "Something went wrong. Please try again.";
  }

  return (
    <div
      id={id}
      role="alert"
      aria-live={normalizedVariant === "error" ? "assertive" : "polite"}
      className={`flex items-start gap-3 p-4 rounded-xl border ${current.container} ${className}`}
    >
      <Icon className={`w-5 h-5 flex-shrink-0 mt-0.5 ${current.iconColor}`} aria-hidden="true" />
      <div className="flex-1 text-sm">
        {hasTitle && <h4 className="font-semibold mb-1 leading-snug">{title}</h4>}
        {content && <div className="leading-relaxed text-slate-700">{content}</div>}
      </div>
      {dismissible && onDismiss && (
        <button
          type="button"
          onClick={onDismiss}
          className="text-slate-400 hover:text-slate-600 p-0.5 rounded focus-visible:ring-2 focus-visible:ring-blue-600 cursor-pointer"
          aria-label="Dismiss alert"
        >
          <X className="w-4 h-4" />
        </button>
      )}
    </div>
  );
}
