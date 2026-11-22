import React from "react";
import { BrowserRouter, Routes, Route } from "react-router-dom";
import { LanguageProvider } from "./context/LanguageContext";
import { ToastProvider } from "./context/ToastContext";
import { AuthProvider } from "./context/AuthContext";

// Route Guards
import { ProtectedRoute } from "./components/auth/ProtectedRoute";

// Layouts
import { PublicLayout } from "./layouts/PublicLayout";
import { AppLayout } from "./layouts/AppLayout";

// Pages
import { Landing } from "./pages/Landing";
import { Dashboard } from "./pages/Dashboard";
import { Assistant } from "./pages/Assistant";
import { Documents } from "./pages/Documents";
import { Compare } from "./pages/Compare";
import { Verify } from "./pages/Verify";
import { Services } from "./pages/Services";
import { Grievance } from "./pages/Grievance";
import { DesignSystem } from "./pages/DesignSystem";
import { NotFound } from "./pages/NotFound";

// Auth Pages
import { Login } from "./pages/Login";
import { Signup } from "./pages/Signup";
import { ForgotPassword } from "./pages/ForgotPassword";
import { ResetPassword } from "./pages/ResetPassword";
import { Terms } from "./pages/Terms";
import { Privacy } from "./pages/Privacy";
import { Settings } from "./pages/Settings";

export default function App() {
  return (
    <LanguageProvider>
      <ToastProvider>
        <AuthProvider>
          <BrowserRouter>
            <Routes>
              {/* Standalone Auth & Policy Pages */}
              <Route path="/login" element={<Login />} />
              <Route path="/signup" element={<Signup />} />
              <Route path="/forgot-password" element={<ForgotPassword />} />
              <Route path="/reset-password" element={<ResetPassword />} />
              <Route path="/terms" element={<Terms />} />
              <Route path="/privacy" element={<Privacy />} />

              {/* Public Marketing Layout Routes */}
              <Route element={<PublicLayout />}>
                <Route path="/" element={<Landing />} />
                <Route path="*" element={<NotFound />} />
              </Route>

              {/* Protected App Layout Routes */}
              <Route
                element={
                  <ProtectedRoute>
                    <AppLayout />
                  </ProtectedRoute>
                }
              >
                <Route path="/dashboard" element={<Dashboard />} />
                <Route path="/assistant" element={<Assistant />} />
                <Route path="/documents" element={<Documents />} />
                <Route path="/compare" element={<Compare />} />
                <Route path="/verify" element={<Verify />} />
                <Route path="/services" element={<Services />} />
                <Route path="/grievance" element={<Grievance />} />
                <Route path="/settings" element={<Settings />} />
                <Route path="/design-system" element={<DesignSystem />} />
              </Route>
            </Routes>
          </BrowserRouter>
        </AuthProvider>
      </ToastProvider>
    </LanguageProvider>
  );
}
