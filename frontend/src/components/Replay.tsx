import { useState, useMemo } from "react";
import { ArrowLeft, ArrowRight, Spade, X } from "lucide-react";
import type { FullHand } from "../types";
import { Card, number } from "./shared";
export default function Replay({
  hand,
  onClose,
}: {
  hand: FullHand;
  onClose: () => void;
}) {
  const [step, setStep] = useState(0);
  const events = hand.history.events;
  const state = useMemo(() => {
    const players = new Map(
      hand.history.players.map((p) => [
        p.player_id.value,
        {
          ...p,
          stack: Number(p.starting_stack),
          committed: 0,
          folded: false,
          cards: [] as string[],
        },
      ]),
    );
    let pot = 0;
    const boards = new Map<number, string[]>();
    let anonymous: string[] = [];
    for (const e of events.slice(0, step + 1)) {
      const p = e.player_id ? players.get(e.player_id.value) : undefined;
      if (e.kind === "board") {
        boards.set(
          e.run ?? 1,
          e.cards.map((c) => c.code),
        );
        if ((e.run ?? 1) === 1) players.forEach((p) => (p.committed = 0));
      }
      if (p) {
        if (
          ["small_blind", "big_blind", "call", "bet", "raise"].includes(e.kind)
        ) {
          const delta = e.street_total
            ? Number(e.amount) - p.committed
            : Number(e.amount);
          p.stack -= delta;
          p.committed += delta;
          pot += delta;
        }
        if (e.kind === "return") {
          p.stack += Number(e.amount);
          p.committed -= Number(e.amount);
          pot -= Number(e.amount);
        }
        if (e.kind === "award") {
          p.stack += Number(e.amount);
          pot -= Number(e.amount);
        }
        if (e.kind === "fold") p.folded = true;
        if (["show", "private_cards"].includes(e.kind))
          p.cards = [...new Set([...p.cards, ...e.cards.map((c) => c.code)])];
      } else if (e.kind === "private_cards")
        anonymous = e.cards.map((c) => c.code);
    }
    return {
      players: [...players.values()],
      pot,
      boards: [...boards],
      anonymous,
    };
  }, [hand, step, events]);
  return (
    <div className="modal-backdrop">
      <section
        className="replay-modal"
        role="dialog"
        aria-modal="true"
        aria-label={"Replay hand " + hand.history.number}
      >
        <div className="replay-heading">
          <div>
            <p className="eyebrow">
              {hand.history.session_id} · {hand.history.variant}
            </p>
            <h2>Hand #{hand.history.number}</h2>
          </div>
          <button className="close" aria-label="Close replay" onClick={onClose}>
            <X />
          </button>
        </div>
        <div className="replay-grid">
          <div>
            <div className="poker-table">
              <div className="table-center">
                <span className="table-logo">
                  <Spade size={18} />
                  PNOW
                </span>
                <strong>
                  Pot {number(Math.abs(state.pot) < 0.00001 ? 0 : state.pot)}
                </strong>
                {state.boards.map(([run, cards]) => (
                  <div key={run}>
                    <small>{run === 2 ? "SECOND RUN" : ""}</small>
                    <div className="card-row">
                      {cards.map((c) => (
                        <Card key={c} code={c} />
                      ))}
                    </div>
                  </div>
                ))}
              </div>
              {state.players.map((p, i) => {
                const angle =
                  (i / state.players.length) * Math.PI * 2 - Math.PI / 2;
                return (
                  <div
                    className={"seat " + (p.folded ? "folded" : "")}
                    key={p.player_id.value}
                    style={{
                      left: `${50 + 43 * Math.cos(angle)}%`,
                      top: `${50 + 43 * Math.sin(angle)}%`,
                    }}
                  >
                    <small>
                      SEAT {p.seat}{" "}
                      {hand.history.button?.value === p.player_id.value
                        ? "· BUTTON"
                        : ""}
                    </small>
                    <strong>{p.display_name}</strong>
                    <span>
                      {number(p.stack)} chips {p.folded ? "· FOLDED" : ""}
                    </span>
                    <div className="card-row tiny">
                      {p.cards.length ? (
                        p.cards.map((c) => <Card key={c} code={c} />)
                      ) : (
                        <span className="unknown-cards">Cards unknown</span>
                      )}
                    </div>
                  </div>
                );
              })}
            </div>
            <div className="replay-controls">
              <button
                className="secondary"
                disabled={!step}
                onClick={() => setStep((s) => s - 1)}
              >
                <ArrowLeft size={16} />
                Previous
              </button>
              <input
                aria-label="Replay event"
                type="range"
                min={0}
                max={events.length - 1}
                value={step}
                onChange={(e) => setStep(Number(e.target.value))}
              />
              <button
                className="primary"
                disabled={step >= events.length - 1}
                onClick={() => setStep((s) => s + 1)}
              >
                Next
                <ArrowRight size={16} />
              </button>
            </div>
            <p className="event-caption">{events[step]?.raw}</p>
            {state.anonymous.length > 0 && (
              <div className="anonymous">
                <small>EXPORT OWNER UNASSIGNED</small>
                <div className="card-row tiny">
                  {state.anonymous.map((c) => (
                    <Card key={c} code={c} />
                  ))}
                </div>
              </div>
            )}
            <p className="footnote">
              Replay uses normalized observations. Authoritative amounts are
              exact decimals in the backend; this display rounds to two places.
            </p>
          </div>
          <div className="timeline">
            <h3>Action timeline</h3>
            {events.map((e, i) => (
              <button
                className={i === step ? "selected" : ""}
                key={e.order}
                onClick={() => setStep(i)}
              >
                <small>
                  {i + 1} · {e.street ?? e.kind.replaceAll("_", " ")}
                </small>
                <span>{e.raw}</span>
              </button>
            ))}
          </div>
        </div>
        {hand.diagnostics.length > 0 && (
          <details className="diagnostics">
            <summary>
              {hand.diagnostics.length} reconstruction diagnostics
            </summary>
            {hand.diagnostics.map((d, i) => (
              <p key={i}>
                <strong>{d.code}</strong> · {d.message}
              </p>
            ))}
          </details>
        )}
        <details className="diagnostics">
          <summary>Source provenance for selected event</summary>
          {events[step]?.sources.map((s, i) => (
            <p key={i}>
              File SHA-256 <code>{s.file_sha256}</code>
              <br />
              Record {s.record_number}, lines {s.line_start}–{s.line_end}
            </p>
          ))}
        </details>
      </section>
    </div>
  );
}
