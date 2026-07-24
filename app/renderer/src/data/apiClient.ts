import type { DesktopRequestInit } from "../../../shared/contracts";

export class ApiError extends Error {
  constructor(
    message: string,
    readonly status: number,
    readonly payload: unknown
  ) {
    super(message);
  }
}

export interface DashboardSummary {
  current_signal: {
    signal: string;
    status: string;
    confidence: number;
    current_price?: number | null;
    entry_price?: number | null;
  } | null;
  model_consensus: Record<string, unknown> | null;
  risk_quality: string | null;
  storage_backend: string;
  dynamic_model_weights: Record<string, number>;
  model_artifacts: Record<string, unknown>;
  today_performance: {
    win_rate: number;
    profit_factor: number;
    pnl: number;
    signals: number;
  };
}

export interface PriceSnapshot {
  status?: string;
  epic?: string;
  bid?: number;
  ask?: number;
  price?: number;
  timestamp?: string;
  updated_at?: string;
  source?: string;
  message?: string;
}

export interface MarketHoursSnapshot {
  status?: string;
  market_state?: string;
  session?: string;
  tradable?: boolean;
  reason?: string;
  [key: string]: unknown;
}

export interface ExecutionSnapshot {
  enabled?: boolean;
  auto_execute?: boolean;
  demo_only?: boolean;
  environment?: string;
  armed?: boolean;
  status?: string;
  [key: string]: unknown;
}

export interface SystemHealthSnapshot {
  status?: string;
  overall_status?: string;
  checks?: Record<string, unknown>;
  [key: string]: unknown;
}

export interface DesktopRuntimeSnapshot {
  status: string;
  pid: number;
  runtime_root: string;
  resource_root: string;
  desktop_mode: boolean;
  execution: {
    enabled: boolean;
    auto_execute: boolean;
    demo_only: boolean;
  };
}

export async function request<T>(path: string, init?: DesktopRequestInit): Promise<T> {
  const response = await window.newxau.backend.request(path, init);
  if (!response.ok) {
    const detail =
      response.body && typeof response.body === "object" && "detail" in response.body
        ? String((response.body as { detail: unknown }).detail)
        : `Request failed with status ${response.status}`;
    throw new ApiError(detail, response.status, response.body);
  }
  return response.body as T;
}

export const api = {
  dashboard: {
    summary: () => request<DashboardSummary>("/api/dashboard/summary"),
    currentSignal: () => request<Record<string, unknown>>("/api/dashboard/current-signal")
  },
  price: {
    latest: () => request<PriceSnapshot>("/api/price/latest")
  },
  execution: {
    status: () => request<ExecutionSnapshot>("/api/execution/status"),
    control: () => request<Record<string, unknown>>("/api/execution/control"),
    updateControl: (config: object) =>
      request<Record<string, unknown>>("/api/execution/control", {
        method: "PUT",
        body: JSON.stringify(config)
      }),
    controlStats: () => request<Record<string, unknown>>("/api/execution/control/stats"),
    orders: () => request<Record<string, unknown>>("/api/execution/orders?page=1&page_size=20"),
    refreshOutcomes: () =>
      request<Record<string, unknown>>("/api/execution/refresh-outcomes", { method: "POST" })
  },
  signals: {
    latest: () => request<Record<string, unknown>>("/api/signals/latest"),
    history: () => request<Record<string, unknown>>("/api/signals/history?page=1&page_size=20"),
    outcomes: () => request<Record<string, unknown>>("/api/signals/outcomes")
  },
  models: {
    votes: () => request<Record<string, unknown>>("/api/models/latest-votes"),
    artifacts: () => request<Record<string, unknown>>("/api/models/artifacts"),
    performance: () => request<Record<string, unknown>>("/api/models/performance/summary"),
    weights: () => request<Record<string, unknown>>("/api/models/weights/current")
  },
  market: {
    hours: () => request<MarketHoursSnapshot>("/api/market/hours"),
    regime: () => request<Record<string, unknown>>("/api/market/regime/current"),
    timeframes: () => request<Record<string, unknown>>("/api/market/timeframes/current")
  },
  analysis: {
    indicators: () => request<Record<string, unknown>>("/api/indicators/latest"),
    risk: () => request<Record<string, unknown>>("/api/risk/status")
  },
  research: {
    backtestSummary: () => request<Record<string, unknown>>("/api/backtest/summary"),
    backtests: () => request<Record<string, unknown>>("/api/backtests"),
    optimizations: () => request<Record<string, unknown>>("/api/optimization/runs"),
    news: () => request<Record<string, unknown>>("/api/news/dashboard/summary"),
    runBacktest: (payload: Record<string, unknown>) =>
      request<Record<string, unknown>>("/api/backtests/run", {
        method: "POST",
        body: JSON.stringify(payload)
      })
  },
  system: {
    health: () => request<SystemHealthSnapshot>("/api/system/health"),
    runtime: () => request<DesktopRuntimeSnapshot>("/api/desktop/runtime"),
    readiness: () => request<Record<string, unknown>>("/api/desktop/readiness")
  }
};
