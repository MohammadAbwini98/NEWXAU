import { ChevronLeft, Moon, PanelLeftClose, PanelLeftOpen, RotateCw, Sun, Wifi, WifiOff, XCircle } from "lucide-react";
import { useState, type ReactNode } from "react";
import type { AppRoute, RouteId } from "../routes";
import { routes, routeGroups } from "../routes";
import { useBackend } from "../state/BackendContext";
import { useTheme } from "../state/ThemeContext";
import { WindowControls } from "./WindowControls";

function BrandMark() {
  return (
    <span className="brand-mark" aria-hidden="true">
      <svg viewBox="0 0 40 40">
        <path d="M9 10h22l-5 7H14l-5-7Z" />
        <path d="M12 18h16l-4 6h-8l-4-6Z" />
        <path d="M15 25h10l-5 7-5-7Z" />
      </svg>
    </span>
  );
}

export function AppShell({
  route,
  routeId,
  onRouteChange,
  children
}: {
  route: AppRoute;
  routeId: RouteId;
  onRouteChange(id: RouteId): void;
  children: ReactNode;
}) {
  const { backend, events, restart } = useBackend();
  const { resolved, setAppearance } = useTheme();
  const [collapsed, setCollapsed] = useState(false);
  const backendReady = backend.phase === "ready";
  const eventsReady = events.phase === "connected";
  return (
    <div className="app-window">
      <header className="title-bar" onDoubleClick={() => void window.newxau.window.toggleMaximize()}>
        <div className="title-identity"><BrandMark /><strong>NEWXAU</strong><span>Trading Intelligence</span></div>
        <div className="title-context"><span />{route.label}</div>
        <div className="drag-space" />
        <span className={`environment-badge ${backendReady ? "safe" : "warning"}`}>
          {backendReady ? "DESKTOP · DEMO SAFE" : backend.phase.toUpperCase()}
        </span>
        <WindowControls />
      </header>
      <div className={collapsed ? "app-shell sidebar-collapsed" : "app-shell"}>
        <aside className="sidebar">
          <div className="sidebar-heading">
            {!collapsed ? <span>Workspace</span> : <BrandMark />}
            <button
              className="icon-button"
              type="button"
              aria-label={collapsed ? "Expand navigation" : "Collapse navigation"}
              aria-expanded={!collapsed}
              onClick={() => setCollapsed((value) => !value)}
            >
              {collapsed ? <PanelLeftOpen size={17} /> : <PanelLeftClose size={17} />}
            </button>
          </div>
          <nav aria-label="Primary navigation">
            {routeGroups.map((group) => (
              <section className="nav-group" key={group}>
                {!collapsed ? <h2>{group}</h2> : null}
                {routes.filter((item) => item.group === group).map((item) => {
                  const Icon = item.icon;
                  return (
                    <button
                      key={item.id}
                      className={item.id === routeId ? "nav-item active" : "nav-item"}
                      type="button"
                      aria-current={item.id === routeId ? "page" : undefined}
                      title={collapsed ? item.label : item.description}
                      onClick={() => onRouteChange(item.id)}
                    >
                      <Icon size={17} />
                      {!collapsed ? <span>{item.label}</span> : null}
                    </button>
                  );
                })}
              </section>
            ))}
          </nav>
          <div className="sidebar-footer">
            <button
              className="nav-item"
              type="button"
              title={`Switch to ${resolved === "dark" ? "light" : "dark"} mode`}
              onClick={() => setAppearance(resolved === "dark" ? "light" : "dark")}
            >
              {resolved === "dark" ? <Moon size={17} /> : <Sun size={17} />}
              {!collapsed ? <span>{resolved === "dark" ? "Dark theme" : "Light theme"}</span> : null}
            </button>
            {!collapsed ? (
              <div className="workspace-note">
                <BrandMark />
                <span><strong>Local workspace</strong><small>Protected loopback runtime</small></span>
              </div>
            ) : null}
          </div>
        </aside>
        <div className="main-column">
          <header className="page-header">
            <button className="icon-button" type="button" aria-label="Back to overview" disabled={routeId === "dashboard"} onClick={() => onRouteChange("dashboard")}>
              <ChevronLeft size={18} />
            </button>
            <div><span className="eyebrow">{route.group}</span><h1>{route.label}</h1><p>{route.description}</p></div>
            <div className="page-actions">
              {!backendReady ? (
                <button className="button" type="button" onClick={() => void restart()}><RotateCw size={15} />Restart backend</button>
              ) : null}
              <span className={`connection-pill ${eventsReady ? "connected" : "disconnected"}`}>
                {eventsReady ? <Wifi size={14} /> : <WifiOff size={14} />}
                {events.phase}
              </span>
            </div>
          </header>
          <main key={routeId} className="main-surface">{children}</main>
          <footer className="status-bar">
            <span className={backendReady ? "status-item ok" : "status-item warn"}>
              {backendReady ? <Wifi size={13} /> : <XCircle size={13} />}Backend: {backend.phase}
            </span>
            <span className={eventsReady ? "status-item ok" : "status-item warn"}>Events: {events.phase}</span>
            <span className="status-spacer" />
            <span>PID {backend.pid ?? "—"}</span>
            <span>Execution defaults: OFF · demo-only</span>
          </footer>
        </div>
      </div>
    </div>
  );
}
