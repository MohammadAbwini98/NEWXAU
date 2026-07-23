import { Activity, BarChart3, BrainCircuit, ChartNoAxesCombined, FlaskConical, History, Newspaper, Radar, RefreshCw, ShieldCheck } from "lucide-react";
import { useCallback, useState, type FormEvent } from "react";
import { RecordTable } from "../components/RecordTable";
import { api } from "../data/apiClient";
import { useRemoteResource } from "../hooks/useRemoteResource";
import { useBackend } from "../state/BackendContext";

function JsonSummary({ payload }: { payload: unknown }) {
  return <pre className="json-view domain-json">{JSON.stringify(payload ?? { status: "No data" }, null, 2)}</pre>;
}

function DomainPage({
  eyebrow,
  title,
  description,
  icon: Icon,
  loader,
  table = false
}: {
  eyebrow: string;
  title: string;
  description: string;
  icon: typeof Activity;
  loader: () => Promise<Record<string, unknown>>;
  table?: boolean;
}) {
  const { backend } = useBackend();
  const resource = useRemoteResource(loader, backend.phase === "ready");
  return (
    <div className="page-stack">
      <section className="panel domain-hero">
        <div><span className="eyebrow gold">{eyebrow}</span><h2>{title}</h2><p>{description}</p></div>
        <Icon size={28} />
      </section>
      <section className="panel">
        <div className="panel-heading">
          <div><span className="eyebrow">Backend contract</span><h3>Current data</h3></div>
          <button className="icon-button" type="button" aria-label={`Refresh ${title}`} onClick={() => void resource.refresh()}><RefreshCw size={16} /></button>
        </div>
        {resource.error ? <div className="inline-alert" role="alert">{resource.error}</div> : null}
        {table ? <RecordTable payload={resource.data} /> : <JsonSummary payload={resource.data} />}
      </section>
    </div>
  );
}

const signalsLoader = () => api.signals.history();
const modelsLoader = async () => ({
  performance: await api.models.performance(),
  weights: await api.models.weights(),
  artifacts: await api.models.artifacts(),
  votes: await api.models.votes()
});
const indicatorsLoader = () => api.analysis.indicators();
const riskLoader = () => api.analysis.risk();
const optimizationLoader = () => api.research.optimizations();
const replayLoader = async () => ({ latest_signal: await api.signals.latest(), note: "Select a signal from Signal History for a complete replay drill-down." });
const newsLoader = () => api.research.news();

export function SignalsPage() {
  return <DomainPage eyebrow="Evidence ledger" title="Signal history" description="Persisted recommendations and outcome evidence from the authoritative storage layer." icon={History} loader={signalsLoader} table />;
}

export function ModelsPage() {
  return <DomainPage eyebrow="Ensemble intelligence" title="Model observability" description="Artifacts, dynamic weights, latest votes, and measured performance in one contract view." icon={BrainCircuit} loader={modelsLoader} />;
}

export function IndicatorsPage() {
  return <DomainPage eyebrow="Technical context" title="Indicator state" description="The latest normalized features used by the strategy and risk pipeline." icon={ChartNoAxesCombined} loader={indicatorsLoader} />;
}

export function RiskPage() {
  return <DomainPage eyebrow="Safety boundary" title="Risk status" description="Eligibility gates and risk limits remain backend-owned and cannot be bypassed by this interface." icon={ShieldCheck} loader={riskLoader} />;
}

export function OptimizationPage() {
  return <DomainPage eyebrow="Research workspace" title="Optimization runs" description="Candidate thresholds and strategy profile evidence." icon={FlaskConical} loader={optimizationLoader} table />;
}

export function ReplayPage() {
  return <DomainPage eyebrow="Decision audit" title="Signal replay" description="Trace the signal, model, strategy, trade-plan, and risk decision trail." icon={Radar} loader={replayLoader} />;
}

export function NewsPage() {
  return <DomainPage eyebrow="Macro intelligence" title="News state" description="Current impact, sentiment, risk windows, and conservative fallback state." icon={Newspaper} loader={newsLoader} />;
}

export function BacktestingPage() {
  const { backend } = useBackend();
  const runsLoader = useCallback(() => api.research.backtests(), []);
  const runs = useRemoteResource(runsLoader, backend.phase === "ready");
  const [running, setRunning] = useState(false);
  const [result, setResult] = useState<Record<string, unknown> | null>(null);
  const [error, setError] = useState("");

  async function run(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    const form = new FormData(event.currentTarget);
    setRunning(true);
    setError("");
    try {
      setResult(await api.research.runBacktest({
        run_type: form.get("run_type"),
        instrument: "XAUUSD",
        timeframe: form.get("timeframe"),
        synthetic_count: Number(form.get("synthetic_count")),
        min_window: Number(form.get("min_window")),
        model_mode: "MOCK_FOR_TEST_ONLY",
        name: "desktop_research_run"
      }));
      await runs.refresh();
    } catch (reason) {
      setError(reason instanceof Error ? reason.message : String(reason));
    } finally {
      setRunning(false);
    }
  }

  return (
    <div className="page-stack">
      <section className="panel domain-hero"><div><span className="eyebrow gold">Simulation only</span><h2>Backtesting laboratory</h2><p>Run deterministic synthetic research without contacting a broker or enabling execution.</p></div><BarChart3 size={28} /></section>
      <section className="content-grid">
        <article className="panel">
          <div className="panel-heading"><div><span className="eyebrow">New research run</span><h3>Configuration</h3></div><FlaskConical size={18} /></div>
          <form className="research-form" onSubmit={(event) => void run(event)}>
            <label><span>Run type</span><select name="run_type" defaultValue="BACKTEST"><option>BACKTEST</option><option>WALK_FORWARD</option></select></label>
            <label><span>Timeframe</span><select name="timeframe" defaultValue="5m"><option>1m</option><option>5m</option><option>15m</option><option>1h</option></select></label>
            <label><span>Synthetic candles</span><input name="synthetic_count" type="number" min="100" max="2000" defaultValue="260" /></label>
            <label><span>Minimum window</span><input name="min_window" type="number" min="40" max="500" defaultValue="80" /></label>
            <button className="button primary" type="submit" disabled={running}>{running ? "Running…" : "Run simulation"}</button>
          </form>
          {error ? <div className="inline-alert" role="alert">{error}</div> : null}
          {result ? <JsonSummary payload={result} /> : null}
        </article>
        <article className="panel">
          <div className="panel-heading"><div><span className="eyebrow">Guardrails</span><h3>Research posture</h3></div><ShieldCheck size={18} /></div>
          <div className="safety-banner"><strong>Mock inference is explicit.</strong><p>This desktop form sends `MOCK_FOR_TEST_ONLY`; it cannot place or authorize an order.</p></div>
        </article>
      </section>
      <section className="panel">
        <div className="panel-heading"><div><span className="eyebrow">Run history</span><h3>Backtest ledger</h3></div><button className="icon-button" type="button" onClick={() => void runs.refresh()}><RefreshCw size={16} /></button></div>
        <RecordTable payload={runs.data} emptyTitle="No backtests recorded" />
      </section>
    </div>
  );
}
