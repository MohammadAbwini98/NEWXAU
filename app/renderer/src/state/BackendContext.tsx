import { createContext, useContext, useEffect, useMemo, useState, type ReactNode } from "react";
import type { BackendState } from "../../../shared/contracts";
import { eventClient, type EventClientStatus, type NewxauEvent } from "../data/eventClient";

interface BackendContextValue {
  backend: BackendState;
  events: EventClientStatus;
  lastEvent: NewxauEvent | null;
  restart(): Promise<void>;
}

const initialBackend: BackendState = {
  phase: "stopped",
  baseUrl: null,
  websocketUrl: null,
  pid: null,
  startedAt: null,
  message: "Loading backend state…",
  restartCount: 0
};

const BackendContext = createContext<BackendContextValue | null>(null);

export function BackendProvider({ children }: { children: ReactNode }) {
  const [backend, setBackend] = useState(initialBackend);
  const [events, setEvents] = useState<EventClientStatus>({
    phase: "idle",
    attempt: 0,
    message: "Waiting for backend."
  });
  const [lastEvent, setLastEvent] = useState<NewxauEvent | null>(null);

  useEffect(() => {
    let active = true;
    const synchronize = () => {
      void window.newxau.backend.getState().then((state) => active && setBackend(state));
    };
    synchronize();
    const timer = window.setInterval(synchronize, 1000);
    const offBackend = window.newxau.backend.onStateChange(setBackend);
    return () => {
      active = false;
      window.clearInterval(timer);
      offBackend();
    };
  }, []);

  useEffect(() => {
    const offStatus = eventClient.onStatus(setEvents);
    const offEvent = eventClient.onEvent(setLastEvent);
    if (backend.phase === "ready") eventClient.start();
    else eventClient.stop();
    return () => {
      offStatus();
      offEvent();
    };
  }, [backend.phase]);

  const value = useMemo<BackendContextValue>(
    () => ({
      backend,
      events,
      lastEvent,
      restart: async () => {
        setBackend(await window.newxau.backend.restart());
      }
    }),
    [backend, events, lastEvent]
  );
  return <BackendContext.Provider value={value}>{children}</BackendContext.Provider>;
}

export function useBackend(): BackendContextValue {
  const value = useContext(BackendContext);
  if (!value) throw new Error("useBackend must be used inside BackendProvider.");
  return value;
}
