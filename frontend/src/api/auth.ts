import { apiClient } from "./client";

export interface User {
  id: number;
  name: string | null;
  email: string;
  created_at: string | null;
}

export interface AuthResponse {
  user: User;
  access_token: string;
}

export interface MeResponse {
  user: User;
}

export async function registerApi(data: {
  name?: string;
  email: string;
  password: string;
}): Promise<AuthResponse> {
  const res = await apiClient.post<AuthResponse>("/auth/register", data);
  return res.data;
}

export async function loginApi(data: {
  email: string;
  password: string;
}): Promise<AuthResponse> {
  const res = await apiClient.post<AuthResponse>("/auth/login", data);
  return res.data;
}

export async function getMeApi(): Promise<User> {
  const res = await apiClient.get<MeResponse>("/auth/me");
  return res.data.user;
}
