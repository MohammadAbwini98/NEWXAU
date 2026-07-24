export type AppearanceMode = "light" | "dark" | "system";

export interface DesktopSettings {
  appearance: AppearanceMode;
  sidebarCollapsed: boolean;
  lastRouteId: string;
  launchBackendOnStart: boolean;
}

export interface BackendState {
  phase: "stopped" | "starting" | "ready" | "degraded" | "restarting" | "stopping" | "failed";
  baseUrl: string | null;
  websocketUrl: string | null;
  pid: number | null;
  startedAt: string | null;
  message: string;
  restartCount: number;
}

export interface DesktopBridge {
  window: {
    minimize(): Promise<void>;
    toggleMaximize(): Promise<void>;
    close(): Promise<void>;
    isMaximized(): Promise<boolean>;
    onMaximizedChange(callback: (maximized: boolean) => void): () => void;
  };
  backend: {
    getState(): Promise<BackendState>;
    restart(): Promise<BackendState>;
    onStateChange(callback: (state: BackendState) => void): () => void;
    request(path: string, init?: DesktopRequestInit): Promise<DesktopResponse>;
    websocketConfig(): Promise<{ url: string; token: string }>;
  };
  settings: {
    get(): Promise<DesktopSettings>;
    update(patch: Partial<DesktopSettings>): Promise<DesktopSettings>;
  };
  secrets: {
    status(): Promise<Record<string, boolean>>;
    set(name: string, value: string): Promise<void>;
    remove(name: string): Promise<void>;
  };
  platform: NodeJS.Platform;
}

export interface DesktopRequestInit {
  method?: string;
  headers?: Record<string, string>;
  body?: string;
}

export interface DesktopResponse {
  ok: boolean;
  status: number;
  headers: Record<string, string>;
  body: unknown;
}

export const IPC = {
  windowMinimize: "window:minimize",
  windowToggleMaximize: "window:toggle-maximize",
  windowClose: "window:close",
  windowIsMaximized: "window:is-maximized",
  windowMaximizedChanged: "window:maximized-changed",
  backendGetState: "backend:get-state",
  backendRestart: "backend:restart",
  backendStateChanged: "backend:state-changed",
  backendRequest: "backend:request",
  backendWebsocketConfig: "backend:websocket-config",
  settingsGet: "settings:get",
  settingsUpdate: "settings:update",
  secretsStatus: "secrets:status",
  secretsSet: "secrets:set",
  secretsRemove: "secrets:remove"
} as const;
