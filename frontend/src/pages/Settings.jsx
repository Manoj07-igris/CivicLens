import React, { useState, useEffect, useMemo } from "react";
import useAuth from "../hooks/useAuth";
import { useLanguage } from "../hooks/useLanguage";
import { useToast } from "../hooks/useToast";
import authService from "../services/authService";
import { Card } from "../components/ui/Card";
import { Button } from "../components/ui/Button";
import { Input } from "../components/ui/Input";
import { Select } from "../components/ui/Select";
import { Alert } from "../components/ui/Alert";
import { Modal } from "../components/ui/Modal";
import { Badge } from "../components/ui/Badge";
import { Spinner } from "../components/ui/Spinner";

export function Settings() {
  const { user, updateProfile, changePassword, deleteAccount, logoutAll, setLanguage: setAuthLang } = useAuth();
  const { t, language, setLanguage } = useLanguage();
  const { addToast } = useToast();

  const [activeTab, setActiveTab] = useState("profile"); // 'profile' | 'security' | 'data'

  // Profile Form State
  const [fullName, setFullName] = useState(user?.full_name || "");
  const [preferredLang, setPreferredLang] = useState(user?.preferred_language || language || "en");
  const [savingProfile, setSavingProfile] = useState(false);

  // Security - Change Password State
  const [currentPassword, setCurrentPassword] = useState("");
  const [newPassword, setNewPassword] = useState("");
  const [confirmPassword, setConfirmPassword] = useState("");
  const [changingPass, setChangingPass] = useState(false);
  const [passError, setPassError] = useState(null);

  // Security - Sessions State
  const [sessions, setSessions] = useState([]);
  const [loadingSessions, setLoadingSessions] = useState(false);
  const [revokingSessionId, setRevokingSessionId] = useState(null);

  // Data & Privacy - Delete Account State
  const [deleteModalOpen, setDeleteModalOpen] = useState(false);
  const [deletePassword, setDeletePassword] = useState("");
  const [deleteConfirmText, setDeleteConfirmText] = useState("");
  const [deletingAccount, setDeletingAccount] = useState(false);
  const [deleteError, setDeleteError] = useState(null);

  useEffect(() => {
    if (user) {
      setFullName(user.full_name);
      setPreferredLang(user.preferred_language || "en");
    }
  }, [user]);

  // Load sessions when Security tab active
  useEffect(() => {
    if (activeTab === "security") {
      fetchSessions();
    }
  }, [activeTab]);

  const fetchSessions = async () => {
    setLoadingSessions(true);
    try {
      const data = await authService.listSessions();
      setSessions(data || []);
    } catch (err) {
      addToast({
        type: "error",
        title: t("common.error") || "Error",
        message: t("auth.fetchSessionsFailed") || "Could not load active sessions.",
      });
    } finally {
      setLoadingSessions(false);
    }
  };

  // Password validation checks
  const passChecks = useMemo(() => {
    const lenValid = newPassword.length >= 12 && newPassword.length <= 128;
    const hasUpper = /[A-Z]/.test(newPassword);
    const hasLower = /[a-z]/.test(newPassword);
    const hasDigit = /[0-9]/.test(newPassword);
    const hasSymbol = /[^A-Za-z0-9]/.test(newPassword);
    const diversityValid = [hasUpper, hasLower, hasDigit, hasSymbol].filter(Boolean).length >= 3;
    const matches = newPassword.length > 0 && newPassword === confirmPassword;

    return {
      length: lenValid,
      diversity: diversityValid,
      match: matches,
      allValid: lenValid && diversityValid && matches,
    };
  }, [newPassword, confirmPassword]);

  const handleProfileSubmit = async (e) => {
    e.preventDefault();
    if (savingProfile) return;

    setSavingProfile(true);
    try {
      await updateProfile({
        full_name: fullName.trim(),
        preferred_language: preferredLang,
      });

      if (preferredLang !== language) {
        setLanguage(preferredLang);
      }

      addToast({
        type: "success",
        title: t("settings.profileUpdated") || "Profile Updated",
        message: t("settings.profileUpdatedMessage") || "Your citizen profile details have been saved.",
      });
    } catch (err) {
      addToast({
        type: "error",
        title: t("common.error") || "Error",
        message: err.message || t("settings.profileUpdateFailed") || "Failed to update profile.",
      });
    } finally {
      setSavingProfile(false);
    }
  };

  const handlePasswordSubmit = async (e) => {
    e.preventDefault();
    if (changingPass) return;

    if (!passChecks.allValid) {
      setPassError(t("auth.passwordPolicyError") || "Please satisfy all password security requirements.");
      return;
    }

    setPassError(null);
    setChangingPass(true);

    try {
      await changePassword(currentPassword, newPassword);
      setCurrentPassword("");
      setNewPassword("");
      setConfirmPassword("");

      addToast({
        type: "success",
        title: t("settings.passwordChanged") || "Password Changed",
        message:
          t("settings.passwordChangedMessage") ||
          "Password updated successfully. All other active sessions have been invalidated.",
      });

      fetchSessions();
    } catch (err) {
      setPassError(err.message || t("settings.passwordChangeFailed") || "Failed to change password.");
    } finally {
      setChangingPass(false);
    }
  };

  const handleRevokeSession = async (sessionId) => {
    setRevokingSessionId(sessionId);
    try {
      await authService.revokeSession(sessionId);
      addToast({
        type: "success",
        title: t("settings.sessionRevoked") || "Session Revoked",
        message: t("settings.sessionRevokedMessage") || "The remote session has been terminated.",
      });
      fetchSessions();
    } catch (err) {
      addToast({
        type: "error",
        title: t("common.error") || "Error",
        message: err.message || t("settings.sessionRevokeFailed") || "Could not revoke session.",
      });
    } finally {
      setRevokingSessionId(null);
    }
  };

  const handleLogoutOtherSessions = async () => {
    try {
      await logoutAll();
      addToast({
        type: "success",
        title: t("settings.loggedOutAll") || "Sessions Revoked",
        message: t("settings.loggedOutAllMessage") || "Logged out of all sessions. Please sign in again.",
      });
    } catch (err) {
      addToast({
        type: "error",
        title: t("common.error") || "Error",
        message: err.message || "Failed to revoke sessions.",
      });
    }
  };

  const handleDeleteAccountSubmit = async (e) => {
    e.preventDefault();
    if (deletingAccount) return;

    if (deleteConfirmText.trim().toUpperCase() !== "DELETE") {
      setDeleteError(t("settings.deleteConfirmMismatch") || "Type DELETE in uppercase to confirm.");
      return;
    }

    setDeleteError(null);
    setDeletingAccount(true);

    try {
      await deleteAccount(deletePassword);
      addToast({
        type: "info",
        title: t("settings.accountDeleted") || "Account Purged",
        message: t("settings.accountDeletedMessage") || "Your account and all data have been completely erased.",
      });
    } catch (err) {
      setDeleteError(err.message || t("settings.accountDeleteFailed") || "Failed to delete account.");
      setDeletingAccount(false);
    }
  };

  return (
    <div className="max-w-4xl mx-auto px-4 py-8">
      <div className="mb-8">
        <h1 className="text-2xl font-bold text-surface-900 dark:text-surface-100">
          {t("settings.pageTitle") || "Citizen Account & Preferences"}
        </h1>
        <p className="text-sm text-surface-600 dark:text-surface-400 mt-1">
          {t("settings.pageSubtitle") || "Manage personal identity, security credentials, active sessions, and local data."}
        </p>
      </div>

      {/* Tabs Header */}
      <div className="border-b border-surface-200 dark:border-surface-800 mb-6 flex gap-6">
        <button
          onClick={() => setActiveTab("profile")}
          className={`pb-3 text-sm font-semibold border-b-2 transition-colors ${
            activeTab === "profile"
              ? "border-primary-600 text-primary-600 dark:border-primary-400 dark:text-primary-400"
              : "border-transparent text-surface-600 hover:text-surface-900 dark:text-surface-400"
          }`}
        >
          {t("settings.tabProfile") || "Citizen Profile"}
        </button>
        <button
          onClick={() => setActiveTab("security")}
          className={`pb-3 text-sm font-semibold border-b-2 transition-colors ${
            activeTab === "security"
              ? "border-primary-600 text-primary-600 dark:border-primary-400 dark:text-primary-400"
              : "border-transparent text-surface-600 hover:text-surface-900 dark:text-surface-400"
          }`}
        >
          {t("settings.tabSecurity") || "Security & Sessions"}
        </button>
        <button
          onClick={() => setActiveTab("data")}
          className={`pb-3 text-sm font-semibold border-b-2 transition-colors ${
            activeTab === "data"
              ? "border-primary-600 text-primary-600 dark:border-primary-400 dark:text-primary-400"
              : "border-transparent text-surface-600 hover:text-surface-900 dark:text-surface-400"
          }`}
        >
          {t("settings.tabData") || "Data & Privacy"}
        </button>
      </div>

      {/* Tab 1: Profile */}
      {activeTab === "profile" && (
        <Card className="p-6 sm:p-8 space-y-6">
          <form onSubmit={handleProfileSubmit} className="space-y-5">
            <div className="flex items-center gap-4 pb-4 border-b border-surface-200 dark:border-surface-800">
              <div className="w-14 h-14 rounded-full bg-primary-100 dark:bg-primary-950/60 border border-primary-200 dark:border-primary-800 flex items-center justify-center text-xl font-bold text-primary-700 dark:text-primary-300">
                {user?.full_name ? user.full_name[0].toUpperCase() : "C"}
              </div>
              <div>
                <h3 className="text-lg font-semibold text-surface-900 dark:text-surface-100">
                  {user?.full_name || "Citizen"}
                </h3>
                <div className="flex items-center gap-2 mt-1">
                  <Badge variant={user?.role === "admin" ? "warning" : "default"}>
                    {user?.role === "admin" ? "Administrator" : "Citizen"}
                  </Badge>
                  <span className="text-xs text-surface-500">{user?.email}</span>
                </div>
              </div>
            </div>

            <div>
              <label htmlFor="settingsFullName" className="block text-sm font-medium text-surface-700 dark:text-surface-300 mb-1">
                {t("auth.fullNameLabel") || "Full Name"}
              </label>
              <Input
                id="settingsFullName"
                type="text"
                required
                value={fullName}
                onChange={(e) => setFullName(e.target.value)}
                className="max-w-md w-full"
              />
            </div>

            <div>
              <label htmlFor="settingsEmail" className="block text-sm font-medium text-surface-700 dark:text-surface-300 mb-1">
                {t("auth.emailLabel") || "Email Address"}
              </label>
              <Input
                id="settingsEmail"
                type="email"
                disabled
                value={user?.email || ""}
                className="max-w-md w-full bg-surface-100 dark:bg-surface-800 opacity-80 cursor-not-allowed"
              />
              <p className="text-xs text-surface-500 mt-1">
                {t("settings.emailLockedNote") || "Email address is cryptographically anchored to your identity and cannot be edited."}
              </p>
            </div>

            <div>
              <label htmlFor="settingsLang" className="block text-sm font-medium text-surface-700 dark:text-surface-300 mb-1">
                {t("auth.preferredLanguageLabel") || "Preferred Language"}
              </label>
              <Select
                id="settingsLang"
                value={preferredLang}
                onChange={(e) => setPreferredLang(e.target.value)}
                options={[
                  { value: "en", label: "English" },
                  { value: "ta", label: "தமிழ் (Tamil)" },
                ]}
                className="max-w-md w-full"
              />
            </div>

            <div className="pt-2">
              <Button type="submit" variant="primary" loading={savingProfile}>
                {savingProfile ? (t("common.saving") || "Saving...") : (t("common.saveChanges") || "Save Changes")}
              </Button>
            </div>
          </form>
        </Card>
      )}

      {/* Tab 2: Security & Sessions */}
      {activeTab === "security" && (
        <div className="space-y-8">
          {/* Change Password Card */}
          <Card className="p-6 sm:p-8">
            <h3 className="text-lg font-semibold text-surface-900 dark:text-surface-100 mb-1">
              {t("settings.changePasswordTitle") || "Change Password"}
            </h3>
            <p className="text-xs text-surface-500 mb-6">
              {t("settings.changePasswordDesc") || "Changing your password requires memory-hard Argon2id recomputation and revokes all other active sessions."}
            </p>

            {passError && (
              <div className="mb-5">
                <Alert variant="error">{passError}</Alert>
              </div>
            )}

            <form onSubmit={handlePasswordSubmit} className="space-y-4 max-w-md">
              <div>
                <label htmlFor="currentPass" className="block text-sm font-medium text-surface-700 dark:text-surface-300 mb-1">
                  {t("settings.currentPasswordLabel") || "Current Password"}
                </label>
                <Input
                  id="currentPass"
                  type="password"
                  required
                  value={currentPassword}
                  onChange={(e) => setCurrentPassword(e.target.value)}
                  className="w-full"
                />
              </div>

              <div>
                <label htmlFor="newPass" className="block text-sm font-medium text-surface-700 dark:text-surface-300 mb-1">
                  {t("auth.newPasswordLabel") || "New Password"}
                </label>
                <Input
                  id="newPass"
                  type="password"
                  required
                  value={newPassword}
                  onChange={(e) => setNewPassword(e.target.value)}
                  className="w-full"
                />
              </div>

              <div>
                <label htmlFor="confirmNewPass" className="block text-sm font-medium text-surface-700 dark:text-surface-300 mb-1">
                  {t("auth.confirmPasswordLabel") || "Confirm New Password"}
                </label>
                <Input
                  id="confirmNewPass"
                  type="password"
                  required
                  value={confirmPassword}
                  onChange={(e) => setConfirmPassword(e.target.value)}
                  className="w-full"
                />
              </div>

              <div className="p-3 bg-surface-100 dark:bg-surface-800/60 rounded-md border border-surface-200 dark:border-surface-700/60 text-xs space-y-1">
                <div className="flex items-center gap-2">
                  <span className={passChecks.length ? "text-success-600 font-bold" : "text-surface-400"}>
                    {passChecks.length ? "✓" : "○"}
                  </span>
                  <span>{t("auth.checkMinLength") || "At least 12 characters"}</span>
                </div>
                <div className="flex items-center gap-2">
                  <span className={passChecks.diversity ? "text-success-600 font-bold" : "text-surface-400"}>
                    {passChecks.diversity ? "✓" : "○"}
                  </span>
                  <span>{t("auth.checkDiversity") || "3 of 4 diversity categories"}</span>
                </div>
                <div className="flex items-center gap-2">
                  <span className={passChecks.match ? "text-success-600 font-bold" : "text-surface-400"}>
                    {passChecks.match ? "✓" : "○"}
                  </span>
                  <span>{t("auth.checkMatch") || "Passwords match"}</span>
                </div>
              </div>

              <div className="pt-2">
                <Button type="submit" variant="primary" loading={changingPass} disabled={!passChecks.allValid || !currentPassword}>
                  {changingPass ? (t("auth.saving") || "Saving...") : (t("settings.updatePasswordButton") || "Update Password")}
                </Button>
              </div>
            </form>
          </Card>

          {/* Active Sessions Card */}
          <Card className="p-6 sm:p-8">
            <div className="flex items-center justify-between mb-4">
              <div>
                <h3 className="text-lg font-semibold text-surface-900 dark:text-surface-100">
                  {t("settings.activeSessionsTitle") || "Active Browser Sessions"}
                </h3>
                <p className="text-xs text-surface-500">
                  {t("settings.activeSessionsDesc") || "Opaque HttpOnly tokens stored safely on your machine. Revoke any unfamiliar device."}
                </p>
              </div>
              <Button variant="secondary" size="sm" onClick={fetchSessions} loading={loadingSessions}>
                {t("common.refresh") || "Refresh"}
              </Button>
            </div>

            {loadingSessions ? (
              <div className="py-8 flex justify-center">
                <Spinner size="md" />
              </div>
            ) : sessions.length === 0 ? (
              <p className="text-sm text-surface-500 py-4">No active sessions reported.</p>
            ) : (
              <div className="overflow-x-auto">
                <table className="w-full text-left text-sm">
                  <thead className="border-b border-surface-200 dark:border-surface-800 text-xs text-surface-500 uppercase">
                    <tr>
                      <th className="py-3 px-2">Device / Client</th>
                      <th className="py-3 px-2">Network (Hashed)</th>
                      <th className="py-3 px-2">Last Active</th>
                      <th className="py-3 px-2 text-right">Action</th>
                    </tr>
                  </thead>
                  <tbody className="divide-y divide-surface-100 dark:divide-surface-800/60">
                    {sessions.map((sess) => (
                      <tr key={sess.id} className="hover:bg-surface-50/50 dark:hover:bg-surface-800/30">
                        <td className="py-3 px-2">
                          <div className="font-medium text-surface-900 dark:text-surface-100 flex items-center gap-2">
                            <span>{sess.user_agent_summary || "Browser Session"}</span>
                            {sess.is_current && (
                              <Badge variant="success">
                                {t("settings.currentDevice") || "This Device"}
                              </Badge>
                            )}
                          </div>
                          <div className="text-xs text-surface-400">Created: {new Date(sess.created_at).toLocaleString()}</div>
                        </td>
                        <td className="py-3 px-2 text-surface-600 dark:text-surface-400 font-mono text-xs">
                          {sess.ip_hash || "local"}
                        </td>
                        <td className="py-3 px-2 text-surface-600 dark:text-surface-400 text-xs">
                          {sess.last_seen_at ? new Date(sess.last_seen_at).toLocaleTimeString() : "Recent"}
                        </td>
                        <td className="py-3 px-2 text-right">
                          {sess.is_current ? (
                            <span className="text-xs text-surface-400 italic">Active</span>
                          ) : (
                            <Button
                              variant="danger"
                              size="sm"
                              loading={revokingSessionId === sess.id}
                              onClick={() => handleRevokeSession(sess.id)}
                            >
                              {t("settings.revokeButton") || "Revoke"}
                            </Button>
                          )}
                        </td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            )}
          </Card>
        </div>
      )}

      {/* Tab 3: Data & Privacy */}
      {activeTab === "data" && (
        <div className="space-y-6">
          <Card className="p-6 sm:p-8 space-y-4">
            <h3 className="text-lg font-semibold text-surface-900 dark:text-surface-100">
              {t("settings.exportDataTitle") || "Export Citizen Records"}
            </h3>
            <p className="text-sm text-surface-600 dark:text-surface-400">
              {t("settings.exportDataDesc") ||
                "Download a portable summary of your account metadata and personal identifiers stored locally in CivicLens."}
            </p>
            <div>
              <Button
                variant="secondary"
                onClick={() => {
                  const blob = new Blob([JSON.stringify(user, null, 2)], { type: "application/json" });
                  const url = URL.createObjectURL(blob);
                  const a = document.createElement("a");
                  a.href = url;
                  a.download = `civiclens-citizen-profile-${user?.id || "export"}.json`;
                  a.click();
                  URL.revokeObjectURL(url);
                }}
              >
                {t("settings.downloadExportButton") || "Download Identity Summary"}
              </Button>
            </div>
          </Card>

          <Card className="p-6 sm:p-8 border-danger-200 dark:border-danger-900/60 bg-danger-50/20 dark:bg-danger-950/10 space-y-4">
            <h3 className="text-lg font-bold text-danger-700 dark:text-danger-400">
              {t("settings.dangerZoneTitle") || "Danger Zone — Permanently Delete Account"}
            </h3>
            <p className="text-sm text-surface-600 dark:text-surface-400">
              {t("settings.dangerZoneDesc") ||
                "Irreversibly deletes your citizen account, all uploaded documents, extracted OCR text chunks, FAISS vector embeddings, grievance drafts, and chat history. This action cannot be undone."}
            </p>
            <div>
              <Button variant="danger" onClick={() => setDeleteModalOpen(true)}>
                {t("settings.deleteAccountButton") || "Permanently Delete Account"}
              </Button>
            </div>
          </Card>

          {/* Delete Account Confirmation Modal */}
          <Modal
            isOpen={deleteModalOpen}
            onClose={() => {
              if (!deletingAccount) {
                setDeleteModalOpen(false);
                setDeleteError(null);
                setDeletePassword("");
                setDeleteConfirmText("");
              }
            }}
            title={t("settings.deleteAccountModalTitle") || "Confirm Irreversible Account Deletion"}
          >
            <div className="space-y-4 pt-2">
              <Alert variant="error">
                {t("settings.deleteAccountWarning") ||
                  "WARNING: This will permanently wipe all your documents and chat history from this device. Enter your password and type DELETE to confirm."}
              </Alert>

              {deleteError && <Alert variant="error">{deleteError}</Alert>}

              <form onSubmit={handleDeleteAccountSubmit} className="space-y-4">
                <div>
                  <label htmlFor="delPass" className="block text-sm font-medium text-surface-700 dark:text-surface-300 mb-1">
                    {t("auth.passwordLabel") || "Your Password"}
                  </label>
                  <Input
                    id="delPass"
                    type="password"
                    required
                    value={deletePassword}
                    onChange={(e) => setDeletePassword(e.target.value)}
                    placeholder="••••••••••••"
                    disabled={deletingAccount}
                    className="w-full"
                  />
                </div>

                <div>
                  <label htmlFor="delConf" className="block text-sm font-medium text-surface-700 dark:text-surface-300 mb-1">
                    {t("settings.typeDeleteToConfirm") || "Type DELETE to confirm"}
                  </label>
                  <Input
                    id="delConf"
                    type="text"
                    required
                    value={deleteConfirmText}
                    onChange={(e) => setDeleteConfirmText(e.target.value)}
                    placeholder="DELETE"
                    disabled={deletingAccount}
                    className="w-full"
                  />
                </div>

                <div className="flex justify-end gap-3 pt-3">
                  <Button
                    type="button"
                    variant="secondary"
                    disabled={deletingAccount}
                    onClick={() => setDeleteModalOpen(false)}
                  >
                    {t("common.cancel") || "Cancel"}
                  </Button>
                  <Button
                    type="submit"
                    variant="danger"
                    loading={deletingAccount}
                    disabled={deleteConfirmText.trim().toUpperCase() !== "DELETE" || !deletePassword}
                  >
                    {deletingAccount ? "Deleting..." : (t("settings.confirmDeleteButton") || "Permanently Delete")}
                  </Button>
                </div>
              </form>
            </div>
          </Modal>
        </div>
      )}
    </div>
  );
}

export default Settings;
