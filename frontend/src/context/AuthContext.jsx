import React, { useState, useEffect, useCallback } from "react";
import { AuthContext } from "./AuthContextInstance";
import authService from "../services/authService";
import apiClient from "../services/apiClient";

export function AuthProvider({ children }) {
  const [user, setUser] = useState(null);
  const [status, setStatus] = useState("loading"); // 'loading' | 'authenticated' | 'anonymous'
  const [capabilities, setCapabilities] = useState(null);
  const [csrfToken, setCsrfTokenState] = useState(null);

  const handleUnauthorized = useCallback(() => {
    setUser(null);
    setStatus("anonymous");
    setCsrfTokenState(null);
    apiClient.setCsrfToken(null);
  }, []);

  const refreshUser = useCallback(async () => {
    try {
      const data = await authService.getMe();
      if (data && data.user) {
        setUser(data.user);
        setStatus("authenticated");
        if (data.csrf_token) {
          setCsrfTokenState(data.csrf_token);
          apiClient.setCsrfToken(data.csrf_token);
        }
        return data.user;
      }
      handleUnauthorized();
      return null;
    } catch (err) {
      handleUnauthorized();
      return null;
    }
  }, [handleUnauthorized]);

  useEffect(() => {
    // Register global 401 interceptor listener
    const unsubscribe = apiClient.onUnauthorized(handleUnauthorized);

    // Initial session bootstrap
    let mounted = true;
    async function initAuth() {
      try {
        const [capsData, meData] = await Promise.allSettled([
          authService.getCapabilities(),
          authService.getMe(),
        ]);

        if (!mounted) return;

        if (capsData.status === "fulfilled") {
          setCapabilities(capsData.value);
        }

        if (meData.status === "fulfilled" && meData.value && meData.value.user) {
          setUser(meData.value.user);
          setStatus("authenticated");
          if (meData.value.csrf_token) {
            setCsrfTokenState(meData.value.csrf_token);
            apiClient.setCsrfToken(meData.value.csrf_token);
          }
        } else {
          setUser(null);
          setStatus("anonymous");
        }
      } catch (err) {
        if (mounted) {
          setUser(null);
          setStatus("anonymous");
        }
      }
    }

    initAuth();

    return () => {
      mounted = false;
      unsubscribe();
    };
  }, [handleUnauthorized]);

  const login = async (email, password, rememberMe = false) => {
    const data = await authService.login({
      email,
      password,
      remember_me: rememberMe,
    });
    if (data && data.user) {
      setUser(data.user);
      setStatus("authenticated");
      if (data.csrf_token) {
        setCsrfTokenState(data.csrf_token);
        apiClient.setCsrfToken(data.csrf_token);
      }
    }
    return data;
  };

  const register = async (payload) => {
    const data = await authService.register(payload);
    if (data && data.user) {
      setUser(data.user);
      setStatus("authenticated");
      if (data.csrf_token) {
        setCsrfTokenState(data.csrf_token);
        apiClient.setCsrfToken(data.csrf_token);
      }
    }
    return data;
  };

  const logout = async () => {
    try {
      await authService.logout();
    } catch {
      // Ignore network errors on logout
    } finally {
      handleUnauthorized();
    }
  };

  const logoutAll = async () => {
    try {
      await authService.logoutAll();
    } catch {
      // Ignore network errors
    } finally {
      handleUnauthorized();
    }
  };

  const updateProfile = async (data) => {
    const updatedUser = await authService.updateProfile(data);
    setUser(updatedUser);
    return updatedUser;
  };

  const changePassword = async (currentPassword, newPassword) => {
    return authService.changePassword(currentPassword, newPassword);
  };

  const deleteAccount = async (password) => {
    const res = await authService.deleteAccount(password);
    handleUnauthorized();
    return res;
  };

  const claimLegacyData = async () => {
    return authService.claimLegacyData();
  };

  const value = {
    user,
    status,
    capabilities,
    csrfToken,
    isAuthenticated: status === "authenticated",
    isLoading: status === "loading",
    isAdmin: user?.role === "admin",
    login,
    register,
    logout,
    logoutAll,
    updateProfile,
    changePassword,
    deleteAccount,
    claimLegacyData,
    refreshUser,
  };

  return <AuthContext.Provider value={value}>{children}</AuthContext.Provider>;
}

export default AuthProvider;
