import React, { createContext, useContext, useEffect, useState } from "react";
import { User, getMeApi, loginApi, registerApi } from "../api/auth";

interface AuthContextType {
  user: User | null;
  token: string | null;
  isLoading: boolean;
  isAuthenticated: boolean;
  login: (email: string, password: string) => Promise<void>;
  register: (name: string | undefined, email: string, password: string) => Promise<void>;
  logout: () => void;
}

const AuthContext = createContext<AuthContextType | undefined>(undefined);

export function AuthProvider({ children }: { children: React.ReactNode }) {
  const [user, setUser] = useState<User | null>(() => {
    const saved = localStorage.getItem("docchat_user");
    return saved ? JSON.parse(saved) : null;
  });
  const [token, setToken] = useState<string | null>(() => {
    return localStorage.getItem("docchat_token");
  });
  const [isLoading, setIsLoading] = useState<boolean>(true);

  // Validate token against backend /auth/me on initial load
  useEffect(() => {
    async function verifySession() {
      if (!token) {
        setIsLoading(false);
        return;
      }
      try {
        const currentUser = await getMeApi();
        setUser(currentUser);
        localStorage.setItem("docchat_user", JSON.stringify(currentUser));
      } catch {
        setUser(null);
        setToken(null);
        localStorage.removeItem("docchat_token");
        localStorage.removeItem("docchat_user");
      } finally {
        setIsLoading(false);
      }
    }

    verifySession();
  }, [token]);

  const login = async (email: string, password: string) => {
    const data = await loginApi({ email, password });
    setToken(data.access_token);
    setUser(data.user);
    localStorage.setItem("docchat_token", data.access_token);
    localStorage.setItem("docchat_user", JSON.stringify(data.user));
  };

  const register = async (name: string | undefined, email: string, password: string) => {
    const data = await registerApi({ name, email, password });
    setToken(data.access_token);
    setUser(data.user);
    localStorage.setItem("docchat_token", data.access_token);
    localStorage.setItem("docchat_user", JSON.stringify(data.user));
  };

  const logout = () => {
    setUser(null);
    setToken(null);
    localStorage.removeItem("docchat_token");
    localStorage.removeItem("docchat_user");
  };

  return (
    <AuthContext.Provider
      value={{
        user,
        token,
        isLoading,
        isAuthenticated: !!user && !!token,
        login,
        register,
        logout,
      }}
    >
      {children}
    </AuthContext.Provider>
  );
}

export function useAuth() {
  const context = useContext(AuthContext);
  if (!context) {
    throw new Error("useAuth must be used within an AuthProvider");
  }
  return context;
}
