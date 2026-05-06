import { createContext, useContext, useEffect, useState } from "react";
import api from "./api";

const AuthContext = createContext(null);
const TOKEN_KEY = "anutech.token";
const USER_KEY = "anutech.user";

function decodeJwtPayload(token) {
  try {
    const [, payload] = token.split(".");
    const json = atob(payload.replace(/-/g, "+").replace(/_/g, "/"));
    return JSON.parse(json);
  } catch {
    return null;
  }
}

function isExpired(payload) {
  return !payload?.exp || payload.exp * 1000 < Date.now();
}

export function AuthProvider({ children }) {
  const [user, setUser] = useState(() => {
    const token = localStorage.getItem(TOKEN_KEY);
    if (!token) return null;
    const payload = decodeJwtPayload(token);
    if (!payload || isExpired(payload)) {
      localStorage.removeItem(TOKEN_KEY);
      localStorage.removeItem(USER_KEY);
      return null;
    }
    const stored = localStorage.getItem(USER_KEY);
    return stored ? JSON.parse(stored) : { user_id: payload.sub, role: payload.role, tenant_schema: payload.tenant_schema };
  });

  const login = async ({ slug, email, password }) => {
    const { data } = await api.post("/auth/login", { slug, email, password });
    localStorage.setItem(TOKEN_KEY, data.access_token);
    const payload = decodeJwtPayload(data.access_token) || {};
    const u = {
      user_id: payload.sub,
      role: data.role,
      tenant_schema: data.tenant_slug,
    };
    localStorage.setItem(USER_KEY, JSON.stringify(u));
    setUser(u);
    return u;
  };

  const register = async (payload) => {
    const { data } = await api.post("/auth/register", payload);
    localStorage.setItem(TOKEN_KEY, data.access_token);
    const u = {
      user_id: data.admin_user_id,
      role: "admin",
      tenant_schema: data.schema_name,
    };
    localStorage.setItem(USER_KEY, JSON.stringify(u));
    setUser(u);
    return u;
  };

  const logout = () => {
    localStorage.removeItem(TOKEN_KEY);
    localStorage.removeItem(USER_KEY);
    setUser(null);
  };

  return (
    <AuthContext.Provider value={{ user, login, register, logout }}>
      {children}
    </AuthContext.Provider>
  );
}

export function useAuth() {
  const ctx = useContext(AuthContext);
  if (!ctx) throw new Error("useAuth must be inside <AuthProvider>");
  return ctx;
}
