import { FileUp, Spade } from "lucide-react";
import type { Metric, MetricResult } from "../types";
export const number = (
  value: string | number | null | undefined,
  digits = 2,
) =>
  value == null
    ? "—"
    : Number(value).toLocaleString(undefined, {
        maximumFractionDigits: digits,
        minimumFractionDigits: digits,
      });
export function metricValue(
  row: MetricResult | undefined,
  definition: Metric | undefined,
) {
  if (row?.value == null) return "—";
  return definition?.unit === "frequency"
    ? number(Number(row.value) * 100, 1) + "%"
    : number(row.value, definition?.unit === "count" ? 0 : 2);
}
export function Card({ code }: { code: string }) {
  const suit: { [key: string]: string } = { c: "♣", d: "♦", h: "♥", s: "♠" };
  return (
    <span className={"playing-card " + ("dh".includes(code[1]) ? "red" : "")}>
      {code[0] === "T" ? "10" : code[0]}
      <small>{suit[code[1]]}</small>
    </span>
  );
}
export function Empty({
  title,
  description,
  action,
}: {
  title: string;
  description: string;
  action?: () => void;
}) {
  return (
    <div className="empty">
      <div className="empty-icon">
        <Spade size={30} />
      </div>
      <h2>{title}</h2>
      <p>{description}</p>
      {action && (
        <button className="primary" onClick={action}>
          <FileUp size={16} />
          Import hand histories
        </button>
      )}
    </div>
  );
}
