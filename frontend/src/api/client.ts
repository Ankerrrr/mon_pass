export type Admin = { username: string };

let csrfToken: string | null = sessionStorage.getItem("quant-home-csrf");

export class ApiError extends Error {
  constructor(public status: number, message: string) {
    super(message);
  }
}

export async function request<T>(path: string, init: RequestInit = {}): Promise<T> {
  const headers = new Headers(init.headers);
  if (init.body && !headers.has("Content-Type")) headers.set("Content-Type", "application/json");
  if (csrfToken && init.method && !["GET", "HEAD"].includes(init.method.toUpperCase())) {
    headers.set("X-CSRF-Token", csrfToken);
  }
  const response = await fetch(`/api${path}`, { ...init, headers, credentials: "same-origin" });
  if (!response.ok) {
    const body = await response.json().catch(() => ({})) as { detail?: string };
    throw new ApiError(response.status, body.detail ?? "Request failed");
  }
  if (response.status === 204) return undefined as T;
  return response.json() as Promise<T>;
}

export async function login(username: string, password: string): Promise<Admin> {
  const response = await request<{ user: Admin; csrf_token: string }>("/auth/login", {
    method: "POST",
    body: JSON.stringify({ username, password }),
  });
  csrfToken = response.csrf_token;
  sessionStorage.setItem("quant-home-csrf", response.csrf_token);
  return response.user;
}

export async function currentAdmin(): Promise<Admin | null> {
  try {
    return await request<Admin>("/auth/me");
  } catch (error) {
    if (error instanceof ApiError && error.status === 401) return null;
    throw error;
  }
}

export async function logout(): Promise<void> {
  await request<void>("/auth/logout", { method: "POST" });
  csrfToken = null;
  sessionStorage.removeItem("quant-home-csrf");
}

export type Configuration = {
  id: string; name: string; version: number; description?: string; payload: Record<string, unknown>;
};

export type BacktestRun = {
  id: string; job_id: string | null; created_at: string; fingerprint: string;
  configuration_snapshot: { name?: string; payload?: Record<string, unknown> } & Record<string, unknown>;
  result_snapshot: { cash_reserve: string; ledgers: Record<string, { initial_cash: string; cash: string; fills: unknown[] }> };
};

export const listConfigurations = () => request<Configuration[]>("/configurations");
export const listBacktests = () => request<BacktestRun[]>("/backtests");

export async function createConfiguration(name: string, payload: Record<string, unknown>): Promise<Configuration> {
  return request<Configuration>("/configurations", {
    method: "POST", body: JSON.stringify({ name, description: "由 Quant Home 工作台建立", payload }),
  });
}

export async function createBacktest(configurationId: string): Promise<{ job_id: string }> {
  return request<{ job_id: string }>("/backtests", {
    method: "POST", body: JSON.stringify({ configuration_id: configurationId }),
  });
}
