import React, { useState } from "react";
import { Outlet, NavLink, Link, useNavigate } from "react-router-dom";
import {
  LayoutDashboard,
  Bot,
  FileText,
  GitCompare,
  ShieldCheck,
  Compass,
  LifeBuoy,
  Palette,
  Settings as SettingsIcon,
  LogOut,
  User,
  Menu,
  X,
  ChevronRight,
  Database,
} from "lucide-react";
import { Logo } from "../components/ui/Logo";
import { LanguageSwitcher } from "../components/ui/LanguageSwitcher";
import { BackendStatus } from "../components/ui/BackendStatus";
import { Badge } from "../components/ui/Badge";
import { Button } from "../components/ui/Button";
import { useLanguage } from "../hooks/useLanguage";
import { useBackendStatus } from "../hooks/useBackendStatus";
import useAuth from "../hooks/useAuth";
import { useToast } from "../hooks/useToast";

export function AppLayout() {
  const { t } = useLanguage();
  const { user, logout, isAdmin, claimLegacyData } = useAuth();
  const { status, info, retry } = useBackendStatus();
  const { addToast } = useToast();
  const navigate = useNavigate();
  const [sidebarOpen, setSidebarOpen] = useState(false);
  const [userMenuOpen, setUserMenuOpen] = useState(false);
  const [claiming, setClaiming] = useState(false);

  const closeSidebar = () => setSidebarOpen(false);

  const handleLogout = async () => {
    try {
      await logout();
      addToast({
        type: "info",
        title: t("auth.signedOut") || "Signed Out",
        message: t("auth.signedOutMessage") || "Your session has been securely closed.",
      });
      navigate("/login");
    } catch {
      navigate("/login");
    }
  };

  const handleClaimLocal = async () => {
    setClaiming(true);
    try {
      const res = await claimLegacyData();
      addToast({
        type: "success",
        title: t("settings.claimSuccess") || "Local Data Claimed",
        message: `${res.message} (${res.claimed_documents_count || 0} docs, ${res.claimed_conversations_count || 0} chats, ${res.claimed_grievances_count || 0} grievances).`,
      });
    } catch (err) {
      addToast({
        type: "error",
        title: t("common.error") || "Error",
        message: err.message || "Failed to claim local data.",
      });
    } finally {
      setClaiming(false);
    }
  };

  const navItems = [
    { to: "/dashboard", label: t("nav.dashboard"), icon: LayoutDashboard },
    { to: "/assistant", label: t("nav.assistant"), icon: Bot },
    { to: "/documents", label: t("nav.documents"), icon: FileText },
    { to: "/compare", label: t("nav.compare"), icon: GitCompare },
    { to: "/verify", label: t("nav.verify"), icon: ShieldCheck },
    { to: "/services", label: t("nav.services"), icon: Compass },
    { to: "/grievance", label: t("nav.grievance"), icon: LifeBuoy },
    { to: "/settings", label: t("settings.navSettings") || "Settings", icon: SettingsIcon },
  ];

  return (
    <div className="min-h-screen flex bg-slate-50 text-slate-900 overflow-x-hidden">
      {/* Mobile Drawer Backdrop */}
      {sidebarOpen && (
        <div
          className="fixed inset-0 z-40 bg-slate-900/50 backdrop-blur-xs lg:hidden transition-opacity"
          onClick={closeSidebar}
          aria-hidden="true"
        />
      )}

      {/* Sidebar Navigation */}
      <aside
        className={`fixed inset-y-0 left-0 z-50 w-64 bg-white border-r border-slate-200 flex flex-col transition-transform duration-200 ease-in-out lg:static lg:translate-x-0 ${
          sidebarOpen ? "translate-x-0" : "-translate-x-full"
        }`}
      >
        {/* Sidebar Brand Header */}
        <div className="h-16 px-5 border-b border-slate-100 flex items-center justify-between">
          <Logo size="sm" to="/dashboard" />
          <button
            type="button"
            onClick={closeSidebar}
            className="p-1 rounded-lg text-slate-400 hover:text-slate-600 lg:hidden focus-visible:ring-2 focus-visible:ring-blue-600"
            aria-label="Close sidebar"
          >
            <X className="w-5 h-5" />
          </button>
        </div>

        {/* Navigation List */}
        <nav className="flex-1 px-3 py-4 space-y-1 overflow-y-auto" aria-label="Sidebar Navigation">
          <div className="px-3 pb-2 text-[11px] font-semibold tracking-wider text-slate-400 uppercase">
            Civic Intelligence
          </div>
          {navItems.map((item) => {
            const Icon = item.icon;
            return (
              <NavLink
                key={item.to}
                to={item.to}
                onClick={closeSidebar}
                className={({ isActive }) =>
                  `flex items-center gap-3 px-3 py-2.5 rounded-xl text-sm font-medium transition-all group focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-blue-600 ${
                    isActive
                      ? "bg-blue-50 text-blue-700 font-semibold shadow-2xs"
                      : "text-slate-600 hover:bg-slate-100 hover:text-slate-900"
                  }`
                }
              >
                {({ isActive }) => (
                  <>
                    <Icon
                      className={`w-5 h-5 flex-shrink-0 transition-colors ${
                        isActive ? "text-blue-700" : "text-slate-400 group-hover:text-slate-600"
                      }`}
                    />
                    <span className="truncate">{item.label}</span>
                    {isActive && (
                      <ChevronRight className="w-4 h-4 ml-auto text-blue-600 flex-shrink-0" />
                    )}
                  </>
                )}
              </NavLink>
            );
          })}

          {/* Dev Showcase link in sidebar */}
          <div className="pt-4 mt-4 border-t border-slate-100">
            <div className="px-3 pb-2 text-[11px] font-semibold tracking-wider text-slate-400 uppercase">
              Developer Tools
            </div>
            <NavLink
              to="/design-system"
              onClick={closeSidebar}
              className={({ isActive }) =>
                `flex items-center gap-3 px-3 py-2 rounded-xl text-xs font-medium transition-all focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-blue-600 ${
                  isActive
                    ? "bg-blue-50 text-blue-700 font-semibold"
                    : "text-slate-500 hover:bg-slate-100 hover:text-slate-800"
                }`
              }
            >
              <Palette className="w-4 h-4 flex-shrink-0 text-slate-400" />
              <span>{t("nav.designSystem")}</span>
            </NavLink>
          </div>
        </nav>

        {/* Sidebar Citizen Profile Footer */}
        <div className="p-3 border-t border-slate-100 bg-slate-50/70 m-2 rounded-xl">
          <div className="flex items-center justify-between mb-1.5">
            <div className="flex items-center gap-2 min-w-0">
              <div className="w-7 h-7 rounded-full bg-blue-100 text-blue-700 font-bold flex items-center justify-center text-xs flex-shrink-0">
                {user?.full_name ? user.full_name[0].toUpperCase() : "C"}
              </div>
              <div className="truncate">
                <p className="text-xs font-semibold text-slate-800 truncate">
                  {user?.full_name || "Citizen"}
                </p>
                <p className="text-[10px] text-slate-400 truncate">{user?.email}</p>
              </div>
            </div>
            <Badge variant={user?.role === "admin" ? "warning" : "default"} size="sm">
              {user?.role === "admin" ? "Admin" : "Citizen"}
            </Badge>
          </div>

          <div className="flex items-center justify-between pt-1 border-t border-slate-200/50 text-[11px]">
            <Link
              to="/settings"
              onClick={closeSidebar}
              className="text-slate-600 hover:text-blue-700 font-medium flex items-center gap-1"
            >
              <SettingsIcon className="w-3.5 h-3.5" />
              <span>{t("settings.navSettings") || "Settings"}</span>
            </Link>
            <button
              onClick={handleLogout}
              className="text-red-600 hover:text-red-700 font-medium flex items-center gap-1"
            >
              <LogOut className="w-3.5 h-3.5" />
              <span>{t("auth.signOut") || "Sign Out"}</span>
            </button>
          </div>
        </div>
      </aside>

      {/* Main Content Column */}
      <div className="flex-1 flex flex-col min-w-0">
        {/* Top Header Bar */}
        <header className="sticky top-0 z-30 h-16 bg-white/90 backdrop-blur-md border-b border-slate-200 px-4 sm:px-6 lg:px-8 flex items-center justify-between gap-4">
          <div className="flex items-center gap-3">
            <button
              type="button"
              onClick={() => setSidebarOpen(true)}
              className="p-2 -ml-2 rounded-lg text-slate-600 hover:text-slate-900 hover:bg-slate-100 lg:hidden focus-visible:ring-2 focus-visible:ring-blue-600"
              aria-label="Open sidebar drawer"
              aria-expanded={sidebarOpen}
            >
              <Menu className="w-5 h-5" />
            </button>
            <Link
              to="/"
              className="text-xs font-semibold text-slate-500 hover:text-blue-700 transition-colors hidden sm:inline-block"
            >
              CivicLens
            </Link>
          </div>

          <div className="flex items-center gap-3">
            {isAdmin && (
              <Button
                variant="secondary"
                size="sm"
                onClick={handleClaimLocal}
                loading={claiming}
                className="hidden md:inline-flex items-center gap-1.5 text-xs text-amber-700 border-amber-300 bg-amber-50 hover:bg-amber-100"
              >
                <Database className="w-3.5 h-3.5" />
                <span>{t("settings.claimLocalData") || "Claim Local Data"}</span>
              </Button>
            )}

            <BackendStatus
              status={status}
              version={info?.version}
              onRetry={retry}
              showRetry={true}
            />

            <LanguageSwitcher />

            {/* User Avatar Menu */}
            <div className="relative">
              <button
                type="button"
                onClick={() => setUserMenuOpen((prev) => !prev)}
                className="flex items-center gap-2 p-1 rounded-full hover:ring-2 hover:ring-blue-500/30 transition-all focus:outline-none"
                aria-expanded={userMenuOpen}
              >
                <div className="w-8 h-8 rounded-full bg-blue-600 text-white font-bold flex items-center justify-center text-xs shadow-xs">
                  {user?.full_name ? user.full_name[0].toUpperCase() : "C"}
                </div>
              </button>

              {userMenuOpen && (
                <>
                  <div
                    className="fixed inset-0 z-30"
                    onClick={() => setUserMenuOpen(false)}
                    aria-hidden="true"
                  />
                  <div className="absolute right-0 mt-2 w-56 bg-white rounded-xl shadow-lg border border-slate-100 py-2 z-40 text-sm animate-in fade-in zoom-in-95">
                    <div className="px-4 py-2 border-b border-slate-100">
                      <p className="font-semibold text-slate-800 truncate">{user?.full_name}</p>
                      <p className="text-xs text-slate-400 truncate">{user?.email}</p>
                      <div className="mt-1">
                        <Badge variant={user?.role === "admin" ? "warning" : "default"} size="sm">
                          {user?.role === "admin" ? "Admin" : "Citizen"}
                        </Badge>
                      </div>
                    </div>

                    <Link
                      to="/settings"
                      onClick={() => setUserMenuOpen(false)}
                      className="flex items-center gap-2 px-4 py-2 text-slate-700 hover:bg-slate-50 transition-colors"
                    >
                      <SettingsIcon className="w-4 h-4 text-slate-400" />
                      <span>{t("settings.navSettings") || "Account Settings"}</span>
                    </Link>

                    <button
                      onClick={() => {
                        setUserMenuOpen(false);
                        handleLogout();
                      }}
                      className="w-full flex items-center gap-2 px-4 py-2 text-red-600 hover:bg-red-50 transition-colors text-left"
                    >
                      <LogOut className="w-4 h-4 text-red-500" />
                      <span>{t("auth.signOut") || "Sign Out"}</span>
                    </button>
                  </div>
                </>
              )}
            </div>
          </div>
        </header>

        {/* Page Content Viewport */}
        <main className="flex-1 p-4 sm:p-6 lg:p-8 max-w-7xl w-full mx-auto">
          <Outlet />
        </main>
      </div>
    </div>
  );
}
