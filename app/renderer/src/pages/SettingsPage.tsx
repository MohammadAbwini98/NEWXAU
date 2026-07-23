import { KeyRound, MonitorCog, RotateCw, ShieldCheck, Trash2 } from "lucide-react";
import { useEffect, useState, type FormEvent } from "react";
import type { AppearanceMode } from "../../../shared/contracts";
import { useBackend } from "../state/BackendContext";
import { useTheme } from "../state/ThemeContext";

const secretLabels: Record<string, string> = {
  CAPITALCOM_API_KEY: "Capital.com API key",
  CAPITALCOM_IDENTIFIER: "Capital.com identifier",
  CAPITALCOM_PASSWORD: "Capital.com password",
  POSTGRES_DSN: "PostgreSQL DSN",
  TELEGRAM_BOT_TOKEN: "Telegram bot token",
  TELEGRAM_CHAT_ID: "Telegram chat ID"
};

export function SettingsPage() {
  const { appearance, setAppearance } = useTheme();
  const { backend, restart } = useBackend();
  const [secretStatus, setSecretStatus] = useState<Record<string, boolean>>({});
  const [secretName, setSecretName] = useState("CAPITALCOM_API_KEY");
  const [secretValue, setSecretValue] = useState("");
  const [message, setMessage] = useState("");

  const refreshStatus = () => void window.newxau.secrets.status().then(setSecretStatus);
  useEffect(refreshStatus, []);

  async function saveSecret(event: FormEvent) {
    event.preventDefault();
    if (!secretValue) return;
    await window.newxau.secrets.set(secretName, secretValue);
    setSecretValue("");
    setMessage(`${secretLabels[secretName]} saved with Windows encryption.`);
    refreshStatus();
  }

  return (
    <div className="page-stack">
      <section className="content-grid">
        <article className="panel">
          <div className="panel-heading"><div><span className="eyebrow">Appearance</span><h3>Desktop experience</h3></div><MonitorCog size={18} /></div>
          <fieldset className="segmented-field">
            <legend>Color theme</legend>
            {(["light", "dark", "system"] as AppearanceMode[]).map((mode) => (
              <button className={appearance === mode ? "active" : ""} type="button" key={mode} onClick={() => setAppearance(mode)}>{mode}</button>
            ))}
          </fieldset>
          <div className="settings-row">
            <span><strong>Python backend</strong><small>{backend.message}</small></span>
            <button className="button" type="button" onClick={() => void restart()}><RotateCw size={15} />Restart</button>
          </div>
        </article>
        <article className="panel">
          <div className="panel-heading"><div><span className="eyebrow">Safety posture</span><h3>Execution defaults</h3></div><ShieldCheck size={18} /></div>
          <div className="safety-banner">
            <strong>Automated execution is not enabled by the desktop.</strong>
            <p>Capital execution remains OFF and demo-only unless the existing backend configuration and every eligibility gate explicitly allow it.</p>
          </div>
        </article>
      </section>
      <section className="panel">
        <div className="panel-heading"><div><span className="eyebrow">Protected credentials</span><h3>Windows-encrypted secret store</h3></div><KeyRound size={18} /></div>
        <p className="panel-intro">Secret values are sent directly to the Electron main process. The renderer can only see whether a value exists.</p>
        <form className="secret-form" onSubmit={(event) => void saveSecret(event)}>
          <label><span>Credential</span><select value={secretName} onChange={(event) => setSecretName(event.target.value)}>{Object.entries(secretLabels).map(([name, label]) => <option key={name} value={name}>{label}</option>)}</select></label>
          <label><span>New value</span><input type="password" autoComplete="new-password" value={secretValue} onChange={(event) => setSecretValue(event.target.value)} placeholder={secretStatus[secretName] ? "Stored · enter to replace" : "Not configured"} /></label>
          <button className="button primary" type="submit" disabled={!secretValue}>Save securely</button>
          {secretStatus[secretName] ? <button className="button danger" type="button" onClick={() => void window.newxau.secrets.remove(secretName).then(refreshStatus)}><Trash2 size={15} />Remove</button> : null}
        </form>
        {message ? <div className="inline-alert success" role="status">{message}</div> : null}
      </section>
    </div>
  );
}
