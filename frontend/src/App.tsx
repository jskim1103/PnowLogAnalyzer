import { useEffect, useMemo, useState } from "react";
import {
  Activity,
  ArrowDownToLine,
  ArrowLeft,
  ArrowRight,
  BarChart3,
  BookOpen,
  ChevronRight,
  Database,
  FileUp,
  FlaskConical,
  Layers,
  LayoutDashboard,
  LoaderCircle,
  Search,
  Spade,
  Users,
  X,
} from "lucide-react";
import { api } from "./api";
import type {
  FullHand,
  HandPage,
  Metric,
  MetricResult,
  Performance,
  Player,
  Session,
  Starting,
} from "./types";

import { number, metricValue, Empty } from "./components/shared";
import ProfitChart from "./components/ProfitChart";
import HandTable from "./components/HandTable";
import Imports from "./components/Imports";
import Replay from "./components/Replay";
import MathLab from "./components/MathLab";
const evidenceLabels: Record<string, string> = {
  supported_hand: "Consistent reconstructed hand",
  known_positions: "Known table positions",
  reconciled_accounting: "Reconciled chip accounting",
  observed_nlhe_hole_cards: "Both Hold’em hole cards observed",
};

type View =
  | "overview"
  | "statistics"
  | "hands"
  | "starting"
  | "performance"
  | "opponents"
  | "lab"
  | "imports";
const nav = [
  ["overview", "Overview", LayoutDashboard],
  ["statistics", "Statistics explorer", BarChart3],
  ["hands", "Hand browser", Layers],
  ["starting", "Starting hands", Spade],
  ["performance", "Performance", Activity],
  ["opponents", "Player comparison", Users],
  ["lab", "Math lab", FlaskConical],
  ["imports", "Import manager", Database],
] as const;
export default function App() {
  const [view, setView] = useState<View>("overview");
  const [players, setPlayers] = useState<Player[]>([]);
  const [sessions, setSessions] = useState<Session[]>([]);
  const [catalog, setCatalog] = useState<Metric[]>([]);
  const [player, setPlayer] = useState("");
  const [variant, setVariant] = useState("PLO5");
  const [session, setSession] = useState("");
  const [from, setFrom] = useState("");
  const [to, setTo] = useState("");
  const [revision, setRevision] = useState(0);
  const [stats, setStats] = useState<MetricResult[]>([]);
  const [performance, setPerformance] = useState<Performance | null>(null);
  const [page, setPage] = useState<HandPage | null>(null);
  const [offset, setOffset] = useState(0);
  const [search, setSearch] = useState("");
  const [metricSearch, setMetricSearch] = useState("");
  const [category, setCategory] = useState("");
  const [detail, setDetail] = useState<Metric | null>(null);
  const [position, setPosition] = useState("");
  const [minStack, setMinStack] = useState("");
  const [maxStack, setMaxStack] = useState("");
  const [startingHand, setStartingHand] = useState("");
  const [handSort, setHandSort] = useState("newest");
  const [starting, setStarting] = useState<Starting | null>(null);
  const [selectedCell, setSelectedCell] = useState("");
  const [comparison, setComparison] = useState<MetricResult[]>([]);
  const [hand, setHand] = useState<FullHand | null>(null);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");
  useEffect(() => {
    const ctrl = new AbortController();
    setError("");
    Promise.all([
      api<Player[]>("/players", { signal: ctrl.signal }),
      api<Session[]>("/sessions", { signal: ctrl.signal }),
      api<Metric[]>("/catalog", { signal: ctrl.signal }),
    ])
      .then(([p, s, c]) => {
        setPlayers(p);
        setSessions(s);
        setCatalog(c);
        setPlayer((old) =>
          p.some((x) => x.player_id === old) ? old : (p[0]?.player_id ?? ""),
        );
      })
      .catch((e) => {
        if (e.name !== "AbortError") setError(e.message);
      });
    return () => ctrl.abort();
  }, [revision]);
  const query = useMemo(() => {
    const q = new URLSearchParams({ variant });
    if (player) q.set("player_id", player);
    if (session) q.set("session_id", session);
    if (from) q.set("date_from", from);
    if (to) q.set("date_to", to);
    return q;
  }, [player, variant, session, from, to]);
  useEffect(() => {
    if (!player) return;
    const ctrl = new AbortController();
    setBusy(true);
    setError("");
    const q = new URLSearchParams(query);
    if (position) q.set("position", position);
    if (minStack) q.set("min_stack_bb", minStack);
    if (maxStack) q.set("max_stack_bb", maxStack);
    if (startingHand && variant === "NLHE")
      q.set("starting_hand", startingHand);
    const handsQ = new URLSearchParams(query);
    handsQ.set("offset", String(offset));
    handsQ.set("search", search);
    handsQ.set("sort", handSort);
    if (startingHand && variant === "NLHE")
      handsQ.set("starting_hand", startingHand);
    Promise.all([
      api<MetricResult[]>("/stats?" + q, { signal: ctrl.signal }),
      api<Performance>("/performance?" + query, { signal: ctrl.signal }),
      api<HandPage>("/hands?" + handsQ, { signal: ctrl.signal }),
    ])
      .then(([s, p, h]) => {
        setStats(s);
        setPerformance(p);
        setPage(h);
      })
      .catch((e) => {
        if (e.name !== "AbortError") {
          setStats([]);
          setPage(null);
          setPerformance(null);
          setError(e.message);
        }
      })
      .finally(() => {
        if (!ctrl.signal.aborted) setBusy(false);
      });
    return () => ctrl.abort();
  }, [
    query,
    revision,
    offset,
    search,
    position,
    minStack,
    maxStack,
    player,
    startingHand,
    handSort,
    variant,
  ]);
  useEffect(() => {
    setOffset(0);
  }, [player, variant, session, from, to, search, startingHand, handSort]);
  useEffect(() => {
    if (view !== "statistics") {
      setPosition("");
      setMinStack("");
      setMaxStack("");
    }
    if (view !== "statistics" && view !== "hands") setStartingHand("");
  }, [view]);
  useEffect(() => {
    if (!hand && !detail) return;
    const previous = document.activeElement as HTMLElement | null;
    const dialog = document.querySelector<HTMLElement>("[role=dialog]");
    dialog?.querySelector<HTMLElement>("button,input,select,textarea")?.focus();
    function keys(e: KeyboardEvent) {
      if (e.key === "Escape") {
        setHand(null);
        setDetail(null);
      }
      if (e.key === "Tab" && dialog) {
        const focusable = Array.from(
          dialog.querySelectorAll<HTMLElement>(
            'button:not(:disabled),input,select,textarea,[tabindex="0"]',
          ),
        );
        const first = focusable[0],
          last = focusable.at(-1);
        if (e.shiftKey && document.activeElement === first) {
          e.preventDefault();
          last?.focus();
        } else if (!e.shiftKey && document.activeElement === last) {
          e.preventDefault();
          first?.focus();
        }
      }
    }
    document.addEventListener("keydown", keys);
    return () => {
      document.removeEventListener("keydown", keys);
      previous?.focus();
    };
  }, [hand, detail]);
  useEffect(() => {
    if (view !== "starting" || !player) return;
    const ctrl = new AbortController();
    api<Starting>("/starting-hands?" + query, { signal: ctrl.signal })
      .then(setStarting)
      .catch((e) => {
        if (e.name !== "AbortError") setError(e.message);
      });
    return () => ctrl.abort();
  }, [view, query, revision, player]);
  useEffect(() => {
    if (view !== "opponents") return;
    const ctrl = new AbortController();
    const q = new URLSearchParams(query);
    q.delete("player_id");
    api<MetricResult[]>("/stats?" + q, { signal: ctrl.signal })
      .then(setComparison)
      .catch((e) => {
        if (e.name !== "AbortError") setError(e.message);
      });
    return () => ctrl.abort();
  }, [view, query, revision]);
  const definitions = useMemo(
    () => new Map(catalog.map((x) => [x.id, x])),
    [catalog],
  );
  const results = useMemo(
    () => new Map(stats.map((x) => [x.metric_id, x])),
    [stats],
  );
  const current = players.find((p) => p.player_id === player);
  const filteredCatalog = catalog.filter(
    (d) =>
      (!category || d.category === category) &&
      [d.id, d.name, d.description].some((x) =>
        x.toLowerCase().includes(metricSearch.toLowerCase()),
      ),
  );
  const pickMetric = (id: string) =>
    metricValue(results.get(id), definitions.get(id));
  const openHand = async (s: string, id: string) => {
    setError("");
    try {
      setHand(
        await api<FullHand>(
          "/hands/" + encodeURIComponent(s) + "/" + encodeURIComponent(id),
        ),
      );
    } catch (e) {
      setError((e as Error).message);
    }
  };
  function download() {
    const rows = [
      [
        "Metric",
        "Player ID",
        "Variant",
        "Value",
        "Numerator",
        "Denominator",
        "Excluded",
      ],
      ...stats.map((r) => [
        r.metric_id,
        r.player_id,
        r.variant,
        r.value ?? "",
        r.numerator,
        String(r.denominator),
        String(r.excluded_hands),
      ]),
    ];
    const blob = new Blob(
      [
        rows
          .map((row) =>
            row.map((v) => '"' + v.replaceAll('"', '""') + '"').join(","),
          )
          .join("\n"),
      ],
      { type: "text/csv" },
    );
    const url = URL.createObjectURL(blob);
    const a = document.createElement("a");
    a.href = url;
    a.download = "pnow-statistics.csv";
    a.click();
    URL.revokeObjectURL(url);
  }
  return (
    <div className="app-shell">
      <aside className="sidebar">
        <a
          className="brand"
          href="#"
          onClick={(e) => {
            e.preventDefault();
            setView("overview");
          }}
        >
          <span className="brand-symbol">
            <Spade size={25} fill="currentColor" />
          </span>
          <span>
            pnow<span className="brand-dot">.</span>
            <small>HAND HISTORY ANALYTICS</small>
          </span>
        </a>
        <p className="nav-label">YOUR WORKSPACE</p>
        <nav>
          {nav.map(([id, label, Icon]) => (
            <button
              key={id}
              className={view === id ? "active" : ""}
              onClick={() => setView(id)}
            >
              <Icon size={18} />
              {label}
              {view === id && <ChevronRight className="nav-arrow" size={14} />}
            </button>
          ))}
        </nav>
        <div className="sidebar-bottom">
          <span className="live-dot" />
          Local & private
          <p>
            Observed data.
            <br />
            Explainable numbers.
          </p>
          <small>RETROSPECTIVE ANALYSIS ONLY</small>
        </div>
      </aside>
      <div className="workspace">
        <header className="topbar">
          <div className="breadcrumb">
            Workspace
            <ChevronRight size={13} />
            <strong>{nav.find((n) => n[0] === view)?.[1]}</strong>
          </div>
          <div className="topbar-right">
            <span className="local-label">
              <span className="live-dot" />
              Local workspace
            </span>
            <button
              className="primary small"
              onClick={() => setView("imports")}
            >
              <FileUp size={15} />
              Import logs
            </button>
          </div>
        </header>
        <main>
          <div className="page-heading">
            <div>
              <p className="eyebrow">THE STUDY STARTS HERE</p>
              <h1>
                {view === "overview"
                  ? "Your game, in perspective."
                  : nav.find((n) => n[0] === view)?.[1]}
              </h1>
              <p className="subtitle">
                {view === "overview"
                  ? "Turn your hand histories into a clearer understanding of your play."
                  : view === "statistics"
                    ? "Every metric, with the definition and evidence behind it."
                    : "Explore the observations behind your numbers."}
              </p>
            </div>
            {view !== "imports" && view !== "lab" && (
              <button
                className="secondary"
                onClick={download}
                disabled={!stats.length}
              >
                <ArrowDownToLine size={15} />
                Export stats
              </button>
            )}
          </div>
          {error && (
            <div className="error" role="alert">
              {error}
              <button onClick={() => setRevision((v) => v + 1)}>Retry</button>
            </div>
          )}
          {!["imports", "lab"].includes(view) && (
            <div className="filters">
              <label>
                PLAYER
                <select
                  value={player}
                  onChange={(e) => setPlayer(e.target.value)}
                >
                  <option value="" disabled>
                    Select player
                  </option>
                  {players.map((p) => (
                    <option key={p.player_id} value={p.player_id}>
                      {p.name}
                    </option>
                  ))}
                </select>
              </label>
              <label>
                GAME
                <select
                  value={variant}
                  onChange={(e) => setVariant(e.target.value)}
                >
                  <option value="PLO5">PLO5</option>
                  <option value="NLHE">Hold’em</option>
                </select>
              </label>
              <label>
                SESSION
                <select
                  value={session}
                  onChange={(e) => setSession(e.target.value)}
                >
                  <option value="">All sessions</option>
                  {sessions.map((s) => (
                    <option key={s.session_id} value={s.session_id}>
                      {s.session_id}
                    </option>
                  ))}
                </select>
              </label>
              <label>
                FROM (UTC)
                <input
                  type="date"
                  value={from}
                  onChange={(e) => setFrom(e.target.value)}
                />
              </label>
              <label>
                TO (UTC)
                <input
                  type="date"
                  value={to}
                  onChange={(e) => setTo(e.target.value)}
                />
              </label>
              {busy && <LoaderCircle className="spinner" size={18} />}
            </div>
          )}
          {!players.length && !["imports", "lab"].includes(view) ? (
            <Empty
              title="A fresh table."
              description="Import your first PokerNow export to explore player statistics, hand histories, and performance. Your data stays on this computer."
              action={() => setView("imports")}
            />
          ) : (
            <>
              {["overview", "statistics"].includes(view) &&
                Number(results.get("hands.dealt")?.value ?? 0) > 0 &&
                Number(results.get("hands.dealt")?.value ?? 0) < 30 && (
                  <div className="notice">
                    <BookOpen size={18} />
                    <div>
                      <strong>Small sample</strong>
                      <p>
                        Only {results.get("hands.dealt")?.denominator} eligible
                        hands. Use the opportunity counts and confidence
                        intervals when interpreting frequencies.
                      </p>
                    </div>
                  </div>
                )}
              {view === "overview" && (
                <>
                  <div className="stat-grid">
                    {[
                      [
                        "Eligible hands",
                        "hands.dealt",
                        "Hands in the selected game",
                      ],
                      ["VPIP", "preflop.vpip", "Voluntary preflop investment"],
                      [
                        "Preflop raise",
                        "preflop.pfr",
                        "Hands with a preflop raise",
                      ],
                      [
                        "3-bet",
                        "preflop.three_bet",
                        "Eligible reraising decisions",
                      ],
                    ].map(([label, id, note]) => (
                      <div className="stat-card" key={id}>
                        <div className="card-kicker">
                          {label}
                          <button
                            aria-label={"Definition of " + label}
                            onClick={() =>
                              setDetail(definitions.get(id) ?? null)
                            }
                          >
                            <BookOpen size={14} />
                          </button>
                        </div>
                        <strong>{pickMetric(id)}</strong>
                        <p>{note}</p>
                        <small>
                          {results.get(id)?.denominator ?? 0} observations ·{" "}
                          {results.get(id)?.excluded_hands ?? 0} excluded
                        </small>
                      </div>
                    ))}
                  </div>
                  <div className="overview-grid">
                    <section className="panel">
                      <div className="panel-heading">
                        <div>
                          <h2>The long view</h2>
                          <p>Cumulative net chips · {variant}</p>
                        </div>
                        <span className="chip">RECONCILED HANDS</span>
                      </div>
                      <div className="chart-total">
                        {number(performance?.points.at(-1)?.cumulative ?? null)}
                        <small>net chips</small>
                      </div>
                      <ProfitChart data={performance} />
                      <div className="panel-footer">
                        {performance?.points.length ?? 0} reconciled hands ·{" "}
                        {performance?.excluded ?? 0} excluded
                        <span>Chips, not currency</span>
                      </div>
                    </section>
                    <section className="panel tendencies">
                      <div className="panel-heading">
                        <div>
                          <h2>A closer look</h2>
                          <p>{current?.name} · selected sample</p>
                        </div>
                      </div>
                      {[
                        ["Limp frequency", "preflop.limp"],
                        ["Flop continuation bet", "flop.cbet"],
                        ["Flop aggression", "flop.afq"],
                        ["Went to showdown", "showdown.wtsd"],
                        ["Won at showdown", "showdown.wsd"],
                        ["Win rate · bb/100", "results.bb100"],
                      ].map(([label, id]) => (
                        <button
                          className="tendency"
                          key={id}
                          onClick={() => setDetail(definitions.get(id) ?? null)}
                        >
                          <span>{label}</span>
                          <strong>{pickMetric(id)}</strong>
                          <ChevronRight size={14} />
                        </button>
                      ))}
                      <button
                        className="text-link"
                        onClick={() => setView("statistics")}
                      >
                        Explore all {catalog.length} metrics
                        <ArrowRight size={15} />
                      </button>
                    </section>
                  </div>
                  <section className="panel">
                    <div className="panel-heading">
                      <div>
                        <h2>Back to the hands</h2>
                        <p>The evidence behind every number.</p>
                      </div>
                      <button
                        className="text-link"
                        onClick={() => setView("hands")}
                      >
                        View all
                        <ArrowRight size={15} />
                      </button>
                    </div>
                    <HandTable page={page} onOpen={openHand} compact />
                  </section>
                </>
              )}
              {view === "statistics" && (
                <section className="panel">
                  <div className="panel-heading">
                    <div>
                      <h2>
                        Metric library{" "}
                        <span className="count">{catalog.length}</span>
                      </h2>
                      <p>
                        Values are separated by game variant. A dash means no
                        eligible observations.
                      </p>
                    </div>
                  </div>
                  <div className="metric-controls">
                    <div className="search-field">
                      <Search size={17} />
                      <input
                        aria-label="Search metrics"
                        placeholder="Search metric names, definitions, or IDs…"
                        value={metricSearch}
                        onChange={(e) => setMetricSearch(e.target.value)}
                      />
                    </div>
                    <select
                      aria-label="Metric category"
                      value={category}
                      onChange={(e) => setCategory(e.target.value)}
                    >
                      <option value="">All categories</option>
                      {[...new Set(catalog.map((c) => c.category))].map((c) => (
                        <option key={c}>{c}</option>
                      ))}
                    </select>
                    <select
                      aria-label="Position filter for metrics"
                      value={position}
                      onChange={(e) => setPosition(e.target.value)}
                    >
                      <option value="">All positions</option>
                      {[
                        "BTN",
                        "BTN/SB",
                        "SB",
                        "BB",
                        "CO",
                        "HJ",
                        "UTG",
                        "UTG+1",
                        "UTG+2",
                      ].map((p) => (
                        <option key={p}>{p}</option>
                      ))}
                    </select>
                    <select
                      aria-label="Observed Hold'em starting class"
                      disabled={variant !== "NLHE"}
                      value={startingHand}
                      onChange={(e) => setStartingHand(e.target.value)}
                    >
                      <option value="">All observed classes</option>
                      {"AKQJT98765432".split("").flatMap((a, i) =>
                        "AKQJT98765432".split("").map((b, j) => {
                          const c =
                            i === j ? a + b : i < j ? a + b + "s" : b + a + "o";
                          return <option key={c}>{c}</option>;
                        }),
                      )}
                    </select>
                    <input
                      className="depth"
                      aria-label="Minimum starting stack in big blinds"
                      type="number"
                      min="0"
                      placeholder="Min BB"
                      value={minStack}
                      onChange={(e) => setMinStack(e.target.value)}
                    />
                    <input
                      className="depth"
                      aria-label="Maximum starting stack in big blinds"
                      type="number"
                      min="0"
                      placeholder="Max BB"
                      value={maxStack}
                      onChange={(e) => setMaxStack(e.target.value)}
                    />
                  </div>
                  <div className="table-scroll">
                    <table>
                      <thead>
                        <tr>
                          <th>METRIC</th>
                          <th>VALUE</th>
                          <th>NUMERATOR / DENOMINATOR</th>
                          <th>95% INTERVAL</th>
                          <th>EXCLUDED</th>
                        </tr>
                      </thead>
                      <tbody>
                        {filteredCatalog.map((d) => {
                          const row = results.get(d.id);
                          return (
                            <tr
                              key={d.id}
                              className="clickable"
                              onClick={() => setDetail(d)}
                            >
                              <td>
                                <button
                                  className="metric-name"
                                  onClick={() => setDetail(d)}
                                >
                                  {d.name}
                                </button>
                                <small>{d.category.replace("_", " ")}</small>
                              </td>
                              <td className="value-cell">
                                {metricValue(row, d)}
                              </td>
                              <td>
                                {number(
                                  row?.numerator ?? null,
                                  ["frequency", "count", "ratio"].includes(
                                    d.unit,
                                  )
                                    ? 0
                                    : 2,
                                )}{" "}
                                / {row?.denominator ?? 0}
                              </td>
                              <td>
                                {row?.confidence_interval
                                  ? row.confidence_interval
                                      .map((v) => number(v * 100, 1) + "%")
                                      .join(" – ")
                                  : "—"}
                              </td>
                              <td>{row?.excluded_hands ?? 0}</td>
                            </tr>
                          );
                        })}
                      </tbody>
                    </table>
                  </div>
                  {!filteredCatalog.length && (
                    <p className="subempty">No metrics match your search.</p>
                  )}
                </section>
              )}
              {view === "hands" && (
                <section className="panel">
                  <div className="panel-heading">
                    <div>
                      <h2>Hand histories</h2>
                      <p>
                        Step through normalized actions and inspect source
                        records.
                      </p>
                    </div>
                    <div className="search-field">
                      <Search size={17} />
                      <input
                        aria-label="Search hands"
                        placeholder="Hand number or ID"
                        value={search}
                        onChange={(e) => setSearch(e.target.value)}
                      />
                    </div>
                  </div>
                  <div className="metric-controls">
                    <select
                      aria-label="Sort hands"
                      value={handSort}
                      onChange={(e) => setHandSort(e.target.value)}
                    >
                      <option value="newest">Newest first</option>
                      <option value="oldest">Oldest first</option>
                      <option value="pot_desc">Largest pot first</option>
                      <option value="pot_asc">Smallest pot first</option>
                    </select>
                    {startingHand && variant === "NLHE" && (
                      <button
                        className="secondary small"
                        onClick={() => setStartingHand("")}
                      >
                        Observed {startingHand} · clear filter
                      </button>
                    )}
                  </div>
                  <HandTable page={page} onOpen={openHand} />
                  <div className="pagination">
                    <span>{page?.total ?? 0} hands</span>
                    <button
                      className="secondary small"
                      disabled={!offset}
                      onClick={() => setOffset((v) => Math.max(0, v - 50))}
                    >
                      <ArrowLeft size={14} />
                      Previous
                    </button>
                    <button
                      className="secondary small"
                      disabled={offset + 50 >= (page?.total ?? 0)}
                      onClick={() => setOffset((v) => v + 50)}
                    >
                      Next
                      <ArrowRight size={14} />
                    </button>
                  </div>
                </section>
              )}
              {view === "performance" && (
                <>
                  <div className="stat-grid">
                    <div className="stat-card">
                      <div className="card-kicker">Net chips</div>
                      <strong>
                        {number(performance?.points.at(-1)?.cumulative ?? null)}
                      </strong>
                      <p>Reconciled results only</p>
                    </div>
                    <div className="stat-card">
                      <div className="card-kicker">bb / 100</div>
                      <strong>{number(performance?.bb100 ?? null)}</strong>
                      <p>Hand-specific big blinds</p>
                    </div>
                    <div className="stat-card">
                      <div className="card-kicker">Maximum drawdown</div>
                      <strong>
                        {number(performance?.max_drawdown ?? null)}
                      </strong>
                      <p>Observed peak-to-trough chips</p>
                    </div>
                    <div className="stat-card">
                      <div className="card-kicker">Sample</div>
                      <strong>{performance?.points.length ?? 0}</strong>
                      <p>
                        {performance?.excluded ?? 0} unreconciled hands excluded
                      </p>
                    </div>
                  </div>
                  <section className="panel">
                    <div className="panel-heading">
                      <h2>Cumulative net chips</h2>
                      <span className="chip">{variant}</span>
                    </div>
                    <ProfitChart data={performance} />
                    <p className="footnote">
                      Observed results do not establish decision quality. All-in
                      adjusted EV is unavailable until eligible pots and known
                      cards support it.
                    </p>
                  </section>
                </>
              )}
              {view === "starting" && (
                <section className="panel">
                  <div className="panel-heading">
                    <div>
                      <h2>Observed starting hands</h2>
                      <p>
                        {variant === "NLHE"
                          ? `${starting?.observed ?? 0} observed / ${starting?.eligible_dealt ?? 0} dealt`
                          : "PLO5 has five hole cards; a Hold’em matrix does not describe its starting-hand space."}
                      </p>
                    </div>
                  </div>
                  {variant === "NLHE" ? (
                    <>
                      <div className="matrix">
                        {"AKQJT98765432".split("").flatMap((a, i) =>
                          "AKQJT98765432".split("").map((b, j) => {
                            const key =
                              i === j
                                ? a + b
                                : i < j
                                  ? a + b + "s"
                                  : b + a + "o";
                            const cell = starting?.cells.find(
                              (c) => c.hand_class === key,
                            );
                            return (
                              <button
                                key={key}
                                className={
                                  selectedCell === key ? "selected" : ""
                                }
                                style={{
                                  background: cell
                                    ? `rgba(40,119,94,${Math.min(0.85, 0.16 + (cell.observations / Math.max(1, starting?.observed ?? 1)) * 3)})`
                                    : undefined,
                                }}
                                onClick={() => setSelectedCell(key)}
                                title={
                                  cell
                                    ? `${key}: ${cell.observations} observations`
                                    : `${key}: unobserved`
                                }
                              >
                                {key}
                                <small>{cell?.observations ?? "—"}</small>
                              </button>
                            );
                          }),
                        )}
                      </div>
                      {selectedCell && (
                        <div className="cell-detail">
                          <strong>{selectedCell}</strong>
                          {(() => {
                            const c = starting?.cells.find(
                              (c) => c.hand_class === selectedCell,
                            );
                            return c ? (
                              <span>
                                {c.observations} observed · VPIP{" "}
                                {number(
                                  (c.voluntary / c.observations) * 100,
                                  1,
                                )}
                                % · PFR{" "}
                                {number((c.raised / c.observations) * 100, 1)}%
                                · Net {number(c.net)} chips
                              </span>
                            ) : (
                              <span>No observed cards for this class.</span>
                            );
                          })()}
                        </div>
                      )}
                      <div className="metric-controls">
                        {selectedCell && (
                          <button
                            className="secondary small"
                            onClick={() => {
                              setStartingHand(selectedCell);
                              setView("hands");
                            }}
                          >
                            Browse observed {selectedCell} hands
                          </button>
                        )}
                      </div>
                      <p className="footnote">{starting?.note}</p>
                    </>
                  ) : (
                    <>
                      <div className="table-scroll">
                        <table>
                          <thead>
                            <tr>
                              <th>OBSERVED FEATURE</th>
                              <th>STRUCTURE / COUNT</th>
                              <th>HANDS</th>
                              <th>OBSERVED FREQUENCY</th>
                            </tr>
                          </thead>
                          <tbody>
                            {(starting?.features ?? []).map((f) => (
                              <tr key={f.feature + f.value}>
                                <td>{f.feature.replaceAll("_", " ")}</td>
                                <td>{f.value}</td>
                                <td>{f.observations}</td>
                                <td>
                                  {number(
                                    (f.observations /
                                      Math.max(1, starting?.observed ?? 1)) *
                                      100,
                                    1,
                                  )}
                                  %
                                </td>
                              </tr>
                            ))}
                          </tbody>
                        </table>
                      </div>
                      <p className="footnote">
                        {starting?.observed ?? 0} complete observed five-card
                        hands / {starting?.eligible_dealt ?? 0} dealt. Suit and
                        rank patterns are multiplicities, not strength scores.
                        Observed showdowns can be a biased sample.
                      </p>
                    </>
                  )}
                </section>
              )}
              {view === "opponents" && (
                <section className="panel">
                  <div className="panel-heading">
                    <div>
                      <h2>Same game. Different tendencies.</h2>
                      <p>
                        Observed frequencies for the selected game, sessions,
                        and dates. No inferred ranges.
                      </p>
                    </div>
                  </div>
                  <div className="table-scroll">
                    <table>
                      <thead>
                        <tr>
                          <th>PLAYER</th>
                          {[
                            "hands.dealt",
                            "preflop.vpip",
                            "preflop.pfr",
                            "preflop.three_bet",
                            "flop.cbet",
                            "results.bb100",
                          ].map((id) => (
                            <th key={id}>{definitions.get(id)?.name ?? id}</th>
                          ))}
                        </tr>
                      </thead>
                      <tbody>
                        {players.map((p) => (
                          <tr key={p.player_id}>
                            <td>
                              <button
                                className="metric-name"
                                onClick={() => {
                                  setPlayer(p.player_id);
                                  setView("overview");
                                }}
                              >
                                {p.name}
                              </button>
                              <small>{p.player_id}</small>
                            </td>
                            {[
                              "hands.dealt",
                              "preflop.vpip",
                              "preflop.pfr",
                              "preflop.three_bet",
                              "flop.cbet",
                              "results.bb100",
                            ].map((id) => (
                              <td
                                key={id}
                                title={
                                  "Eligible sample: " +
                                  (comparison.find(
                                    (r) =>
                                      r.player_id === p.player_id &&
                                      r.metric_id === id,
                                  )?.denominator ?? 0)
                                }
                              >
                                {metricValue(
                                  comparison.find(
                                    (r) =>
                                      r.player_id === p.player_id &&
                                      r.metric_id === id,
                                  ),
                                  definitions.get(id),
                                )}
                                <small>
                                  n ={" "}
                                  {comparison.find(
                                    (r) =>
                                      r.player_id === p.player_id &&
                                      r.metric_id === id,
                                  )?.denominator ?? 0}
                                </small>
                              </td>
                            ))}
                          </tr>
                        ))}
                      </tbody>
                    </table>
                  </div>
                </section>
              )}
              {view === "imports" && (
                <Imports
                  sessions={sessions}
                  onDone={() => setRevision((r) => r + 1)}
                  onError={setError}
                />
              )}
              {view === "lab" && <MathLab />}
            </>
          )}
          <footer className="workspace-footer">
            <span>
              <Spade size={12} />
              PnowLogAnalyzer
            </span>
            <span>Observe. Understand. Improve.</span>
            <span>Source-traceable · Local-first</span>
          </footer>
        </main>
      </div>
      {detail && (
        <div className="modal-backdrop" onClick={() => setDetail(null)}>
          <section
            className="definition-modal"
            role="dialog"
            aria-modal="true"
            aria-label="Metric definition"
            onClick={(e) => e.stopPropagation()}
          >
            <button
              className="close"
              aria-label="Close metric definition"
              onClick={() => setDetail(null)}
            >
              <X />
            </button>
            <p className="eyebrow">{detail.category}</p>
            <h2>{detail.name}</h2>
            <p>{detail.description}</p>
            <code>{detail.formula}</code>
            <dl>
              <dt>Numerator</dt>
              <dd>{detail.numerator}</dd>
              <dt>Eligible denominator</dt>
              <dd>{detail.denominator}</dd>
              <dt>Required evidence</dt>
              <dd>
                {detail.required_data
                  .map((key) => evidenceLabels[key] ?? key)
                  .join(", ")}
              </dd>
              <dt>Assumptions</dt>
              <dd>{detail.assumptions}</dd>
            </dl>
            <p className="footnote">
              Zero eligible observations means unavailable, not zero. Registry
              metrics currently require a consistent reconstructed hand; legacy
              CLI VPIP has its documented preflop-only eligibility.
            </p>
          </section>
        </div>
      )}
      {hand && <Replay hand={hand} onClose={() => setHand(null)} />}
    </div>
  );
}
