import React, { useState } from "react";
import {
  Database as DatabaseIcon,
  HardDrive,
  DownloadCloud,
  Wrench,
  Trash2,
  AlertTriangle,
  CheckCircle2,
  Clock,
  ShieldAlert,
} from "lucide-react";
import { Card, CardHeader, CardTitle, CardContent } from "../ui/Card";
import { Badge } from "../ui/Badge";
import { Button } from "../ui/Button";
import { Modal } from "../ui/Modal";
import { Alert } from "../ui/Alert";
import { useLanguage } from "../../hooks/useLanguage";
import { useToast } from "../../hooks/useToast";
import { deleteData } from "../../services/systemService";

function formatBytes(bytes) {
  if (bytes === 0) return "0 B";
  if (!bytes) return "0 B";
  const k = 1024;
  const sizes = ["B", "KB", "MB", "GB"];
  const i = Math.floor(Math.log(bytes) / Math.log(k));
  return parseFloat((bytes / Math.pow(k, i)).toFixed(1)) + " " + sizes[i];
}

export function StorageManagementCard({
  status,
  stats,
  onTriggerBackup,
  onTriggerMaintenance,
  onDataDeleted,
  className = "",
}) {
  const { t } = useLanguage();
  const { showToast } = useToast();

  const [isBackupLoading, setIsBackupLoading] = useState(false);
  const [isMaintenanceModalOpen, setIsMaintenanceModalOpen] = useState(false);
  const [isMaintenanceLoading, setIsMaintenanceLoading] = useState(false);
  const [maintenanceOptions, setMaintenanceOptions] = useState({
    removeOrphans: true,
    vacuum: false,
  });

  const [isDeleteModalOpen, setIsDeleteModalOpen] = useState(false);
  const [confirmPhraseInput, setConfirmPhraseInput] = useState("");
  const [includeLibrary, setIncludeLibrary] = useState(false);
  const [isDeleting, setIsDeleting] = useState(false);
  const [deleteError, setDeleteError] = useState(null);

  const storage = status?.storage || {};
  const totalBytes = storage.total_bytes || 0;
  const dbState = status?.database_state || "ok";
  const schemaVer = status?.schema_version || 1;

  const handleBackup = async () => {
    setIsBackupLoading(true);
    try {
      const res = await onTriggerBackup();
      showToast({
        title: t("storage.backupSuccessTitle", "Database Backup Created"),
        message: `${res?.backup_file} (${formatBytes(res?.size_bytes)})`,
        variant: "success",
      });
    } catch (err) {
      showToast({
        title: t("storage.backupErrorTitle", "Backup Failed"),
        message: err?.message || "Could not complete online backup.",
        variant: "error",
      });
    } finally {
      setIsBackupLoading(false);
    }
  };

  const handleMaintenance = async () => {
    setIsMaintenanceLoading(true);
    try {
      const res = await onTriggerMaintenance({
        remove_orphans: maintenanceOptions.removeOrphans,
        vacuum: maintenanceOptions.vacuum,
      });
      setIsMaintenanceModalOpen(false);
      showToast({
        title: t("storage.maintenanceSuccessTitle", "Maintenance Completed"),
        message: `Pruned ${res?.activity_records_pruned || 0} activity records, ${res?.interrupted_jobs_failed || 0} interrupted jobs cleaned.`,
        variant: "success",
      });
    } catch (err) {
      showToast({
        title: t("storage.maintenanceErrorTitle", "Maintenance Failed"),
        message: err?.message || "Maintenance execution encountered an issue.",
        variant: "error",
      });
    } finally {
      setIsMaintenanceLoading(false);
    }
  };

  const handleDeleteData = async () => {
    if (confirmPhraseInput.trim() !== "DELETE MY DATA") return;
    setIsDeleting(true);
    setDeleteError(null);
    try {
      await deleteData("DELETE MY DATA", includeLibrary);
      setIsDeleteModalOpen(false);
      setConfirmPhraseInput("");
      showToast({
        title: t("storage.deleteSuccessTitle", "Data Cleared"),
        message: "All citizen prototype data has been safely wiped.",
        variant: "info",
      });
      if (onDataDeleted) onDataDeleted();
    } catch (err) {
      setDeleteError(err?.message || "Failed to delete data.");
    } finally {
      setIsDeleting(false);
    }
  };

  return (
    <Card className={className}>
      <CardHeader>
        <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-3">
          <CardTitle className="flex items-center gap-2">
            <DatabaseIcon className="w-4 h-4 text-slate-500" />
            <span>{t("storage.cardTitle", "Data, Database & Storage")}</span>
          </CardTitle>
          <div className="flex items-center gap-2">
            <Badge variant={dbState === "ok" ? "success" : "danger"} size="sm">
              <span className={`w-1.5 h-1.5 rounded-full ${dbState === "ok" ? "bg-emerald-500 animate-pulse" : "bg-rose-500"} mr-1`} />
              {dbState === "ok" ? "SQLite WAL Healthy" : "Degraded"}
            </Badge>
            <Badge variant="outline" size="sm">
              Schema v{schemaVer}
            </Badge>
          </div>
        </div>
      </CardHeader>

      <CardContent className="space-y-6">
        {/* Storage usage summary */}
        <div className="space-y-2">
          <div className="flex items-center justify-between text-xs">
            <span className="font-semibold text-slate-700 flex items-center gap-1.5">
              <HardDrive className="w-3.5 h-3.5 text-slate-400" />
              <span>{t("storage.totalDiskUsage", "Total On-Disk Storage")}</span>
            </span>
            <span className="font-mono font-bold text-slate-900">{formatBytes(totalBytes)}</span>
          </div>

          {/* Breakdown Pills */}
          <div className="grid grid-cols-2 sm:grid-cols-4 gap-2 text-[11px] pt-1">
            <div className="p-2 bg-slate-50 border border-slate-200/60 rounded-lg">
              <span className="text-slate-400 block truncate">{t("storage.uploads", "User PDFs")}</span>
              <span className="font-semibold text-slate-800 font-mono">{formatBytes(storage.uploads_bytes)}</span>
            </div>
            <div className="p-2 bg-slate-50 border border-slate-200/60 rounded-lg">
              <span className="text-slate-400 block truncate">{t("storage.indexes", "Vector Indexes")}</span>
              <span className="font-semibold text-slate-800 font-mono">{formatBytes(storage.indexes_bytes)}</span>
            </div>
            <div className="p-2 bg-slate-50 border border-slate-200/60 rounded-lg">
              <span className="text-slate-400 block truncate">{t("storage.database", "SQLite DB + WAL")}</span>
              <span className="font-semibold text-slate-800 font-mono">{formatBytes(storage.database_bytes)}</span>
            </div>
            <div className="p-2 bg-slate-50 border border-slate-200/60 rounded-lg">
              <span className="text-slate-400 block truncate">{t("storage.backups", "DB Backups")}</span>
              <span className="font-semibold text-slate-800 font-mono">{formatBytes(storage.backups_bytes)}</span>
            </div>
          </div>
        </div>

        {/* Action Controls */}
        <div className="pt-2 border-t border-slate-100 flex flex-wrap items-center justify-between gap-3">
          <div className="flex flex-wrap items-center gap-2">
            <Button
              variant="outline"
              size="sm"
              icon={DownloadCloud}
              onClick={handleBackup}
              disabled={isBackupLoading}
            >
              {isBackupLoading ? t("storage.backingUp", "Backing up...") : t("storage.backUpNow", "Back up now")}
            </Button>
            <Button
              variant="outline"
              size="sm"
              icon={Wrench}
              onClick={() => setIsMaintenanceModalOpen(true)}
            >
              {t("storage.maintenance", "Maintenance")}
            </Button>
          </div>

          <Button
            variant="danger"
            size="sm"
            icon={Trash2}
            onClick={() => setIsDeleteModalOpen(true)}
          >
            {t("storage.deleteMyData", "Delete my data")}
          </Button>
        </div>
      </CardContent>

      {/* Maintenance Modal */}
      <Modal
        isOpen={isMaintenanceModalOpen}
        onClose={() => setIsMaintenanceModalOpen(false)}
        title={t("storage.maintenanceModalTitle", "System Maintenance & Optimization")}
      >
        <div className="space-y-4">
          <p className="text-xs text-slate-600">
            {t(
              "storage.maintenanceModalDesc",
              "Execute routine maintenance tasks to keep your CivicLens storage compact, resolve interrupted background tasks, and prune historical activity logs."
            )}
          </p>

          <div className="space-y-2 bg-slate-50 p-3 rounded-lg border border-slate-200 text-xs">
            <label className="flex items-center gap-2 cursor-pointer">
              <input
                type="checkbox"
                checked={maintenanceOptions.removeOrphans}
                onChange={(e) =>
                  setMaintenanceOptions((prev) => ({ ...prev, removeOrphans: e.target.checked }))
                }
                className="rounded text-blue-600 focus:ring-blue-500"
              />
              <span>{t("storage.removeOrphans", "Scan and remove unreferenced orphan files/folders")}</span>
            </label>
            <label className="flex items-center gap-2 cursor-pointer">
              <input
                type="checkbox"
                checked={maintenanceOptions.vacuum}
                onChange={(e) =>
                  setMaintenanceOptions((prev) => ({ ...prev, vacuum: e.target.checked }))
                }
                className="rounded text-blue-600 focus:ring-blue-500"
              />
              <span>{t("storage.runVacuum", "Run SQLite VACUUM to reclaim disk space")}</span>
            </label>
          </div>

          <div className="flex justify-end gap-2 pt-2">
            <Button variant="outline" size="sm" onClick={() => setIsMaintenanceModalOpen(false)}>
              {t("common.cancel", "Cancel")}
            </Button>
            <Button
              variant="primary"
              size="sm"
              icon={Wrench}
              onClick={handleMaintenance}
              disabled={isMaintenanceLoading}
            >
              {isMaintenanceLoading ? t("storage.running", "Running...") : t("storage.runMaintenanceAction", "Run Maintenance")}
            </Button>
          </div>
        </div>
      </Modal>

      {/* Delete Data Confirmation Modal */}
      <Modal
        isOpen={isDeleteModalOpen}
        onClose={() => setIsDeleteModalOpen(false)}
        title={t("storage.deleteModalTitle", "Delete All Local Data")}
      >
        <div className="space-y-4">
          <Alert variant="error" title={t("storage.deleteModalWarning", "Irreversible Action")}>
            {t(
              "storage.deleteModalWarningDesc",
              "This will permanently delete all uploaded documents, policy comparisons, fact verifications, service guides, complaints, demo sessions, and conversation messages from this device."
            )}
          </Alert>

          <label className="flex items-center gap-2 text-xs text-slate-700 cursor-pointer">
            <input
              type="checkbox"
              checked={includeLibrary}
              onChange={(e) => setIncludeLibrary(e.target.checked)}
              className="rounded text-rose-600 focus:ring-rose-500"
            />
            <span>{t("storage.includeLibrary", "Also delete official sources in the library (resets to defaults)")}</span>
          </label>

          <div className="space-y-1.5">
            <label className="text-xs font-semibold text-slate-700 block">
              {t("storage.confirmPhrasePrompt", "Type 'DELETE MY DATA' to confirm:")}
            </label>
            <input
              type="text"
              value={confirmPhraseInput}
              onChange={(e) => setConfirmPhraseInput(e.target.value)}
              placeholder="DELETE MY DATA"
              className="w-full px-3 py-2 text-xs border border-slate-300 rounded-lg focus:outline-none focus:ring-2 focus:ring-rose-500 font-mono uppercase"
            />
          </div>

          {deleteError && (
            <p className="text-xs text-rose-600 font-medium">{deleteError}</p>
          )}

          <div className="flex justify-end gap-2 pt-2">
            <Button variant="outline" size="sm" onClick={() => setIsDeleteModalOpen(false)}>
              {t("common.cancel", "Cancel")}
            </Button>
            <Button
              variant="danger"
              size="sm"
              icon={Trash2}
              onClick={handleDeleteData}
              disabled={confirmPhraseInput.trim() !== "DELETE MY DATA" || isDeleting}
            >
              {isDeleting ? t("storage.deleting", "Deleting...") : t("storage.confirmDelete", "Permanently Delete Data")}
            </Button>
          </div>
        </div>
      </Modal>
    </Card>
  );
}
