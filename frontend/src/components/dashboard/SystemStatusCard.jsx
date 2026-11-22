import React, { useState, useEffect, useCallback } from "react";
import {
  Server,
  Terminal,
  RotateCcw,
  CheckCircle2,
  AlertCircle,
  Clock,
  Languages,
  Sparkles,
  Cpu,
  Loader2,
  Zap,
} from "lucide-react";
import { Card, CardHeader, CardTitle, CardContent } from "../ui/Card";
import { Badge } from "../ui/Badge";
import { Button } from "../ui/Button";
import { Alert } from "../ui/Alert";
import { Skeleton } from "../ui/Skeleton";
import { useLanguage } from "../../hooks/useLanguage";
import { getGeminiStatus, runGeminiTest } from "../../services/geminiService";

export function SystemStatusCard({
  status = "checking",
  info = null,
  lastChecked = null,
  error = null,
  onRetry,
  className = "",
}) {
  const { t } = useLanguage();

  const [geminiStatus, setGeminiStatus] = useState(null);
  const [testState, setTestState] = useState({
    loading: false,
    result: null,
    error: null,
  });

  const fetchGeminiStatus = useCallback(async () => {
    try {
      const data = await getGeminiStatus({ timeout: 5000 });
      setGeminiStatus(data);
    } catch {
      // Keep silent fallback; system status will reflect offline
    }
  }, []);

  useEffect(() => {
    if (status === "online") {
      // oxlint-disable-next-line react/set-state-in-effect
      fetchGeminiStatus();
    }
  }, [status, fetchGeminiStatus]);

  const handleRunTest = async () => {
    setTestState({ loading: true, result: null, error: null });
    try {
      const data = await runGeminiTest({ timeout: 15000 });
      setTestState({ loading: false, result: data, error: null });
    } catch (err) {
      setTestState({
        loading: false,
        result: null,
        error: err?.message || t("status.geminiTestFailed"),
      });
    }
  };

  const formatLastChecked = (date) => {
    if (!date) return "";
    return date.toLocaleTimeString([], {
      hour: "2-digit",
      minute: "2-digit",
      second: "2-digit",
    });
  };

  const isGeminiConfigured = info?.gemini_configured ?? geminiStatus?.configured ?? false;
  const activeModelName = geminiStatus?.model || "gemini-2.5-flash";

  return (
    <Card className={`overflow-hidden ${className}`}>
      <CardHeader>
        <div className="flex items-center justify-between">
          <CardTitle className="flex items-center gap-2">
            <Server className="w-4 h-4 text-slate-500" />
            <span>{t("status.cardTitle")}</span>
          </CardTitle>
          <div className="flex items-center gap-2">
            {status === "online" ? (
              <Badge variant="success" size="sm">
                <span className="w-1.5 h-1.5 rounded-full bg-emerald-500 mr-1 animate-pulse" />
                {t("status.connected")}
              </Badge>
            ) : status === "degraded" ? (
              <Badge variant="warning" size="sm">
                <span className="w-1.5 h-1.5 rounded-full bg-amber-500 mr-1 animate-pulse" />
                {t("status.degraded")}
              </Badge>
            ) : status === "offline" ? (
              <Badge variant="danger" size="sm">
                <span className="w-1.5 h-1.5 rounded-full bg-rose-500 mr-1" />
                {t("status.offline")}
              </Badge>
            ) : (
              <Badge variant="warning" size="sm">
                <span className="w-1.5 h-1.5 rounded-full bg-amber-400 mr-1 animate-pulse" />
                {t("status.checking")}
              </Badge>
            )}
          </div>
        </div>
      </CardHeader>

      <CardContent className="space-y-4">
        {status === "checking" && !info ? (
          <div className="space-y-3 py-2">
            <div className="flex items-center gap-2 text-xs text-slate-500">
              <span className="w-2 h-2 rounded-full bg-amber-400 animate-ping" />
              <span>{t("status.connectingMessage")}</span>
            </div>
            <Skeleton height="1.25rem" width="70%" />
            <Skeleton height="1rem" width="90%" />
          </div>
        ) : status === "offline" ? (
          <div className="space-y-4">
            <Alert variant="error" title={t("status.offlineAlertTitle")}>
              <p className="text-xs text-rose-900 mb-2">
                {error || t("status.offlineAlertDesc")}
              </p>
              <p className="text-xs font-semibold text-rose-950 mb-1 flex items-center gap-1.5">
                <Terminal className="w-3.5 h-3.5" />
                <span>{t("status.offlineCommandHelp")}</span>
              </p>
              <div className="bg-slate-900 text-slate-100 p-2.5 rounded-lg font-mono text-[11px] overflow-x-auto select-all">
                <code>uvicorn app.main:app --reload --port 8000 --app-dir backend</code>
              </div>
            </Alert>

            <div className="flex items-center justify-between pt-1">
              <span className="text-xs text-slate-400">
                {lastChecked && `${t("status.lastChecked")}: ${formatLastChecked(lastChecked)}`}
              </span>
              {onRetry && (
                <Button
                  variant="primary"
                  size="sm"
                  onClick={onRetry}
                  icon={RotateCcw}
                >
                  {t("status.retryConnection")}
                </Button>
              )}
            </div>
          </div>
        ) : status === "degraded" ? (
          <div className="space-y-4">
            <Alert variant="warning" title={t("status.degradedAlertTitle")}>
              <p className="text-xs text-amber-900 mb-2">
                {error || t("status.degradedAlertDesc")}
              </p>
            </Alert>

            <div className="flex items-center justify-between pt-1">
              <span className="text-xs text-slate-400">
                {lastChecked && `${t("status.lastChecked")}: ${formatLastChecked(lastChecked)}`}
              </span>
              {onRetry && (
                <Button
                  variant="secondary"
                  size="sm"
                  onClick={onRetry}
                  icon={RotateCcw}
                >
                  {t("status.retryConnection")}
                </Button>
              )}
            </div>
          </div>
        ) : (
          <div className="space-y-4">
            {/* Live metadata grid */}
            <div className="grid grid-cols-2 sm:grid-cols-4 gap-3">
              <div className="p-3 bg-slate-50 rounded-xl border border-slate-100">
                <span className="text-[11px] font-semibold text-slate-400 uppercase tracking-wider block mb-1">
                  {t("status.version")}
                </span>
                <span className="text-sm font-bold text-slate-900 font-mono">
                  v{info?.version || "0.1.0"}
                </span>
              </div>

              <div className="p-3 bg-slate-50 rounded-xl border border-slate-100">
                <span className="text-[11px] font-semibold text-slate-400 uppercase tracking-wider block mb-1">
                  {t("status.environment")}
                </span>
                <span className="text-sm font-bold text-slate-900 capitalize">
                  {info?.environment || "development"}
                </span>
              </div>

              <div className="p-3 bg-slate-50 rounded-xl border border-slate-100">
                <span className="text-[11px] font-semibold text-slate-400 uppercase tracking-wider block mb-1 flex items-center gap-1">
                  <Languages className="w-3 h-3 text-slate-400" />
                  <span>{t("status.languages")}</span>
                </span>
                <span className="text-sm font-bold text-slate-900 uppercase">
                  {info?.supported_languages?.join(", ") || "EN, TA"}
                </span>
              </div>

              <div className="p-3 bg-slate-50 rounded-xl border border-slate-100">
                <span className="text-[11px] font-semibold text-slate-400 uppercase tracking-wider block mb-1 flex items-center gap-1">
                  <Sparkles className="w-3 h-3 text-slate-400" />
                  <span>{t("status.aiEngine")}</span>
                </span>
                <div>
                  {isGeminiConfigured ? (
                    <span className="inline-flex items-center text-xs font-semibold text-emerald-700">
                      <CheckCircle2 className="w-3.5 h-3.5 mr-1" />
                      {t("status.configured")}
                    </span>
                  ) : (
                    <span className="inline-flex items-center text-xs font-semibold text-amber-700">
                      <Clock className="w-3.5 h-3.5 mr-1 text-amber-500" />
                      {t("status.notConfigured")}
                    </span>
                  )}
                </div>
              </div>
            </div>

            {/* AI Engine & Diagnostic Test Control */}
            <div className="p-3.5 bg-gradient-to-r from-slate-50 to-blue-50/40 rounded-xl border border-slate-200/80 space-y-3">
              <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-3">
                <div className="space-y-0.5">
                  <div className="flex items-center gap-2">
                    <Cpu className="w-4 h-4 text-blue-600" />
                    <span className="text-xs font-bold text-slate-800">
                      Google Gemini AI
                    </span>
                    <span className="font-mono text-[10px] px-1.5 py-0.5 rounded bg-blue-100 text-blue-800 font-medium">
                      {activeModelName}
                    </span>
                  </div>
                  <p className="text-[11px] text-slate-500">
                    {isGeminiConfigured
                      ? t("status.diagnosticOnly")
                      : t("status.howToConfigure")}
                  </p>
                </div>

                <Button
                  variant={isGeminiConfigured ? "primary" : "outline"}
                  size="sm"
                  onClick={handleRunTest}
                  disabled={!isGeminiConfigured || testState.loading}
                  icon={testState.loading ? Loader2 : Zap}
                  className={testState.loading ? "opacity-80" : ""}
                >
                  {testState.loading
                    ? t("status.testingAi")
                    : t("status.testAiBtn")}
                </Button>
              </div>

              {/* Diagnostic Test Success Output */}
              {testState.result && (
                <div className="p-3 rounded-lg bg-emerald-50 border border-emerald-200 text-xs space-y-2 animate-fadeIn">
                  <div className="flex items-center justify-between text-emerald-900 font-semibold">
                    <span className="flex items-center gap-1.5">
                      <CheckCircle2 className="w-3.5 h-3.5 text-emerald-600" />
                      <span>{t("status.testSuccess")}</span>
                    </span>
                    <div className="flex items-center gap-3 font-mono text-[11px] text-emerald-700">
                      <span>
                        {t("status.testLatency")}: {testState.result.latency_ms} ms
                      </span>
                      {testState.result.token_usage?.total_tokens && (
                        <span>
                          {t("status.testTokens")}: {testState.result.token_usage.total_tokens}
                        </span>
                      )}
                    </div>
                  </div>
                  <p className="text-emerald-950 font-medium bg-white/70 p-2 rounded border border-emerald-200/60 text-[11px] leading-relaxed">
                    "{testState.result.message}"
                  </p>
                </div>
              )}

              {/* Diagnostic Test Error Output */}
              {testState.error && (
                <div className="p-3 rounded-lg bg-rose-50 border border-rose-200 text-xs text-rose-900 flex items-start gap-2">
                  <AlertCircle className="w-4 h-4 text-rose-600 flex-shrink-0 mt-0.5" />
                  <div>
                    <span className="font-semibold block mb-0.5">
                      {t("status.geminiTestFailed")}
                    </span>
                    <span className="text-[11px] text-rose-800">
                      {testState.error}
                    </span>
                  </div>
                </div>
              )}
            </div>

            {/* Modules status overview */}
            {info?.modules && (
              <div className="pt-2 border-t border-slate-100">
                <div className="flex items-center justify-between mb-2">
                  <span className="text-xs font-semibold text-slate-500 uppercase tracking-wider">
                    {t("status.activeModules")}
                  </span>
                  <span className="text-xs text-slate-400">
                    {info.modules.length} {t("status.modulesCount")}
                  </span>
                </div>
                <div className="grid grid-cols-1 sm:grid-cols-2 md:grid-cols-3 gap-2">
                  {info.modules.map((mod) => (
                    <div
                      key={mod.id}
                      className="p-2 rounded-lg bg-slate-50 border border-slate-100 flex items-center justify-between text-xs"
                    >
                      <span className="font-medium text-slate-800 truncate pr-2">
                        {mod.title}
                      </span>
                      <span className="text-[10px] font-semibold text-blue-700 uppercase bg-blue-50 px-1.5 py-0.5 rounded border border-blue-200">
                        {mod.status}
                      </span>
                    </div>
                  ))}
                </div>
              </div>
            )}

            {/* Footer with last checked time and manual recheck */}
            <div className="pt-2 flex items-center justify-between text-xs text-slate-400 border-t border-slate-100">
              <span>
                {lastChecked && `${t("status.lastChecked")}: ${formatLastChecked(lastChecked)}`}
              </span>
              {onRetry && (
                <button
                  type="button"
                  onClick={onRetry}
                  className="hover:text-blue-700 transition-colors inline-flex items-center gap-1 font-medium cursor-pointer"
                >
                  <RotateCcw className="w-3 h-3" />
                  <span>{t("common.retry")}</span>
                </button>
              )}
            </div>
          </div>
        )}
      </CardContent>
    </Card>
  );
}
