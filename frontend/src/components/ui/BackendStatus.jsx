import React from "react";
import { Server, RefreshCw } from "lucide-react";
import { useLanguage } from "../../hooks/useLanguage";

export function BackendStatus({
  status = "checking",
  version,
  onRetry,
  showRetry = false,
  className = "",
}) {
  const { t } = useLanguage();

  const configMap = {
    online: {
      dot: "bg-emerald-500",
      ring: "ring-emerald-400/30",
      badge: "bg-emerald-50 text-emerald-800 border-emerald-200",
      label: t("status.connected"),
    },
    offline: {
      dot: "bg-rose-500",
      ring: "ring-rose-400/30",
      badge: "bg-rose-50 text-rose-800 border-rose-200",
      label: t("status.offline"),
    },
    degraded: {
      dot: "bg-amber-500",
      ring: "ring-amber-400/30",
      badge: "bg-amber-50 text-amber-800 border-amber-200",
      label: t("status.degraded"),
    },
    checking: {
      dot: "bg-amber-400 animate-pulse",
      ring: "ring-amber-400/30",
      badge: "bg-amber-50 text-amber-800 border-amber-200",
      label: t("status.checking"),
    },
  };

  const current = configMap[status] || configMap.checking;

  return (
    <div className={`inline-flex items-center gap-2 ${className}`}>
      <div
        className={`inline-flex items-center gap-2 px-2.5 py-1 rounded-full border text-xs font-medium transition-colors select-none ${current.badge}`}
        title={version ? `CivicLens API v${version}` : "Backend status"}
      >
        <span className="relative flex h-2 w-2">
          {status === "online" && (
            <span className="animate-ping absolute inline-flex h-full w-full rounded-full bg-emerald-400 opacity-75" />
          )}
          <span className={`relative inline-flex rounded-full h-2 w-2 ${current.dot}`} />
        </span>
        <span className="flex items-center gap-1.5">
          <Server className="w-3 h-3 text-slate-400" />
          <span>{current.label}</span>
          {version && status === "online" && (
            <span className="text-[10px] text-emerald-600 font-mono font-semibold">
              v{version}
            </span>
          )}
        </span>
      </div>

      {showRetry && (status === "offline" || status === "degraded") && onRetry && (
        <button
          type="button"
          onClick={onRetry}
          className="p-1 rounded-md text-slate-400 hover:text-blue-600 hover:bg-slate-100 transition-colors focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-blue-600 cursor-pointer"
          aria-label={t("common.retry")}
          title={t("common.retry")}
        >
          <RefreshCw className="w-3.5 h-3.5" />
        </button>
      )}
    </div>
  );
}
