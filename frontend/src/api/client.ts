export type Admin = { username: string };

const csrfCookieName = "quant_home_csrf";

function csrfCookie(): string | null {
  const prefix = `${csrfCookieName}=`;
  const row = document.cookie.split("; ").find((item) => item.startsWith(prefix));
  return row ? decodeURIComponent(row.slice(prefix.length)) : null;
}

let csrfToken: string | null = csrfCookie() ?? sessionStorage.getItem("quant-home-csrf");

function saveCsrfToken(value: string): void {
  csrfToken = value;
  sessionStorage.setItem("quant-home-csrf", value);
}

export class ApiError extends Error {
  constructor(public status: number, message: string) {
    super(message);
  }
}

export async function request<T>(path: string, init: RequestInit = {}): Promise<T> {
  const method = init.method?.toUpperCase() ?? "GET";
  const isMutation = !["GET", "HEAD"].includes(method);
  const send = () => {
    const headers = new Headers(init.headers);
    if (init.body && !headers.has("Content-Type")) headers.set("Content-Type", "application/json");
    const activeToken = csrfCookie() ?? csrfToken;
    if (activeToken && isMutation) headers.set("X-CSRF-Token", activeToken);
    return fetch(`/api${path}`, { ...init, headers, credentials: "same-origin" });
  };

  let response = await send();
  if (!response.ok && response.status === 403 && isMutation && path !== "/auth/csrf") {
    const body = await response.clone().json().catch(() => ({})) as { detail?: string };
    if (body.detail === "Invalid CSRF token") {
      const refreshed = await fetch("/api/auth/csrf", { credentials: "same-origin" });
      if (refreshed.ok) {
        const payload = await refreshed.json() as { csrf_token: string };
        saveCsrfToken(payload.csrf_token);
        response = await send();
      }
    }
  }
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
  saveCsrfToken(response.csrf_token);
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

export type StrategySummary = {
  initial_cash: string; ending_cash: string; position_value: string; ending_equity: string;
  total_pnl: string; total_return: string; realized_pnl: string; unrealized_pnl: string;
  fees: string; fill_count: number; valuation_is_estimated: boolean;
};

export type StrategyOperation = {
  filled_at: string | null; symbol: string; side: "buy" | "sell"; quantity: string;
  price: string; notional: string; fee: string; cash_delta: string; realized_pnl: string;
  cash_after: string; position_quantity_after: string; equity_after: string;
  equity_change: string; reason: string; mode: "backtest" | "paper";
};

export type StrategyLedger = {
  initial_cash: string; cash: string; fills: unknown[]; positions?: Record<string, unknown>;
  summary: StrategySummary; operations: StrategyOperation[];
};

export type BacktestRun = {
  id: string; job_id: string | null; created_at: string; fingerprint: string;
  configuration_snapshot: { name?: string; payload?: Record<string, unknown> } & Record<string, unknown>;
  result_snapshot: { cash_reserve: string; ledgers: Record<string, StrategyLedger> };
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

export type PaperSession = {
  id: string; configuration_id: string | null; configuration_version: number;
  status: "active" | "stopped" | "error"; connection_state: string;
  last_candle_at: string | null; error: string | null; created_at: string;
  state_snapshot: { cash_reserve: string; ledgers: Record<string, StrategyLedger> };
};

export const listPaperSessions = () => request<PaperSession[]>("/paper");
export const startPaperSession = (configurationId: string) => request<{ id: string }>("/paper", {
  method: "POST", body: JSON.stringify({ configuration_id: configurationId }),
});
export const stopPaperSession = (sessionId: string) => request<{ stopped: boolean }>(`/paper/${sessionId}/stop`, { method: "POST" });
export const emergencyStopPaper = () => request<{ stopped: number }>("/paper/emergency-stop/all", { method: "POST" });
export const systemHealth = () => request<Record<string, string | null>>("/system/health");

export type Job = { id: string; status: string; progress: number; error: string | null; kind: string; created_at: string };
export const getJob = (id: string) => request<Job>(`/jobs/${id}`);
export const cancelJob = (id: string) => request<{ status: string }>(`/jobs/${id}/cancel`, { method: "POST" });
export const cloneConfiguration = (id: string, name: string) => request<Configuration>(`/configurations/${id}/clone`, { method: "POST", body: JSON.stringify({ name }) });
export const deleteConfiguration = (id: string) => request<void>(`/configurations/${id}`, { method: "DELETE" });
export const exportConfiguration = (id: string) => request<Record<string, unknown>>(`/configurations/${id}/export`);

export type Dataset = { id: string; symbol: string; interval: string; start: string; end: string; candle_count: number; is_valid: boolean; reference_count: number; fingerprint: string };
export const listDatasets = () => request<Dataset[]>("/datasets");
export const deleteDataset = (id: string) => request<void>(`/datasets/${id}`, { method: "DELETE" });
export const refreshSymbols = () => request<{ total_symbols: number }>("/symbols/refresh", { method: "POST" });
export type AuditEvent = { id: string; action: string; subject_type: string; subject_id: string | null; created_at: string };
export const listAuditEvents = () => request<AuditEvent[]>("/paper/audit/events");
