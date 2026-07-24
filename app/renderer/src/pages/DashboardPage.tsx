import { Activity, CircleDollarSign, Clock3, Database, RefreshCw, ShieldCheck, Sparkles, Target } from "lucide-react";
import { useCallback, useEffect } from "react";
import { EmptyState } from "../components/EmptyState";
import { MetricCard } from "../components/MetricCard";
import { api } from "../data/apiClient";
import { isPriceTickEvent } from "../data/eventClient";
import { resolveDisplayPrice } from "../data/priceDisplay";
import { useRemoteResource } from "../hooks/useRemoteResource";
import { useBackend } from "../state/BackendContext";

function formatPercent(value: number | undefined): string {
  if (value === undefined || !Number.isFinite(value)) return "—";
  return `${(value * 100).toFixed(value >= 1 ? 0 : 1)}%`;
}

function formatMoney(value: number | undefined): string {
  if (value === undefined || !Number.isFinite(value)) return "—";
  return new Intl.NumberFormat("en-US", { style: "currency", currency: "USD", maximumFractionDigits: 2 }).format(value);
}

export function DashboardPage() {
  const { backend, lastEvent } = useBackend();
  const ready = backend.phase === "ready";
  const summaryLoader = useCallback(() => api.dashboard.summary(), []);
  const priceLoader = useCallback(() => api.price.latest(), []);
  const marketLoader = useCallback(() => api.market.hours(), []);
  const executionLoader = useCallback(() => api.execution.status(), []);
  const summary = useRemoteResource(summaryLoader, ready);
  const price = useRemoteResource(priceLoader, ready);
  const market = useRemoteResource(marketLoader, ready);
  const execution = useRemoteResource(executionLoader, ready);

  useEffect(() => {
    if (!lastEvent) return;
    if (lastEvent.event === "signal.updated") void summary.refresh();
    if (isPriceTickEvent(lastEvent.event)) void price.refresh();
    if (lastEvent.event === "execution.updated") void execution.refresh();
    if (lastEvent.event.startsWith("market.")) void market.refresh();
  }, [lastEvent, summary.refresh, price.refresh, execution.refresh, market.refresh]);

  const currentSignal = summary.data?.current_signal;
  const dataStatus = summary.data?.data_status;
  const displayPrice = resolveDisplayPrice(price.data, currentSignal);
  const executionSafe = execution.data?.enabled !== true;
  const marketState = String(market.data?.market_state ?? market.data?.status ?? "Unknown");

  if (!ready) {
    return (
      <section className="startup-panel">
        <div className="startup-orbit"><span /><span /><span /></div>
        <span className="eyebrow gold">Local intelligence runtime</span>
        <h2>{backend.phase === "failed" ? "Backend needs attention" : "Preparing NEWXAU"}</h2>
        <p>{backend.message}</p>
      </section>
    );
  }

  return (
    <div className="page-stack">
      <section className="hero-panel">
        <div className="hero-copy">
          <span className="eyebrow gold"><Sparkles size={13} />Decision snapshot</span>
          <h2>
            {currentSignal ? (
              <>The system is currently <em>{currentSignal.signal}</em></>
            ) : (
              <>Waiting for the next qualified setup</>
            )}
          </h2>
          <p>
            Market evidence, ensemble conviction, risk controls, and execution eligibility remain
            authoritative in the Python backend.
          </p>
          <div className="hero-tags">
            <span className={market.data?.tradable ? "tag positive" : "tag warning"}>{marketState}</span>
            <span className={executionSafe ? "tag positive" : "tag danger"}>
              {executionSafe ? "Execution disarmed" : "Execution enabled"}
            </span>
            <span className="tag neutral">{summary.data?.storage_backend ?? "Storage pending"}</span>
          </div>
        </div>
        <div className="signal-dial" aria-label={`Signal confidence ${formatPercent(currentSignal?.confidence)}`}>
          <div><span>Confidence</span><strong>{formatPercent(currentSignal?.confidence)}</strong><small>{currentSignal?.status ?? "NO SIGNAL"}</small></div>
        </div>
      </section>

      {dataStatus?.status === "ERROR" ? (
        <div className="inline-alert" role="alert">
          <Clock3 size={16} />
          <span>{dataStatus.message}</span>
        </div>
      ) : null}

      <section className="metric-grid">
        <MetricCard
          label="XAUUSD"
          value={displayPrice.value === undefined ? "—" : displayPrice.value.toFixed(2)}
          detail={displayPrice.detail}
          icon={CircleDollarSign}
          tone="gold"
          loading={price.loading}
        />
        <MetricCard
          label="Signal quality"
          value={summary.data?.risk_quality ?? "—"}
          detail="Backend risk evaluation"
          icon={ShieldCheck}
          tone={summary.data?.risk_quality === "PASSED" ? "positive" : "warning"}
          loading={summary.loading}
        />
        <MetricCard
          label="Signals tracked"
          value={String(summary.data?.today_performance.signals ?? 0)}
          detail="Persisted recommendation history"
          icon={Target}
          loading={summary.loading}
        />
        <MetricCard
          label="Session P&L"
          value={formatMoney(summary.data?.today_performance.pnl)}
          detail={`Win rate ${formatPercent(summary.data?.today_performance.win_rate)}`}
          icon={Activity}
          tone={(summary.data?.today_performance.pnl ?? 0) >= 0 ? "positive" : "danger"}
          loading={summary.loading}
        />
      </section>

      <section className="content-grid">
        <article className="panel">
          <div className="panel-heading">
            <div><span className="eyebrow">Operational posture</span><h3>Readiness gates</h3></div>
            <button className="icon-button" type="button" aria-label="Refresh dashboard" onClick={() => void Promise.all([summary.refresh(), market.refresh(), execution.refresh()])}>
              <RefreshCw size={16} />
            </button>
          </div>
          <div className="readiness-list">
            <div><span className="status-dot ok" /><span><strong>Backend</strong><small>Authenticated loopback process is ready</small></span><b>READY</b></div>
            <div><span className={`status-dot ${market.data?.tradable ? "ok" : "warn"}`} /><span><strong>Market hours</strong><small>{String(market.data?.reason ?? "Session rules evaluated")}</small></span><b>{marketState}</b></div>
            <div><span className={`status-dot ${executionSafe ? "ok" : "warn"}`} /><span><strong>Capital execution</strong><small>Automated execution remains off by default</small></span><b>{executionSafe ? "SAFE" : "ARMED"}</b></div>
            <div><span className="status-dot ok" /><span><strong>Storage</strong><small>Persistence layer selected by backend</small></span><b>{summary.data?.storage_backend ?? "—"}</b></div>
          </div>
        </article>
        <article className="panel">
          <div className="panel-heading"><div><span className="eyebrow">Ensemble</span><h3>Model allocation</h3></div><Database size={18} /></div>
          {summary.data && Object.keys(summary.data.dynamic_model_weights).length ? (
            <div className="weight-list">
              {Object.entries(summary.data.dynamic_model_weights).sort((a, b) => b[1] - a[1]).map(([name, weight]) => (
                <div key={name}>
                  <span><strong>{name}</strong><small>{formatPercent(weight)}</small></span>
                  <div className="weight-track"><span style={{ width: `${Math.min(weight * 100, 100)}%` }} /></div>
                </div>
              ))}
            </div>
          ) : <EmptyState title="No model allocation yet" detail="Weights appear after the backend initializes the ensemble." />}
        </article>
      </section>

      {(summary.error || price.error || market.error || execution.error) ? (
        <div className="inline-alert" role="status"><Clock3 size={16} /><span>Some live data is stale. The desktop will retry when the next targeted event arrives.</span></div>
      ) : null}
    </div>
  );
}
