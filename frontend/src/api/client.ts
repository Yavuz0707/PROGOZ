import axios from "axios";
import type { ApiEnvelope } from "../types";

export const API_BASE_URL = (import.meta.env.VITE_API_BASE_URL || "http://127.0.0.1:8002").replace(/\/$/, "");

if (import.meta.env.DEV) {
  console.log("API Base URL:", API_BASE_URL);
}

export const api = axios.create({
  baseURL: `${API_BASE_URL}/api`
});

api.interceptors.request.use((config) => {
  const token = localStorage.getItem("progoz_token");
  if (token) config.headers.Authorization = `Bearer ${token}`;
  if (import.meta.env.DEV) {
    console.debug("[api:request]", config.method?.toUpperCase(), `${config.baseURL || ""}${config.url || ""}`);
  }
  return config;
});

api.interceptors.response.use(
  (response) => {
    if (import.meta.env.DEV) {
      console.debug("[api:response]", response.status, response.config.url, response.data);
    }
    return response;
  },
  (error) => {
    if (import.meta.env.DEV) {
      console.error("[api:error]", error.response?.status, error.config?.url, error.response?.data || error.message);
    }
    return Promise.reject(error);
  }
);

export async function unwrap<T>(promise: Promise<{ data: ApiEnvelope<T> }>): Promise<T> {
  try {
    const response = await promise;
    if (!response.data.success) throw new Error(response.data.detail || response.data.error || "API hatasi");
    return response.data.data;
  } catch (error: any) {
    const status = error?.response?.status;
    const payload = error?.response?.data;
    if (status === 401) {
      localStorage.removeItem("progoz_token");
      throw new Error("Yetki hatasi: Lutfen tekrar giris yapin.");
    }
    if (status === 422) throw new Error(`Form verisi gecersiz: ${payload?.detail || payload?.error || "Alanlari kontrol edin."}`);
    if (payload?.detail || payload?.error || payload?.message) throw new Error(payload.detail || payload.error || payload.message);
    if (error?.request && !error.response) throw new Error("Backend'e baglanilamadi.");
    throw new Error(error?.message || "API hatasi");
  }
}

export const wsUrl = (path: string) => {
  const url = new URL(API_BASE_URL);
  url.protocol = url.protocol === "https:" ? "wss:" : "ws:";
  return `${url.origin}${path}`;
};

export function assetUrl(path?: string | null) {
  if (!path) return undefined;
  if (/^https?:\/\//i.test(path)) return path;
  return `${API_BASE_URL}${path.startsWith("/") ? path : `/${path}`}`;
}
