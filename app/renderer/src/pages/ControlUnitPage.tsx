import { Save, ShieldCheck, SlidersHorizontal } from "lucide-react";
import { useCallback, useEffect, useRef, useState } from "react";
import { api } from "../data/apiClient";
import { useRemoteResource } from "../hooks/useRemoteResource";
import { useBackend } from "../state/BackendContext";

interface ControlConfig {
  enabled: boolean;
  allowed_sessions: Record<string, boolean>;
  allowed_directions: Record<string, boolean>;
  require_ensemble_opposite_or_tie: boolean;
  apply_to_auto: boolean;
  apply_to_manual: boolean;
  tie_policy: string;
}

export function shouldAdoptControlResponse(
  response: unknown,
  initializedResponse: unknown,
  dirty: boolean,
  saving: boolean
): boolean {
  return Boolean(response) && response !== initializedResponse && !dirty && !saving;
}

function Toggle({
  checked,
  label,
  detail,
  disabled = false,
  onChange
}: {
  checked: boolean;
  label: string;
  detail?: string;
  disabled?: boolean;
  onChange(value: boolean): void;
}) {
  return (
    <label className={disabled ? "toggle-row disabled" : "toggle-row"}>
      <span><strong>{label}</strong>{detail ? <small>{detail}</small> : null}</span>
      <input type="checkbox" checked={checked} disabled={disabled} onChange={(event) => onChange(event.target.checked)} />
      <span className="toggle-track" aria-hidden="true"><span /></span>
    </label>
  );
}

export function ControlUnitPage() {
  const { backend } = useBackend();
  const loader = useCallback(() => api.execution.control(), []);
  const resource = useRemoteResource(loader, backend.phase === "ready");
  const [draft, setDraft] = useState<ControlConfig | null>(null);
  const [dirty, setDirty] = useState(false);
  const [saving, setSaving] = useState(false);
  const [message, setMessage] = useState("");
  const initializedResponse = useRef<unknown>(null);

  useEffect(() => {
    if (!shouldAdoptControlResponse(resource.data, initializedResponse.current, dirty, saving)) return;
    const response = resource.data;
    if (!response) return;
    const config = response.config as ControlConfig | undefined;
    if (config) {
      initializedResponse.current = response;
      setDraft(structuredClone(config));
    }
  }, [resource.data, dirty, saving]);

  const update = (mutator: (current: ControlConfig) => ControlConfig) => {
    setDraft((current) => current ? mutator(current) : current);
    setDirty(true);
    setMessage("");
  };

  async function save() {
    if (!draft || saving) return;
    const submitted = structuredClone(draft);
    setSaving(true);
    try {
      const response = await api.execution.updateControl(submitted);
      const confirmed = response.config as ControlConfig;
      setDraft(confirmed);
      initializedResponse.current = response;
      setDirty(false);
      setMessage("Control Unit settings saved and confirmed by the backend.");
    } catch (reason) {
      setMessage(reason instanceof Error ? reason.message : String(reason));
    } finally {
      setSaving(false);
    }
  }

  if (!draft) return <section className="startup-panel"><span className="eyebrow gold">Control Unit</span><h2>Loading authoritative controls</h2><p>{resource.error ?? "Waiting for the backend configuration."}</p></section>;
  const sessions = Object.keys(draft.allowed_sessions);
  const directions = Object.keys(draft.allowed_directions);
  return (
    <div className="page-stack">
      <section className="panel control-banner">
        <div><span className="eyebrow gold">Eligibility layer</span><h2>Execution Control Unit</h2><p>Edits stay local until Save. Stale responses never overwrite checkbox changes that are still being edited.</p></div>
        <div className={draft.enabled ? "control-state enabled" : "control-state disabled"}><ShieldCheck size={18} /><span>{draft.enabled ? "ENABLED" : "DISABLED"}</span></div>
      </section>
      <section className="content-grid">
        <article className="panel">
          <div className="panel-heading"><div><span className="eyebrow">Master control</span><h3>Application scope</h3></div><SlidersHorizontal size={18} /></div>
          <div className="toggle-list">
            <Toggle checked={draft.enabled} label="Enable Control Unit filtering" detail="This does not enable Capital.com execution." onChange={(value) => update((current) => ({ ...current, enabled: value }))} />
            <Toggle checked={draft.apply_to_auto} label="Apply to automatic execution" onChange={(value) => update((current) => ({ ...current, apply_to_auto: value }))} />
            <Toggle checked={draft.apply_to_manual} label="Apply to manual execution" onChange={(value) => update((current) => ({ ...current, apply_to_manual: value }))} />
            <Toggle checked={draft.require_ensemble_opposite_or_tie} label="Require ensemble opposition or tie" detail="Uses the preserved directional-vote tie policy." onChange={(value) => update((current) => ({ ...current, require_ensemble_opposite_or_tie: value }))} />
          </div>
        </article>
        <article className="panel">
          <div className="panel-heading"><div><span className="eyebrow">Direction gates</span><h3>Allowed directions</h3></div><ShieldCheck size={18} /></div>
          <div className="toggle-list">
            {directions.map((direction) => <Toggle key={direction} checked={draft.allowed_directions[direction]} label={direction} onChange={(value) => update((current) => ({ ...current, allowed_directions: { ...current.allowed_directions, [direction]: value } }))} />)}
          </div>
        </article>
      </section>
      <section className="panel">
        <div className="panel-heading"><div><span className="eyebrow">Session gates</span><h3>Allowed market sessions</h3></div><span className="tag neutral">{String(resource.data?.current_session ?? "Session pending")}</span></div>
        <div className="session-grid">
          {sessions.map((session) => {
            const hardBlocked = session === "DAILY_BREAK";
            return (
              <Toggle
                key={session}
                checked={draft.allowed_sessions[session]}
                disabled={hardBlocked}
                label={session.replaceAll("_", " ")}
                detail={hardBlocked ? "Always non-trading; the hard block overrides this stored preference." : undefined}
                onChange={(value) => update((current) => ({ ...current, allowed_sessions: { ...current.allowed_sessions, [session]: value } }))}
              />
            );
          })}
        </div>
      </section>
      <div className="sticky-action-bar">
        <span>{dirty ? "Unsaved Control Unit changes" : message || "Configuration matches the backend."}</span>
        <button className="button primary" type="button" disabled={!dirty || saving} onClick={() => void save()}><Save size={15} />{saving ? "Saving…" : "Save controls"}</button>
      </div>
    </div>
  );
}
