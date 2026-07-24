import { Cpu, Database, FolderCog, HeartPulse, Radio, RotateCw, Server } from "lucide-react";
import { useCallback } from "react";
import { MetricCard } from "../components/MetricCard";
import { api } from "../data/apiClient";
import { useRemoteResource } from "../hooks/useRemoteResource";
import { useBackend } from "../state/BackendContext";

export function HealthPage() {
  const { backend, events, restart } = useBackend();
  const healthLoader = useCallback(() => api.system.health(), []);
  const runtimeLoader = useCallback(() => api.system.runtime(), []);
  const health = useRemoteResource(healthLoader, backend.phase === "ready");
  const runtime = useRemoteResource(runtimeLoader, backend.phase === "ready");
  const overall = String(health.data?.overall_status ?? health.data?.status ?? "UNKNOWN");
  return (
    <div className="page-stack">
      <section className="metric-grid">
        <MetricCard label="Backend" value={backend.phase.toUpperCase()} detail={backend.message} icon={Server} tone={backend.phase === "ready" ? "positive" : "warning"} />
        <MetricCard label="System health" value={overall} detail="FastAPI service aggregation" icon={HeartPulse} tone={overall === "HEALTHY" || overall === "OK" ? "positive" : "warning"} loading={health.loading} />
        <MetricCard label="Event stream" value={events.phase.toUpperCase()} detail={events.message} icon={Radio} tone={events.phase === "connected" ? "positive" : "warning"} />
        <MetricCard label="Process" value={runtime.data ? `PID ${runtime.data.pid}` : "—"} detail="Desktop-owned Python runtime" icon={Cpu} loading={runtime.loading} />
      </section>
      <section className="content-grid">
        <article className="panel">
          <div className="panel-heading"><div><span className="eyebrow">Desktop runtime</span><h3>Process boundaries</h3></div><FolderCog size={18} /></div>
          <dl className="value-table">
            <div><dt>Backend URL</dt><dd>{backend.baseUrl ?? "Not assigned"}</dd></div>
            <div><dt>Runtime root</dt><dd className="path-value">{runtime.data?.runtime_root ?? "—"}</dd></div>
            <div><dt>Resource root</dt><dd className="path-value">{runtime.data?.resource_root ?? "—"}</dd></div>
            <div><dt>Execution enabled</dt><dd>{runtime.data?.execution.enabled ? "YES" : "NO"}</dd></div>
            <div><dt>Auto execute</dt><dd>{runtime.data?.execution.auto_execute ? "YES" : "NO"}</dd></div>
            <div><dt>Demo only</dt><dd>{runtime.data?.execution.demo_only === false ? "NO" : "YES"}</dd></div>
          </dl>
          <button className="button" type="button" onClick={() => void restart()}><RotateCw size={15} />Restart backend</button>
        </article>
        <article className="panel">
          <div className="panel-heading"><div><span className="eyebrow">Service report</span><h3>Backend checks</h3></div><Database size={18} /></div>
          <pre className="json-view">{JSON.stringify(health.data ?? { status: health.error ?? "Waiting for health response" }, null, 2)}</pre>
        </article>
      </section>
    </div>
  );
}
