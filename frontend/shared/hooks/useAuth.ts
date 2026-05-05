/**
 * useAuth — 전역 인증 상태 훅
 * Next.js App Router + React Context 기반
 */
"use client";
import { createContext, useContext, useEffect, useState, useCallback } from "react";
import { authApi, tokenStore, type User } from "../lib/api-client";

interface AuthState {
  user:             User | null;
  isLoading:        boolean;
  isLoggedIn:       boolean;
  isAuthenticated:  boolean;
  login:            (tokens: { access_token: string; refresh_token: string }) => Promise<void>;
  loginWithToken:   (accessToken: string, refreshToken: string) => Promise<void>;
  logout:           () => void;
  refresh:          () => Promise<void>;
}

const AuthContext = createContext<AuthState | null>(null);

export function AuthProvider({ children }: { children: React.ReactNode }) {
  const [user,      setUser]      = useState<User | null>(null);
  const [isLoading, setIsLoading] = useState(true);

  const refresh = useCallback(async () => {
    try {
      const me = await authApi.me();
      setUser(me);
    } catch {
      setUser(null);
    } finally {
      setIsLoading(false);
    }
  }, []);

  useEffect(() => {
    if (tokenStore.get()) refresh();
    else setIsLoading(false);
  }, [refresh]);

  const login = useCallback(async (tokens: { access_token: string; refresh_token: string }) => {
    tokenStore.set(tokens.access_token, tokens.refresh_token);
    await refresh();
  }, [refresh]);

  const loginWithToken = useCallback(async (accessToken: string, refreshToken: string) => {
    return login({ access_token: accessToken, refresh_token: refreshToken });
  }, [login]);

  const logout = useCallback(() => {
    authApi.logout();
    setUser(null);
  }, []);

  return (
    <AuthContext.Provider value={{ user, isLoading, isLoggedIn: !!user, isAuthenticated: !!user, login, loginWithToken, logout, refresh }}>
      {children}
    </AuthContext.Provider>
  );
}

export function useAuth() {
  const ctx = useContext(AuthContext);
  if (!ctx) throw new Error("useAuth must be used within AuthProvider");
  return ctx;
}
