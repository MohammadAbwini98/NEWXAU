import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { EventClient, isPriceTickEvent, type NewxauEvent } from "./eventClient";

class FakeWebSocket {
  static instances: FakeWebSocket[] = [];
  onopen: (() => void) | null = null;
  onmessage: ((event: { data: string }) => void) | null = null;
  onerror: (() => void) | null = null;
  onclose: (() => void) | null = null;
  closed = false;

  constructor(readonly url: string | URL) {
    FakeWebSocket.instances.push(this);
  }

  open(): void {
    this.onopen?.();
  }

  message(payload: unknown): void {
    this.onmessage?.({ data: JSON.stringify(payload) });
  }

  close(): void {
    this.closed = true;
    this.onclose?.();
  }
}

describe("EventClient", () => {
  it("matches the backend price tick event contract", () => {
    expect(isPriceTickEvent("price.tick")).toBe(true);
    expect(isPriceTickEvent("price.updated")).toBe(false);
  });

  beforeEach(() => {
    FakeWebSocket.instances = [];
    vi.stubGlobal("WebSocket", FakeWebSocket);
    Object.defineProperty(window, "newxau", {
      configurable: true,
      value: {
        backend: {
          websocketConfig: vi.fn().mockResolvedValue({
            url: "ws://127.0.0.1:43210/ws/events",
            token: "test-token"
          })
        }
      }
    });
  });

  afterEach(() => {
    vi.useRealTimers();
    vi.unstubAllGlobals();
  });

  it("adds the token and forwards valid event envelopes", async () => {
    const client = new EventClient();
    const received: NewxauEvent[] = [];
    client.onEvent((event) => received.push(event));

    client.start();
    await vi.waitFor(() => expect(FakeWebSocket.instances).toHaveLength(1));
    const socket = FakeWebSocket.instances[0];
    expect(String(socket.url)).toContain("token=test-token");

    socket.open();
    socket.message({ event: "signal.updated", occurred_at: "2026-07-23T00:00:00Z", data: { signal: "BUY" } });

    expect(received).toEqual([
      { event: "signal.updated", occurred_at: "2026-07-23T00:00:00Z", data: { signal: "BUY" } }
    ]);
    client.stop();
  });

  it("reconnects with bounded backoff after a disconnect", async () => {
    vi.useFakeTimers();
    const client = new EventClient();
    const phases: string[] = [];
    client.onStatus((status) => phases.push(status.phase));

    client.start();
    await Promise.resolve();
    await Promise.resolve();
    expect(FakeWebSocket.instances).toHaveLength(1);
    FakeWebSocket.instances[0].open();
    FakeWebSocket.instances[0].close();

    await vi.advanceTimersByTimeAsync(1000);
    expect(FakeWebSocket.instances).toHaveLength(2);
    expect(phases).toContain("reconnecting");
    client.stop();
  });
});
