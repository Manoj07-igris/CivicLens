import React, { useState, useEffect } from "react";
import { Link } from "react-router-dom";
import {
  History,
  MessageSquare,
  FileText,
  GitCompare,
  ShieldCheck,
  Compass,
  LifeBuoy,
  Monitor,
  ArrowUpRight,
} from "lucide-react";
import { Card, CardHeader, CardTitle, CardContent } from "../ui/Card";
import { EmptyState } from "../ui/EmptyState";
import { Button } from "../ui/Button";
import { Badge } from "../ui/Badge";
import { useLanguage } from "../../hooks/useLanguage";
import { getActivity } from "../../services/systemService";

function getEventIcon(eventType) {
  if (eventType.startsWith("document")) return FileText;
  if (eventType.startsWith("comparison")) return GitCompare;
  if (eventType.startsWith("verification")) return ShieldCheck;
  if (eventType.startsWith("service")) return Compass;
  if (eventType.startsWith("grievance")) return LifeBuoy;
  if (eventType.startsWith("browser")) return Monitor;
  return MessageSquare;
}

function formatRelativeTime(isoString, lang = "en") {
  if (!isoString) return "";
  try {
    const diffSec = Math.floor((Date.now() - new Date(isoString).getTime()) / 1000);
    if (diffSec < 60) return lang === "ta" ? "சற்று முன்" : "just now";
    const diffMin = Math.floor(diffSec / 60);
    if (diffMin < 60) return lang === "ta" ? `${diffMin} நிமிடம் முன்` : `${diffMin}m ago`;
    const diffHr = Math.floor(diffMin / 60);
    if (diffHr < 24) return lang === "ta" ? `${diffHr} மணி முன்` : `${diffHr}h ago`;
    const diffDay = Math.floor(diffHr / 24);
    return lang === "ta" ? `${diffDay} நாள் முன்` : `${diffDay}d ago`;
  } catch {
    return isoString.slice(0, 10);
  }
}

export function RecentActivity({ className = "" }) {
  const { t, language } = useLanguage();
  const [items, setItems] = useState([]);
  const [isLoading, setIsLoading] = useState(true);

  useEffect(() => {
    getActivity({ limit: 6 })
      .then((res) => {
        setItems(res?.items || []);
      })
      .catch((err) => {
        console.warn("Failed to load activity feed", err);
      })
      .finally(() => {
        setIsLoading(false);
      });
  }, []);

  return (
    <Card className={className}>
      <CardHeader>
        <div className="flex items-center justify-between">
          <CardTitle className="flex items-center gap-2">
            <History className="w-4 h-4 text-slate-500" />
            <span>{t("dashboard.activity.title", "Recent Activity")}</span>
          </CardTitle>
          {items.length > 0 && (
            <Badge variant="outline" size="sm">
              {items.length} {t("dashboard.activity.recent", "recent")}
            </Badge>
          )}
        </div>
      </CardHeader>
      <CardContent>
        {isLoading ? (
          <div className="space-y-3 py-2">
            <div className="h-4 bg-slate-100 rounded w-3/4 animate-pulse" />
            <div className="h-4 bg-slate-100 rounded w-1/2 animate-pulse" />
            <div className="h-4 bg-slate-100 rounded w-2/3 animate-pulse" />
          </div>
        ) : items && items.length > 0 ? (
          <div className="divide-y divide-slate-100">
            {items.map((item) => {
              const Icon = getEventIcon(item.event_type);
              const isDeleted = item.is_deleted;
              return (
                <div key={item.id} className="py-2.5 flex items-center justify-between gap-3 text-sm">
                  <div className="flex items-center gap-2.5 min-w-0">
                    <div className="w-7 h-7 rounded-lg bg-slate-100 text-slate-600 flex items-center justify-center flex-shrink-0">
                      <Icon className="w-3.5 h-3.5" />
                    </div>
                    <div className="min-w-0">
                      <div className="flex items-center gap-1.5">
                        {isDeleted ? (
                          <span className="text-slate-400 italic text-xs truncate max-w-xs">
                            {item.title}
                          </span>
                        ) : (
                          <Link
                            to={item.open_hint || "/"}
                            className="font-medium text-slate-800 hover:text-blue-600 text-xs truncate max-w-xs transition-colors inline-flex items-center gap-1"
                          >
                            <span className="truncate">{item.title}</span>
                            <ArrowUpRight className="w-3 h-3 flex-shrink-0 text-slate-400" />
                          </Link>
                        )}
                      </div>
                      <span className="text-[11px] text-slate-400 capitalize block">
                        {item.event_type.replace(".", " • ")}
                      </span>
                    </div>
                  </div>
                  <span className="text-[11px] text-slate-400 flex-shrink-0 font-mono">
                    {formatRelativeTime(item.created_at, language)}
                  </span>
                </div>
              );
            })}
          </div>
        ) : (
          <EmptyState
            icon={History}
            title={t("dashboard.activity.emptyTitle", "No recent activity yet")}
            description={t("dashboard.activity.emptyDesc", "Uploaded documents, comparisons, and verifications will appear here.")}
            action={
              <Link to="/assistant">
                <Button variant="secondary" size="sm" icon={MessageSquare}>
                  {t("dashboard.activity.action", "Ask Assistant")}
                </Button>
              </Link>
            }
          />
        )}
      </CardContent>
    </Card>
  );
}
