import React from "react";
import { Link } from "react-router-dom";
import { AlertCircle, ArrowLeft } from "lucide-react";
import { Button } from "../components/ui/Button";
import { useLanguage } from "../hooks/useLanguage";

export function NotFound() {
  const { t } = useLanguage();

  return (
    <div className="min-h-[70vh] flex items-center justify-center p-6 text-center">
      <div className="max-w-md w-full bg-white p-8 rounded-2xl border border-slate-200 shadow-xs">
        <div className="w-16 h-16 rounded-2xl bg-amber-50 text-amber-600 flex items-center justify-center mx-auto mb-4">
          <AlertCircle className="w-8 h-8" />
        </div>
        <h1 className="text-4xl font-extrabold text-slate-900 mb-2">404</h1>
        <h2 className="text-lg font-semibold text-slate-800 mb-2">
          {t("pages.notFound.title")}
        </h2>
        <p className="text-sm text-slate-500 mb-6 leading-relaxed">
          {t("pages.notFound.description")}
        </p>
        <div className="flex flex-col sm:flex-row items-center justify-center gap-3">
          <Link to="/">
            <Button variant="secondary" icon={ArrowLeft}>
              {t("common.backHome")}
            </Button>
          </Link>
          <Link to="/dashboard">
            <Button variant="primary">
              {t("common.backToDashboard")}
            </Button>
          </Link>
        </div>
      </div>
    </div>
  );
}
