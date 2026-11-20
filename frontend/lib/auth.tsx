"use client";
import { createContext, useContext, useState, useEffect, useCallback, ReactNode } from "react";
import { api, setAccessToken, ApiError } from "./api";

interface User {
  id: string;
  email: string;
  profile_complete: boolean;
  display_name?: string;
  credits_remaining?: number;
  credits_reset_date?: string;
}

interface AuthContextValue {
  user: User | null;
  loading: boolean;
  login: (email: string, password: string) => Promise<void>;
  signup: (email: string, password: string) => Promise<void>;
  logout: () => Promise<void>;
  refreshUser: () => Promise<void>;
}

const AuthContext = createContext<AuthContextValue>({
  user: null,
  loading: true,
  login: async () => {},
  signup: async () => {},
  logout: async () => {},
  refreshUser: async () => {},
});

export function useAuth() { return useContext(AuthContext); }

export function AuthProvider({ children }: { children: ReactNode }) {
  const [user, setUser] = useState<User | null>(null);
  const [loading, setLoading] = useState(true);

  const refreshUser = useCallback(async () => {
    try {
      const me = await api.get<User>("/me");
      setUser(me);
    } catch {}
  }, []);

  useEffect(() => {
    (async () => {
      const ok = await api.refresh();
      if (ok) {
        try {
          const me = await api.get<User>("/me");
          setUser(me);
        } catch {}
      }
      setLoading(false);
    })();
  }, []);

  const login = useCallback(async (email: string, password: string) => {
    const data = await api.post<{ access_token: string; user: User }>("/auth/login", { email, password });
    setAccessToken(data.access_token);
    setUser(data.user);
  }, []);

  const signup = useCallback(async (email: string, password: string) => {
    const data = await api.post<{ access_token: string; user: User }>("/auth/signup", { email, password });
    setAccessToken(data.access_token);
    setUser(data.user);
  }, []);

  const logout = useCallback(async () => {
    try { await api.post("/auth/logout"); } catch {}
    setAccessToken(null);
    setUser(null);
  }, []);

  return (
    <AuthContext.Provider value={{ user, loading, login, signup, logout, refreshUser }}>
      {children}
    </AuthContext.Provider>
  );
}
