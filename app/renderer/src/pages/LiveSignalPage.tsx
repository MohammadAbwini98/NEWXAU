import { Activity, Clock3, Crosshair, Gauge, RefreshCw, ShieldAlert } from "lucide-react";
import { useCallback, useEffect } from "react";
import { EmptyState } from "../components/EmptyState";
import { MetricCard } from "../components/MetricCard";
import { api } from "../data/apiClient";
import { useRemoteResource } from "../hooks/useRemoteResource";
import { useBackend } from "../state/BackendContext";

function ValueTable({ payload }: { payload: Record<string, unknown> }) {
  const entries = Object.entries(payload).filter(([, value]) => value === null || ["string", "number", "boolean"].includes(typeof value));
  return (
    <dl className="value-table">
      {entries.slice(0, 18).map(([key, value]) => (
        <div key={key}><dt>{key.replaceAll("_", " ")}</dt><dd>{value === null ? "—" : String(value)}</dd></div>
      ))}
    </dl>
  );
}

export function LiveSignalPage() {
  const { backend, lastEvent } = useBackend();
  const ready = backend.phase === "ready";
  const signalLoader = useCallback(() => api.signals.latest(), []);
  const priceLoader = useCallback(() => api.price.latest(), []);
  const riskLoader = useCallback(() => api.analysis.risk(), []);
  const signal = useRemoteResource(signalLoader, ready);
  const price = useRemoteResource(priceLoader, ready);
  const risk = useRemoteResource(riskLoader, ready);

  useEffect(() => {
    if (lastEvent?.event === "signal.updated") {
      void signal.refresh();
      void risk.refresh();
    }
    if (lastEvent?.event === "price.updated") void price.refresh();
  }, [lastEvent, signal.refresh, risk.refresh, price.refresh]);

  const payload = signal.data && typeof signal.data === "object" ? signal.data : {};
  const direction = String(payload.signal ?? payload.direction ?? "WAITING");
  const confidence = Number(payload.confidence ?? 0);
  const currentPrice = Number(price.data?.price ?? price.data?.bid ?? 0);
  return (
    <div className="page-stack">
      <section className="metric-grid">
        <MetricCard label="Direction" value={direction} detail={String(payload.status ?? "No active recommendation")} icon={Crosshair} tone={direction === "BUY" ? "positive" : direction === "SELL" ? "danger" : "neutral"} loading={signal.loading} />
        <MetricCard label="Confidence" value={confidence ? `${(confidence * 100).toFixed(1)}%` : "—"} detail="Final ensemble confidence" icon={Gauge} tone="gold" loading={signal.loading} />
        <MetricCard label="Market price" value={currentPrice ? currentPrice.toFixed(2) : "—"} detail={price.data?.source ?? "Price stream"} icon={Activity} loading={price.loading} />
        <MetricCard label="Risk state" value={String(risk.data?.status ?? risk.data?.risk_status ?? "—")} detail="Pre-execution risk gate" icon={ShieldAlert} tone="warning" loading={risk.loading} />
      </section>
      <section className="content-grid wide-left">
        <article className="panel">
          <div className="panel-heading">
            <div><span className="eyebrow">Current recommendation</span><h3>Decision contract</h3></div>
            <button className="icon-button" type="button" aria-label="Refresh signal" onClick={() => void signal.refresh()}><RefreshCw size={16} /></button>
          </div>
          {Object.keys(payload).length ? <ValueTable payload={payload} /> : <EmptyState title="No active recommendation" detail="The live signal will appear after a successful pipeline cycle." />}
        </article>
        <article className="panel">
          <div className="panel-heading"><div><span className="eyebrow">Stream context</span><h3>Freshness</h3></div><Clock3 size={18} /></div>
          <div className="timeline-card">
            <span className="pulse-ring" />
            <strong>{price.data?.status ?? (price.data ? "AVAILABLE" : "WAITING")}</strong>
            <p>{price.data?.message ?? "Live price events update this view without broad dashboard reloads."}</p>
            <small>{price.data?.timestamp ?? price.data?.updated_at ?? "No timestamp received"}</small>
          </div>
        </article>
      </section>
    </div>
  );
}
