import React from "react";
import { Link } from "react-router-dom";
import { FileText, UploadCloud, ArrowRight, CheckCircle2, Clock } from "lucide-react";
import { Card, CardHeader, CardTitle, CardContent } from "../ui/Card";
import { EmptyState } from "../ui/EmptyState";
import { Button } from "../ui/Button";
import { Badge } from "../ui/Badge";
import { useLanguage } from "../../hooks/useLanguage";

export function RecentDocuments({ documents = [], className = "" }) {
  const { t } = useLanguage();

  const formatFileSize = (bytes) => {
    if (!bytes) return "";
    const k = 1024;
    const sizes = ["B", "KB", "MB", "GB"];
    const i = Math.floor(Math.log(bytes) / Math.log(k));
    return parseFloat((bytes / Math.pow(k, i)).toFixed(1)) + " " + sizes[i];
  };

  return (
    <Card className={className}>
      <CardHeader className="flex flex-row items-center justify-between">
        <CardTitle className="flex items-center gap-2">
          <FileText className="w-4 h-4 text-slate-500" />
          <span>{t("dashboard.documents.title")}</span>
        </CardTitle>
        {documents && documents.length > 0 && (
          <Link to="/documents">
            <Button variant="ghost" size="sm" icon={ArrowRight} iconPosition="right">
              {t("dashboard.documents.action")}
            </Button>
          </Link>
        )}
      </CardHeader>
      <CardContent>
        {documents && documents.length > 0 ? (
          <div className="divide-y divide-slate-100">
            {documents.slice(0, 5).map((doc) => {
              const displayName = doc.filename || doc.name || "Document";
              const sizeText = doc.file_size_bytes
                ? formatFileSize(doc.file_size_bytes)
                : doc.size || "";
              const pagesText = doc.page_count ? `${doc.page_count}p` : "";
              const isReady = doc.status === "ready" || doc.status === "ready_with_warnings";

              return (
                <div
                  key={doc.document_id || displayName}
                  className="py-3 flex items-center justify-between text-sm hover:bg-slate-50/60 px-2 rounded-lg transition-colors"
                >
                  <Link
                    to="/documents"
                    className="flex items-center gap-2.5 min-w-0 hover:text-blue-600 transition-colors"
                  >
                    <div className="w-8 h-8 rounded-lg bg-blue-50 text-blue-700 flex items-center justify-center shrink-0">
                      <FileText className="w-4 h-4" />
                    </div>
                    <div className="min-w-0">
                      <p className="font-medium text-slate-800 truncate max-w-[200px] sm:max-w-xs">
                        {displayName}
                      </p>
                      <p className="text-[11px] text-slate-400">
                        {[sizeText, pagesText].filter(Boolean).join(" • ")}
                      </p>
                    </div>
                  </Link>

                  <div>
                    {isReady ? (
                      <Badge variant="success" size="sm" className="flex items-center gap-1">
                        <CheckCircle2 className="w-3 h-3" />
                        <span>Ready</span>
                      </Badge>
                    ) : (
                      <Badge variant="primary" size="sm" className="flex items-center gap-1">
                        <Clock className="w-3 h-3" />
                        <span>Processing</span>
                      </Badge>
                    )}
                  </div>
                </div>
              );
            })}
          </div>
        ) : (
          <EmptyState
            icon={FileText}
            title={t("dashboard.documents.emptyTitle")}
            description={t("dashboard.documents.emptyDesc")}
            action={
              <Link to="/documents">
                <Button variant="secondary" size="sm" icon={UploadCloud}>
                  {t("dashboard.documents.action")}
                </Button>
              </Link>
            }
          />
        )}
      </CardContent>
    </Card>
  );
}
