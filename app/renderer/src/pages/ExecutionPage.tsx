import { Activity, RefreshCw, ShieldCheck, TriangleAlert } from "lucide-react";
import { useCallback, useState } from "react";
import { MetricCard } from "../components/MetricCard";
import { RecordTable } from "../components/RecordTable";
import { api } from "../data/apiClient";
import { useRemoteResource } from "../hooks/useRemoteResource";
import { useBackend } from "../state/BackendContext";

export function ExecutionPage() {
  const { backend } = useBackend();
  const statusLoader = useCallback(() => api.execution.status(), []);
  const ordersLoader = useCallback(() => api.execution.orders(), []);
  const status = useRemoteResource(statusLoader, backend.phase === "ready");
  const orders = useRemoteResource(ordersLoader, backend.phase === "ready");
  const [message, setMessage] = useState("");
  const disabled = status.data?.enabled !== true;
  return (
    <div className="page-stack">
      <section className="metric-grid">
        <MetricCard label="Execution" value={disabled ? "DISARMED" : "ENABLED"} detail="Backend master execution switch" icon={ShieldCheck} tone={disabled ? "positive" : "danger"} loading={status.loading} />
        <MetricCard label="Automation" value={status.data?.auto_execute ? "ON" : "OFF"} detail="Automatic order submission" icon={Activity} tone={status.data?.auto_execute ? "danger" : "positive"} loading={status.loading} />
        <MetricCard label="Environment" value={String(status.data?.environment ?? "DEMO")} detail="Broker account environment" icon={TriangleAlert} tone="warning" loading={status.loading} />
        <MetricCard label="Demo-only guard" value={status.data?.demo_only === false ? "OFF" : "ON"} detail="Capital.com execution safeguard" icon={ShieldCheck} tone={status.data?.demo_only === false ? "danger" : "positive"} loading={status.loading} />
      </section>
      <section className="panel">
        <div className="panel-heading">
          <div><span className="eyebrow">Execution ledger</span><h3>Orders and outcomes</h3></div>
          <div className="button-row">
            <button className="button" type="button" onClick={() => void api.execution.refreshOutcomes().then(() => { setMessage("Outcomes refreshed."); void orders.refresh(); })}><RefreshCw size={15} />Refresh outcomes</button>
          </div>
        </div>
        {message ? <div className="inline-alert success" role="status">{message}</div> : null}
        <RecordTable payload={orders.data} emptyTitle="No execution orders" />
      </section>
    </div>
  );
}
