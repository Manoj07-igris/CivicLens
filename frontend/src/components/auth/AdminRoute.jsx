import React from "react";
import { Navigate, useLocation, Outlet } from "react-router-dom";
import useAuth from "../../hooks/useAuth";
import { Spinner } from "../ui/Spinner";
import { Alert } from "../ui/Alert";
import { Button } from "../ui/Button";
import { useLanguage } from "../../hooks/useLanguage";

export function AdminRoute({ children }) {
  const { isAuthenticated, isLoading, isAdmin } = useAuth();
  const { t } = useLanguage();
  const location = useLocation();

  if (isLoading) {
    return (
      <div className="min-h-screen flex items-center justify-center bg-surface-50 dark:bg-surface-950">
        <div className="flex flex-col items-center gap-3">
          <Spinner size="lg" />
          <p className="text-sm font-medium text-surface-500 dark:text-surface-400">
            Checking privileges...
          </p>
        </div>
      </div>
    );
  }

  if (!isAuthenticated) {
    const nextPath = encodeURIComponent(location.pathname + location.search);
    return <Navigate to={`/login?next=${nextPath}`} state={{ from: location }} replace />;
  }

  if (!isAdmin) {
    return (
      <div className="max-w-2xl mx-auto p-6 mt-12">
        <Alert
          variant="error"
          title={t("auth.adminRequiredTitle") || "Administrator Access Required"}
        >
          {t("auth.adminRequiredDesc") ||
            "This area is restricted to administrators. Your current account does not have sufficient permissions."}
        </Alert>
        <div className="mt-6 flex justify-center">
          <Button variant="primary" onClick={() => window.history.back()}>
            {t("common.back") || "Go Back"}
          </Button>
        </div>
      </div>
    );
  }

  return children ? children : <Outlet />;
}

export default AdminRoute;
