import axios from "axios";
import type { ApiEnvelope } from "../types";

export const api = axios.create({
  baseURL: "/api"
});

api.interceptors.request.use((config) => {
  const token = localStorage.getItem("progoz_token");
  if (token) config.headers.Authorization = `Bearer ${token}`;
  return config;
});

export async function unwrap<T>(promise: Promise<{ data: ApiEnvelope<T> }>): Promise<T> {
  const response = await promise;
  if (!response.data.success) throw new Error(response.data.detail || response.data.error || "API hatasi");
  return response.data.data;
}

export const wsUrl = (path: string) => {
  const protocol = window.location.protocol === "https:" ? "wss" : "ws";
  return `${protocol}://${window.location.host}${path}`;
};

