import { useState } from "react";
import { FlaskConical, LoaderCircle } from "lucide-react";
import { post } from "../api";
import { number } from "./shared";
export default function MathLab() {
  const [holes, setHoles] = useState("");
  const [board, setBoard] = useState("");
  const [variant, setVariant] = useState("NLHE");
  const [method, setMethod] = useState("exact");
  const [rangeMode, setRangeMode] = useState(false);
  const [trials, setTrials] = useState(2000);
  const [result, setResult] = useState<{
    equities: number[];
    outcomes: number;
    assumptions: string;
    confidence_intervals: [number, number][] | null;
  } | null>(null);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");
  const [pot, setPot] = useState("");
  const [call, setCall] = useState("");
  const [equity, setEquity] = useState("");
  const [ev, setEv] = useState<{
    required_equity: string;
    call_ev: string;
  } | null>(null);
  const [outs, setOuts] = useState(9);
  const [unseen, setUnseen] = useState(47);
  const [draws, setDraws] = useState(2);
  const [prob, setProb] = useState<{
    probability: number;
    exact: string;
  } | null>(null);
  const [bet, setBet] = useState("");
  const [fold, setFold] = useState("");
  const [bluff, setBluff] = useState<{
    break_even_fold_frequency: string;
    toy_mdf: string;
    ev: string;
  } | null>(null);
  const parse = (v: string) => (v.trim() ? v.trim().split(/[\s,]+/) : []);
  return (
    <>
      <div className="notice">
        <FlaskConical size={20} />
        <div>
          <strong>Mathematics with the assumptions attached.</strong>
          <p>
            Known hands and explicit toy models. No inferred opponent cards,
            ranges, or GTO recommendations.
          </p>
        </div>
      </div>
      {error && (
        <div className="error" role="alert">
          {error}
        </div>
      )}
      <div className="lab-grid">
        <section className="panel lab-panel">
          <p className="eyebrow">01 · CARD EQUITY</p>
          <h2>
            {rangeMode
              ? "Explicit-range showdown equity"
              : "Known-hand showdown equity"}
          </h2>
          <form
            onSubmit={async (e) => {
              e.preventDefault();
              setBusy(true);
              setError("");
              setResult(null);
              try {
                setResult(
                  await post(rangeMode ? "/range-equity" : "/equity", {
                    ...(rangeMode
                      ? {
                          ranges: holes
                            .split("\n")
                            .filter((v) => v.trim())
                            .map((line) =>
                              line.split(";").map((spec) => {
                                const parts = spec.split("@");
                                if (parts.length > 2)
                                  throw new Error(
                                    "Use one @ weight per combination",
                                  );
                                return {
                                  cards: parse(parts[0]),
                                  weight: parts[1]?.trim() || "1",
                                };
                              }),
                            ),
                        }
                      : {
                          hands: holes
                            .split("\n")
                            .filter((v) => v.trim())
                            .map(parse),
                        }),
                    board: parse(board),
                    variant,
                    method,
                    trials,
                    seed: 0,
                  }),
                );
              } catch (e) {
                setError((e as Error).message);
              } finally {
                setBusy(false);
              }
            }}
          >
            <label>
              Card model
              <select
                value={rangeMode ? "range" : "known"}
                onChange={(e) => {
                  setRangeMode(e.target.value === "range");
                  setResult(null);
                }}
              >
                <option value="known">Fixed known hands</option>
                <option value="range">
                  User-supplied weighted combinations
                </option>
              </select>
            </label>
            <div className="form-row">
              <label>
                Variant
                <select
                  value={variant}
                  onChange={(e) => setVariant(e.target.value)}
                >
                  <option value="NLHE">Hold’em</option>
                  <option value="PLO5">PLO5 · exactly two hole cards</option>
                </select>
              </label>
              <label>
                Method
                <select
                  value={method}
                  onChange={(e) => setMethod(e.target.value)}
                >
                  <option value="exact">Exact enumeration</option>
                  <option value="monte_carlo">Monte Carlo · seed 0</option>
                </select>
              </label>
            </div>
            <label>
              {rangeMode
                ? "One assumed range per line"
                : "One known hand per line"}
              <textarea
                required
                rows={3}
                value={holes}
                onChange={(e) => setHoles(e.target.value)}
                placeholder={
                  rangeMode
                    ? "As Ah @ 2; Ac Ad @ 1\nKc Kd @ 1"
                    : "Use canonical cards: As Kh\nOne player per line"
                }
              />
            </label>
            {rangeMode && (
              <p className="field-help">
                Separate exact combinations with semicolons, one player per
                line. Optional @ weights are positive relative model weights,
                not observations. Card collisions are conditioned out jointly.
              </p>
            )}
            <label>
              Known board
              <input
                value={board}
                onChange={(e) => setBoard(e.target.value)}
                placeholder="e.g. 2s 3h 7c 9h"
              />
            </label>
            {method === "monte_carlo" && (
              <label>
                Samples
                <input
                  type="number"
                  min={1}
                  max={10000}
                  value={trials}
                  onChange={(e) => setTrials(Number(e.target.value))}
                />
              </label>
            )}
            <button className="primary" disabled={busy}>
              {busy ? (
                <LoaderCircle className="spinner" size={16} />
              ) : (
                <FlaskConical size={16} />
              )}
              Calculate equity
            </button>
          </form>
          {result && (
            <div className="calculation-result">
              {result.equities.map((v, i) => (
                <p key={i}>
                  <strong>
                    Player {i + 1}: {number(v * 100)}%
                  </strong>
                  {result.confidence_intervals && (
                    <small>
                      95% bound{" "}
                      {result.confidence_intervals[i]
                        .map((v) => number(v * 100, 1) + "%")
                        .join("–")}
                    </small>
                  )}
                </p>
              ))}
              <small>
                {result.outcomes} outcomes. {result.assumptions}
              </small>
            </div>
          )}
          <p className="footnote">
            Suits: c d h s · ranks: 2–9 T J Q K A. Large exact jobs are
            rejected; choose Monte Carlo. No side-pot or range equity in this
            version.
          </p>
        </section>
        <div className="lab-stack">
          <section className="panel lab-panel">
            <p className="eyebrow">02 · CALL MODEL</p>
            <h2>Pot odds & call EV</h2>
            <form
              onSubmit={async (e) => {
                e.preventDefault();
                setError("");
                try {
                  setEv(
                    await post("/call-ev", {
                      pot_before_call: pot,
                      call,
                      equity: Number(equity) / 100,
                      closes_betting: true,
                    }),
                  );
                } catch (e) {
                  setError((e as Error).message);
                }
              }}
            >
              <div className="form-row">
                <label>
                  Pot before call
                  <input
                    required
                    type="number"
                    min={0}
                    step="any"
                    value={pot}
                    onChange={(e) => setPot(e.target.value)}
                  />
                </label>
                <label>
                  Additional call
                  <input
                    required
                    type="number"
                    min="0.01"
                    step="any"
                    value={call}
                    onChange={(e) => setCall(e.target.value)}
                  />
                </label>
                <label>
                  Equity %
                  <input
                    required
                    type="number"
                    min={0}
                    max={100}
                    step="any"
                    value={equity}
                    onChange={(e) => setEquity(e.target.value)}
                  />
                </label>
              </div>
              <button className="secondary">Calculate</button>
            </form>
            {ev && (
              <div className="calculation-result">
                Required equity{" "}
                <strong>{number(Number(ev.required_equity) * 100)}%</strong> ·
                Call EV <strong>{number(ev.call_ev)} chips</strong>
              </div>
            )}
            <p className="footnote">
              One pot; no rake or future betting; call closes action. Equity is
              expected final-pot share, including ties. Folding EV is zero.
            </p>
          </section>
          <section className="panel lab-panel">
            <p className="eyebrow">03 · DRAW PROBABILITY</p>
            <h2>Hit at least one out</h2>
            <form
              onSubmit={async (e) => {
                e.preventDefault();
                setError("");
                try {
                  setProb(
                    await post("/draw-probability", { unseen, outs, draws }),
                  );
                } catch (e) {
                  setError((e as Error).message);
                }
              }}
            >
              <div className="form-row">
                <label>
                  Unseen cards
                  <input
                    type="number"
                    min={0}
                    max={52}
                    value={unseen}
                    onChange={(e) => setUnseen(Number(e.target.value))}
                  />
                </label>
                <label>
                  Clean outs
                  <input
                    type="number"
                    min={0}
                    max={52}
                    value={outs}
                    onChange={(e) => setOuts(Number(e.target.value))}
                  />
                </label>
                <label>
                  Cards to come
                  <input
                    type="number"
                    min={0}
                    max={5}
                    value={draws}
                    onChange={(e) => setDraws(Number(e.target.value))}
                  />
                </label>
              </div>
              <button className="secondary">Calculate</button>
            </form>
            {prob && (
              <div className="calculation-result">
                <strong>{number(prob.probability * 100)}%</strong> · exact{" "}
                {prob.exact}
              </div>
            )}
            <p className="footnote">
              Uniform draws without replacement. Outs are supplied assumptions;
              hitting an out does not guarantee winning.
            </p>
          </section>
          <section className="panel lab-panel">
            <p className="eyebrow">04 · PURE BLUFF MODEL</p>
            <h2>Fold equity & break-even</h2>
            <form
              onSubmit={async (e) => {
                e.preventDefault();
                setError("");
                try {
                  setBluff(
                    await post("/bluff-ev", {
                      pot,
                      bet,
                      fold_probability: Number(fold) / 100,
                      equity_when_called: 0,
                    }),
                  );
                } catch (e) {
                  setError((e as Error).message);
                }
              }}
            >
              <div className="form-row">
                <label>
                  Pot
                  <input
                    required
                    type="number"
                    min="0.01"
                    step="any"
                    value={pot}
                    onChange={(e) => setPot(e.target.value)}
                  />
                </label>
                <label>
                  Bet
                  <input
                    required
                    type="number"
                    min="0.01"
                    step="any"
                    value={bet}
                    onChange={(e) => setBet(e.target.value)}
                  />
                </label>
                <label>
                  Fold %
                  <input
                    required
                    type="number"
                    min={0}
                    max={100}
                    step="any"
                    value={fold}
                    onChange={(e) => setFold(e.target.value)}
                  />
                </label>
              </div>
              <button className="secondary">Calculate</button>
            </form>
            {bluff && (
              <div className="calculation-result">
                Break-even folds{" "}
                <strong>
                  {number(Number(bluff.break_even_fold_frequency) * 100)}%
                </strong>{" "}
                · toy MDF {number(Number(bluff.toy_mdf) * 100)}% · EV{" "}
                {number(bluff.ev)}
              </div>
            )}
            <p className="footnote">
              Heads-up, lose whenever called, no rake or future betting. MDF is
              a toy-game threshold, not a solver prescription.
            </p>
          </section>
        </div>
      </div>
    </>
  );
}
