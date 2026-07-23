import { EmptyState } from "./EmptyState";

function findRecords(payload: unknown): Record<string, unknown>[] {
  if (Array.isArray(payload)) return payload.filter((item): item is Record<string, unknown> => Boolean(item) && typeof item === "object");
  if (!payload || typeof payload !== "object") return [];
  const object = payload as Record<string, unknown>;
  for (const preferred of ["items", "results", "signals", "orders", "runs", "events", "data", "records", "trades"]) {
    if (Array.isArray(object[preferred])) return findRecords(object[preferred]);
  }
  return [];
}

function displayValue(value: unknown): string {
  if (value === null || value === undefined || value === "") return "—";
  if (typeof value === "boolean") return value ? "Yes" : "No";
  if (typeof value === "number") return Number.isInteger(value) ? String(value) : value.toFixed(4).replace(/0+$/, "").replace(/\.$/, "");
  if (typeof value === "object") return JSON.stringify(value);
  return String(value);
}

export function RecordTable({ payload, emptyTitle = "No records yet" }: { payload: unknown; emptyTitle?: string }) {
  const rows = findRecords(payload);
  if (!rows.length) return <EmptyState title={emptyTitle} detail="The backend returned no rows for the current view." />;
  const keys = [...new Set(rows.flatMap((row) => Object.keys(row)))].slice(0, 8);
  return (
    <div className="record-table-wrap">
      <table className="record-table">
        <thead><tr>{keys.map((key) => <th key={key}>{key.replaceAll("_", " ")}</th>)}</tr></thead>
        <tbody>
          {rows.slice(0, 50).map((row, index) => (
            <tr key={String(row.id ?? row.signal_id ?? row.run_id ?? index)}>
              {keys.map((key) => <td key={key} title={displayValue(row[key])}>{displayValue(row[key])}</td>)}
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}
