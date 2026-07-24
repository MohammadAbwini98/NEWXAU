import { useEffect, useMemo, useState } from "react";
import { AppShell } from "./components/AppShell";
import { ErrorBoundary } from "./components/ErrorBoundary";
import { routes, type RouteId } from "./routes";
import { BackendProvider } from "./state/BackendContext";
import { ThemeProvider } from "./state/ThemeContext";

export function App() {
  const [routeId, setRouteId] = useState<RouteId>("dashboard");
  useEffect(() => {
    void window.newxau.settings.get().then((settings) => {
      if (routes.some((route) => route.id === settings.lastRouteId)) setRouteId(settings.lastRouteId as RouteId);
    });
  }, []);
  const route = useMemo(() => routes.find((candidate) => candidate.id === routeId) ?? routes[0], [routeId]);
  const Page = route.component;
  const navigate = (next: RouteId) => {
    setRouteId(next);
    void window.newxau.settings.update({ lastRouteId: next });
  };
  return (
    <ThemeProvider>
      <BackendProvider>
        <AppShell route={route} routeId={routeId} onRouteChange={navigate}>
          <ErrorBoundary key={routeId} area={route.label}><Page /></ErrorBoundary>
        </AppShell>
      </BackendProvider>
    </ThemeProvider>
  );
}
