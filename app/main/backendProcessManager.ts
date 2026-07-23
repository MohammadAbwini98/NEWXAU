import { type ChildProcessWithoutNullStreams, spawn } from "node:child_process";
import { createServer } from "node:net";
import { mkdir, appendFile } from "node:fs/promises";
import { join } from "node:path";
import { randomBytes } from "node:crypto";
import { EventEmitter } from "node:events";
import type { AppPaths } from "./appPaths";
import type { BackendState, DesktopRequestInit, DesktopResponse } from "../shared/contracts";
import type { SecretStore } from "./secretStore";
import {
  redactErrorMessage,
  redactSensitiveText,
  redactSensitiveValue
} from "../shared/redaction";

interface ReadyMessage {
  event: "ready";
  host: string;
  port: number;
}

const ALLOWED_MUTATIONS = new Set([
  "PUT /api/execution/control",
  "POST /api/execution/refresh-outcomes",
  "POST /api/backtests/run"
]);

const DESKTOP_SECRET_ENV_NAMES = [
  "CAPITALCOM_API_KEY",
  "CAPITAL_API_KEY",
  "CAPITALCOM_IDENTIFIER",
  "CAPITAL_IDENTIFIER",
  "CAPITAL_EMAIL",
  "CAPITALCOM_PASSWORD",
  "CAPITAL_PASSWORD",
  "POSTGRES_DSN",
  "TELEGRAM_BOT_TOKEN",
  "TELEGRAM_CHAT_ID"
] as const;

export function resolveDesktopSecretEnvironment(
  stored: Record<string, string>,
  inherited: NodeJS.ProcessEnv
): Record<string, string> {
  return Object.fromEntries(
    DESKTOP_SECRET_ENV_NAMES.map((name) => [name, stored[name] ?? inherited[name] ?? ""])
  );
}

export function assertBackendRequestAllowed(path: string, method: string): void {
  if (!path.startsWith("/") || path.startsWith("//")) throw new Error("Invalid backend path.");
  const normalizedMethod = method.toUpperCase();
  if (normalizedMethod === "GET") return;
  if (!ALLOWED_MUTATIONS.has(`${normalizedMethod} ${path}`)) {
    throw new Error(`The desktop bridge does not permit ${normalizedMethod} ${path}.`);
  }
}

const INITIAL_STATE: BackendState = {
  phase: "stopped",
  baseUrl: null,
  websocketUrl: null,
  pid: null,
  startedAt: null,
  message: "Backend is stopped.",
  restartCount: 0
};

function isReadyMessage(value: unknown): value is ReadyMessage {
  if (!value || typeof value !== "object") return false;
  const candidate = value as Partial<ReadyMessage>;
  return candidate.event === "ready" && candidate.host === "127.0.0.1" && Number.isInteger(candidate.port);
}

async function reservePort(): Promise<number> {
  return new Promise((resolve, reject) => {
    const server = createServer();
    server.unref();
    server.once("error", reject);
    server.listen(0, "127.0.0.1", () => {
      const address = server.address();
      if (!address || typeof address === "string") {
        server.close();
        reject(new Error("Could not reserve a loopback port."));
        return;
      }
      const port = address.port;
      server.close((error) => (error ? reject(error) : resolve(port)));
    });
  });
}

export class BackendProcessManager extends EventEmitter {
  private child: ChildProcessWithoutNullStreams | null = null;
  private state: BackendState = { ...INITIAL_STATE };
  private token = "";
  private stopping = false;
  private restartTimer: NodeJS.Timeout | null = null;

  constructor(
    private readonly paths: AppPaths,
    private readonly secrets: SecretStore
  ) {
    super();
  }

  getState(): BackendState {
    return { ...this.state };
  }

  getWebsocketConfig(): { url: string; token: string } {
    if (!this.state.websocketUrl || !this.token) throw new Error("Backend is not ready.");
    return { url: this.state.websocketUrl, token: this.token };
  }

  private setState(patch: Partial<BackendState>): void {
    const safePatch = patch.message
      ? { ...patch, message: redactSensitiveText(patch.message) }
      : patch;
    this.state = { ...this.state, ...safePatch };
    this.emit("state", this.getState());
  }

  async start(): Promise<BackendState> {
    if (this.child && !this.child.killed) return this.getState();
    if (!this.paths.pythonExecutable) {
      this.setState({
        phase: "failed",
        baseUrl: null,
        websocketUrl: null,
        pid: null,
        startedAt: null,
        message: this.paths.pythonResolutionError ?? "A verified Python runtime is required."
      });
      return this.getState();
    }
    this.stopping = false;
    this.token = randomBytes(32).toString("base64url");
    const port = await reservePort();
    const secretEnvironment = await this.secrets.environment();
    const isolatedSecretEnvironment = resolveDesktopSecretEnvironment(
      secretEnvironment,
      process.env
    );
    await mkdir(this.paths.logsRoot, { recursive: true });
    await mkdir(this.paths.runtimeRoot, { recursive: true });
    this.setState({
      phase: "starting",
      baseUrl: null,
      websocketUrl: null,
      pid: null,
      startedAt: new Date().toISOString(),
      message: "Starting the NEWXAU backend…"
    });

    const child = spawn(
      this.paths.pythonExecutable,
      [join(this.paths.backendRoot, "scripts", "run_backend.py"), "--host", "127.0.0.1", "--port", String(port)],
      {
        cwd: this.paths.backendRoot,
        shell: false,
        windowsHide: true,
        env: {
          ...process.env,
          ...secretEnvironment,
          ...isolatedSecretEnvironment,
          PYTHONDONTWRITEBYTECODE: "1",
          PYTHONUNBUFFERED: "1",
          NEWXAU_DESKTOP_TOKEN: this.token,
          NEWXAU_DESKTOP_ORIGIN: "app://newxau",
          NEWXAU_DESKTOP_ALLOW_SHUTDOWN: "1",
          NEWXAU_RUNTIME_ROOT: this.paths.runtimeRoot,
          NEWXAU_RESOURCE_ROOT: this.paths.resourceRoot,
          CAPITAL_EXECUTION_ENABLED: process.env.CAPITAL_EXECUTION_ENABLED ?? "0",
          CAPITAL_EXECUTION_AUTO_EXECUTE: process.env.CAPITAL_EXECUTION_AUTO_EXECUTE ?? "0",
          CAPITAL_EXECUTION_DEMO_ONLY: process.env.CAPITAL_EXECUTION_DEMO_ONLY ?? "1"
        }
      }
    );
    this.child = child;
    this.setState({ pid: child.pid ?? null });

    let stdoutBuffer = "";
    child.stdout.on("data", (chunk: Buffer) => {
      const text = chunk.toString("utf8");
      void this.log("backend.stdout.log", text);
      stdoutBuffer += text;
      const lines = stdoutBuffer.split(/\r?\n/);
      stdoutBuffer = lines.pop() ?? "";
      for (const line of lines) this.handleStdoutLine(line);
    });
    child.stderr.on("data", (chunk: Buffer) => {
      const text = chunk.toString("utf8");
      void this.log("backend.stderr.log", text);
      if (this.state.phase === "ready") {
        this.setState({
          message: redactSensitiveText(text.trim()).slice(0, 240) || this.state.message
        });
      }
    });
    child.once("error", (error) => {
      this.setState({
        phase: "failed",
        message: `Backend launch failed: ${redactErrorMessage(error)}`
      });
    });
    child.once("exit", (code, signal) => {
      this.child = null;
      const expected = this.stopping;
      this.setState({
        phase: expected ? "stopped" : "failed",
        baseUrl: null,
        websocketUrl: null,
        pid: null,
        message: expected
          ? "Backend stopped."
          : `Backend exited unexpectedly (${signal ?? `code ${code ?? "unknown"}`}).`
      });
      if (!expected && this.state.restartCount < 3) {
        this.restartTimer = setTimeout(() => void this.restart(true), 1200 * (this.state.restartCount + 1));
      }
    });
    return this.getState();
  }

  private handleStdoutLine(line: string): void {
    try {
      const payload = JSON.parse(line) as unknown;
      if (!isReadyMessage(payload)) return;
      const baseUrl = `http://${payload.host}:${payload.port}`;
      this.setState({
        phase: "ready",
        baseUrl,
        websocketUrl: `ws://${payload.host}:${payload.port}/ws/events`,
        message: "Backend ready."
      });
    } catch {
      // Non-JSON application logs are expected and retained in the desktop log.
    }
  }

  async request(path: string, init: DesktopRequestInit = {}): Promise<DesktopResponse> {
    if (!this.state.baseUrl) throw new Error("Backend is not ready.");
    const method = (init.method ?? "GET").toUpperCase();
    assertBackendRequestAllowed(path, method);
    try {
      const response = await fetch(`${this.state.baseUrl}${path}`, {
        method,
        headers: {
          Accept: "application/json",
          ...(init.body ? { "Content-Type": "application/json" } : {}),
          ...init.headers,
          Authorization: `Bearer ${this.token}`
        },
        body: init.body
      });
      const contentType = response.headers.get("content-type") ?? "";
      const body = contentType.includes("application/json") ? await response.json() : await response.text();
      return {
        ok: response.ok,
        status: response.status,
        headers: redactSensitiveValue(
          Object.fromEntries(response.headers.entries())
        ) as Record<string, string>,
        body: response.ok ? body : redactSensitiveValue(body)
      };
    } catch (error) {
      return {
        ok: false,
        status: 503,
        headers: {},
        body: {
          detail: `Backend request failed: ${redactErrorMessage(error)}`
        }
      };
    }
  }

  async restart(automatic = false): Promise<BackendState> {
    if (this.restartTimer) clearTimeout(this.restartTimer);
    this.setState({
      phase: "restarting",
      restartCount: automatic ? this.state.restartCount + 1 : 0,
      message: automatic ? "Restarting backend after an unexpected exit…" : "Restarting backend…"
    });
    await this.stop();
    return this.start();
  }

  async stop(): Promise<void> {
    if (!this.child) {
      this.setState({ phase: "stopped", message: "Backend stopped." });
      return;
    }
    this.stopping = true;
    this.setState({ phase: "stopping", message: "Stopping backend…" });
    const child = this.child;
    try {
      if (this.state.baseUrl) {
        await Promise.race([
          this.requestOwnedShutdown(),
          new Promise((_, reject) => setTimeout(() => reject(new Error("Shutdown timeout")), 2500))
        ]);
      }
    } catch {
      child.kill();
    }
    await new Promise<void>((resolve) => {
      if (!this.child) {
        resolve();
        return;
      }
      const timer = setTimeout(() => {
        child.kill();
        resolve();
      }, 4000);
      child.once("exit", () => {
        clearTimeout(timer);
        resolve();
      });
    });
  }

  private async requestOwnedShutdown(): Promise<void> {
    if (!this.state.baseUrl) return;
    const response = await fetch(`${this.state.baseUrl}/api/desktop/shutdown`, {
      method: "POST",
      headers: {
        Accept: "application/json",
        Authorization: `Bearer ${this.token}`
      }
    });
    if (!response.ok) {
      throw new Error(`Owned backend shutdown failed with HTTP ${response.status}.`);
    }
  }

  private async log(file: string, text: string): Promise<void> {
    await appendFile(join(this.paths.logsRoot, file), redactSensitiveText(text), "utf8");
  }
}
