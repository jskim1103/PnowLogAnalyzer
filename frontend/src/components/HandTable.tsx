import { ChevronRight } from "lucide-react";
import type { HandPage } from "../types";
import { Card, number } from "./shared";
export default function HandTable({
  page,
  onOpen,
  compact = false,
}: {
  page: HandPage | null;
  onOpen: (s: string, id: string) => void;
  compact?: boolean;
}) {
  return (
    <div className="table-scroll">
      <table>
        <thead>
          <tr>
            <th>HAND</th>
            <th>PLAYERS</th>
            <th>BOARD</th>
            <th>POT · CHIPS</th>
            <th>STATUS</th>
            <th />
          </tr>
        </thead>
        <tbody>
          {page?.items.slice(0, compact ? 5 : 50).map((h) => (
            <tr
              key={h.session_id + h.hand_id}
              className="clickable"
              onClick={() => onOpen(h.session_id, h.hand_id)}
            >
              <td>
                <button
                  className="metric-name"
                  onClick={(e) => {
                    e.stopPropagation();
                    onOpen(h.session_id, h.hand_id);
                  }}
                >
                  #{h.number}
                </button>
                <small>
                  {h.session_id} · {h.variant}
                </small>
              </td>
              <td>
                {h.players.length} players<small>{h.players.join(", ")}</small>
              </td>
              <td>
                <div className="card-row tiny">
                  {h.board.map((c) => (
                    <Card code={c} key={c} />
                  ))}
                </div>
              </td>
              <td>{number(h.pot)}</td>
              <td>
                <span
                  className={
                    "status " + (h.status === "reconciled" ? "good" : "warn")
                  }
                >
                  {h.status}
                </span>
              </td>
              <td>
                <ChevronRight size={16} />
              </td>
            </tr>
          ))}
        </tbody>
      </table>
      {page?.total === 0 && (
        <p className="subempty">No hands match these filters.</p>
      )}
    </div>
  );
}
