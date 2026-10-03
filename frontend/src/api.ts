import type { Category, ChatResponse, Customer, Health, Order, Product, Scenario } from "./types";

export const API_URL: string = (import.meta.env.VITE_API_URL as string | undefined)?.replace(/\/$/, "") || "http://localhost:8000";

export class ApiError extends Error {
  status?: number;
  constructor(message: string, status?: number) {
    super(message);
    this.status = status;
  }
}

async function request<T>(path: string, init?: RequestInit & { timeoutMs?: number }): Promise<T> {
  const ctrl = new AbortController();
  const timer = setTimeout(() => ctrl.abort(), init?.timeoutMs ?? 30000);
  try {
    const res = await fetch(`${API_URL}${path}`, {
      ...init,
      signal: ctrl.signal,
      headers: { "Content-Type": "application/json", ...(init?.headers ?? {}) },
    });
    if (!res.ok) {
      const detail = await res.text().catch(() => "");
      throw new ApiError(`${res.status} ${res.statusText}${detail ? `: ${detail.slice(0, 160)}` : ""}`, res.status);
    }
    return (await res.json()) as T;
  } catch (e) {
    if (e instanceof ApiError) throw e;
    if ((e as Error).name === "AbortError") throw new ApiError("Request timed out");
    throw new ApiError("Backend unreachable");
  } finally {
    clearTimeout(timer);
  }
}

export const api = {
  health: () => request<Health>("/health", { timeoutMs: 5000 }),
  customers: (q: string, limit = 20) =>
    request<Customer[]>(`/customers?q=${encodeURIComponent(q)}&limit=${limit}`),
  orders: (customerId: string) => request<Order[]>(`/customers/${encodeURIComponent(customerId)}/orders`),
  scenarios: () => request<Scenario[]>("/demo-scenarios"),
  chat: (body: { customer_id: string; message: string; session_id: string }) =>
    request<ChatResponse>("/chat", { method: "POST", body: JSON.stringify(body), timeoutMs: 90000 }),
  reset: (session_id: string) => request<{ ok: boolean }>("/reset", { method: "POST", body: JSON.stringify({ session_id }) }),
  products: (q = "", category = "", limit = 24) =>
    request<Product[]>(`/products?q=${encodeURIComponent(q)}&category=${encodeURIComponent(category)}&limit=${limit}`),
  categories: () => request<Category[]>("/categories"),
  resetDemo: () => request<{ ok: boolean }>("/demo/reset", { method: "POST" }),
};
