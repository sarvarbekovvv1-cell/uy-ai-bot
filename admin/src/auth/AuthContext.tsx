import React, { createContext, useCallback, useContext, useEffect, useState } from "react";
import { adminApi, ApiError, setCsrfToken, setOnUnauthorizedHandler } from "../api/client";
import type { AuthStatus, StaffUser } from "../types";

export interface AuthContextType {
  status: AuthStatus;
  user: StaffUser | null;
  loading: boolean;
  notice: string | null;
  error: string | null;
  clearNotice: () => void;
  clearError: () => void;
  checkSession: () => Promise<void>;
  login: (u: string, p: string) => Promise<void>;
  logout: () => Promise<void>;
  updateUsername: (newUsername: string) => Promise<StaffUser>;
  updatePassword: (curr: string, newPass: string, confirmPass: string) => Promise<void>;
  hasPerm: (perm: string) => boolean;
  hasAnyPerm: (perms: string[]) => boolean;
}

const AuthContext = createContext<AuthContextType | undefined>(undefined);

export const AuthProvider: React.FC<{ children: React.ReactNode }> = ({ children }) => {
  const [status, setStatus] = useState<AuthStatus>("checking");
  const [user, setUser] = useState<StaffUser | null>(null);
  const [notice, setNotice] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);

  const checkSession = useCallback(async () => {
    setStatus("checking");
    setError(null);
    try {
      const userData = await adminApi.getMe();
      setUser(userData);
      if (userData.csrf_token) {
        setCsrfToken(userData.csrf_token);
      }
      setStatus("authenticated");
    } catch (err: unknown) {
      setUser(null);
      setCsrfToken(null);
      if (err instanceof ApiError && err.status === 401) {
        setStatus("unauthenticated");
      } else {
        setStatus("error");
        setError("Server bilan bog‘lanib bo‘lmadi. Qayta urinib ko‘ring.");
      }
    }
  }, []);

  useEffect(() => {
    let mounted = true;
    checkSession();

    // Register centralized 401 handler for active session expiration
    setOnUnauthorizedHandler((_status, message) => {
      if (mounted) {
        setUser(null);
        setCsrfToken(null);
        setStatus("expired");
        if (message) {
          setNotice(message);
        }
      }
    });

    return () => {
      mounted = false;
      setOnUnauthorizedHandler(null);
    };
  }, [checkSession]);

  const login = async (u: string, p: string) => {
    // 1. Submit credentials to establish server session and cookie
    await adminApi.login(u, p);

    // 2. Canonical verification with /auth/me
    const me = await adminApi.getMe();
    setUser(me);
    if (me.csrf_token) {
      setCsrfToken(me.csrf_token);
    }
    setStatus("authenticated");
    setNotice(null);
    setError(null);
  };

  const logout = async () => {
    try {
      await adminApi.logout();
    } finally {
      setUser(null);
      setCsrfToken(null);
      setStatus("unauthenticated");
      setNotice(null);
      setError(null);
    }
  };

  const updateUsername = async (newUsername: string): Promise<StaffUser> => {
    const updated = await adminApi.updateUsername(newUsername);
    setUser(updated);
    if (updated.csrf_token) {
      setCsrfToken(updated.csrf_token);
    }
    return updated;
  };

  const updatePassword = async (
    curr: string,
    newPass: string,
    confirmPass: string
  ): Promise<void> => {
    const res = await adminApi.updatePassword(curr, newPass, confirmPass);
    // Revocation resets server session; update client state to expired and redirect to login
    setUser(null);
    setCsrfToken(null);
    setStatus("unauthenticated");
    setNotice(res.message || "Parol muvaffaqiyatli o'zgartirildi. Yangi parol bilan qayta kiring.");
  };

  const clearNotice = () => setNotice(null);
  const clearError = () => setError(null);

  const hasPerm = (perm: string): boolean => {
    if (!user) return false;
    return user.permissions.includes(perm);
  };

  const hasAnyPerm = (perms: string[]): boolean => {
    if (!user) return false;
    return perms.some((p) => user.permissions.includes(p));
  };

  return (
    <AuthContext.Provider
      value={{
        status,
        user,
        loading: status === "checking",
        notice,
        error,
        clearNotice,
        clearError,
        checkSession,
        login,
        logout,
        updateUsername,
        updatePassword,
        hasPerm,
        hasAnyPerm,
      }}
    >
      {children}
    </AuthContext.Provider>
  );
};

export function useAuth(): AuthContextType {
  const ctx = useContext(AuthContext);
  if (!ctx) {
    throw new Error("useAuth must be used within an AuthProvider");
  }
  return ctx;
}
