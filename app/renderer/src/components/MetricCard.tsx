import type { LucideIcon } from "lucide-react";

export function MetricCard({
  label,
  value,
  detail,
  icon: Icon,
  tone = "neutral",
  loading = false
}: {
  label: string;
  value: string;
  detail: string;
  icon: LucideIcon;
  tone?: "neutral" | "gold" | "positive" | "warning" | "danger";
  loading?: boolean;
}) {
  return (
    <article className={`metric-card tone-${tone}`}>
      <div className="metric-icon"><Icon size={18} /></div>
      <span>{label}</span>
      {loading ? <div className="skeleton metric-skeleton" /> : <strong>{value}</strong>}
      <p>{detail}</p>
    </article>
  );
}
