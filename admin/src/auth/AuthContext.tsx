import React, { createContext, useContext, useEffect, useState } from "react";
import { adminApi, setCsrfToken } from "../api/client";
import type { StaffUser } from "../types";

interface AuthContextType {
  user: StaffUser | null;
  loading: boolean;
  login: (u: string, p: string) => Promise<void>;
  logout: () => Promise<void>;
  hasPerm: (perm: string) => boolean;
  hasAnyPerm: (perms: string[]) => boolean;
}

const AuthContext = createContext<AuthContextType | undefined>(undefined);

export const AuthProvider: React.FC<{ children: React.ReactNode }> = ({ children }) => {
  const [user, setUser] = useState<StaffUser | null>(null);
  const [loading, setLoading] = useState<boolean>(true);

  useEffect(() => {
    let mounted = true;
    adminApi
      .getMe()
      .then((userData) => {
        if (mounted) {
          setUser(userData);
          if (userData.csrf_token) {
            setCsrfToken(userData.csrf_token);
          }
        }
      })
      .catch(() => {
        if (mounted) setUser(null);
      })
      .finally(() => {
        if (mounted) setLoading(false);
      });

    return () => {
      mounted = false;
    };
  }, []);

  const login = async (u: string, p: string) => {
    const res = await adminApi.login(u, p);
    setUser(res.user);
    setCsrfToken(res.csrf_token);
  };

  const logout = async () => {
    try {
      await adminApi.logout();
    } finally {
      setUser(null);
      setCsrfToken(null);
    }
  };

  const hasPerm = (perm: string): boolean => {
    if (!user) return false;
    return user.permissions.includes(perm);
  };

  const hasAnyPerm = (perms: string[]): boolean => {
    if (!user) return false;
    return perms.some((p) => user.permissions.includes(p));
  };

  return (
    <AuthContext.Provider value={{ user, loading, login, logout, hasPerm, hasAnyPerm }}>
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
