export type ConnectionPhase = "idle" | "connecting" | "connected" | "reconnecting" | "disconnected";

export interface NewxauEvent<T = unknown> {
  event: string;
  occurred_at?: string;
  data: T;
}

export interface EventClientStatus {
  phase: ConnectionPhase;
  attempt: number;
  message: string;
}

export function isPriceTickEvent(eventName: string): boolean {
  return eventName === "price.tick";
}

type EventListener = (event: NewxauEvent) => void;
type StatusListener = (status: EventClientStatus) => void;

export class EventClient {
  private socket: WebSocket | null = null;
  private stopped = true;
  private attempt = 0;
  private reconnectTimer: number | null = null;
  private readonly eventListeners = new Set<EventListener>();
  private readonly statusListeners = new Set<StatusListener>();

  onEvent(listener: EventListener): () => void {
    this.eventListeners.add(listener);
    return () => this.eventListeners.delete(listener);
  }

  onStatus(listener: StatusListener): () => void {
    this.statusListeners.add(listener);
    return () => this.statusListeners.delete(listener);
  }

  start(): void {
    if (!this.stopped) return;
    this.stopped = false;
    void this.connect();
  }

  stop(): void {
    this.stopped = true;
    if (this.reconnectTimer !== null) window.clearTimeout(this.reconnectTimer);
    this.reconnectTimer = null;
    this.socket?.close();
    this.socket = null;
    this.publishStatus("disconnected", "Event stream stopped.");
  }

  private async connect(): Promise<void> {
    if (this.stopped) return;
    this.publishStatus(this.attempt ? "reconnecting" : "connecting", "Connecting to live events…");
    try {
      const config = await window.newxau.backend.websocketConfig();
      const url = new URL(config.url);
      url.searchParams.set("token", config.token);
      const socket = new WebSocket(url);
      this.socket = socket;
      socket.onopen = () => {
        this.attempt = 0;
        this.publishStatus("connected", "Live events connected.");
      };
      socket.onmessage = (message) => {
        try {
          const event = JSON.parse(String(message.data)) as NewxauEvent;
          for (const listener of this.eventListeners) listener(event);
        } catch {
          // Invalid payloads are ignored; the stream remains available for later valid events.
        }
      };
      socket.onerror = () => socket.close();
      socket.onclose = () => {
        if (this.socket === socket) this.socket = null;
        if (!this.stopped) this.scheduleReconnect();
      };
    } catch (error) {
      this.publishStatus("disconnected", error instanceof Error ? error.message : String(error));
      this.scheduleReconnect();
    }
  }

  private scheduleReconnect(): void {
    if (this.stopped || this.reconnectTimer !== null) return;
    this.attempt += 1;
    const delay = Math.min(1000 * 2 ** Math.min(this.attempt - 1, 5), 30_000);
    this.publishStatus("reconnecting", `Reconnecting in ${Math.ceil(delay / 1000)}s…`);
    this.reconnectTimer = window.setTimeout(() => {
      this.reconnectTimer = null;
      void this.connect();
    }, delay);
  }

  private publishStatus(phase: ConnectionPhase, message: string): void {
    const snapshot = { phase, attempt: this.attempt, message };
    for (const listener of this.statusListeners) listener(snapshot);
  }
}

export const eventClient = new EventClient();
