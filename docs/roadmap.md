# Development roadmap

## Phase 0 — Architecture and input discovery
- [x] Select initial stack and separation of concerns.
- [ ] Inspect one or more PokerNow logs and record the actual row/action grammar.
- [ ] Catalogue tricky examples: all-ins, showdown, incomplete hand, side pot, split pot, run-it-twice, player rename, seat movement, different stakes.
- [ ] Agree on canonical player identity and duplicate-hand keys.

## Phase 1 — Ingestion and domain model
- [ ] Typed session/hand/player/action/card/result model.
- [ ] Streaming or batched import of multiple log files.
- [ ] Deterministic hand-state reconstruction and chip accounting.
- [ ] Validation, error reporting, and idempotent deduplication.
- [ ] DuckDB persistence, synthetic fixtures, and automated tests.
- [ ] CLI summary output.

**Exit criterion:** independently check sample-hand action sequences and pot/stack accounting; duplicate imports do not duplicate results.

## Phase 2 — Descriptive statistics
- [ ] VPIP, PFR, limp, RFI, 3-bet and fold-to-3-bet.
- [ ] Postflop actions, opportunities, c-bet, showdown stats.
- [ ] Position/stack/starting-hand and time-window filters.
- [ ] Win-rate and cumulative chip/profit reporting (stake aware).
- [ ] Metric registry with denominator definitions and sample sizes.

**Exit criterion:** hand-calculated test fixtures agree with every reported stat.

## Phase 3 — Probability and EV
- [ ] Hand evaluator with independently verified unit tests.
- [ ] Exact equity enumeration where practical.
- [ ] Monte Carlo equity for uncertain opponent ranges.
- [ ] Pot odds, simplified call EV, ties, confidence intervals, and variance.
- [ ] Benchmark correctness and performance.

## Phase 4 — API and dashboard
- [ ] FastAPI query endpoints, validation and pagination.
- [ ] React/TypeScript dashboard and upload workflow.
- [ ] Performance charts, 13x13 range matrix, hand replay.
- [ ] User-friendly provenance, samples, and uncertainty notes.

## Phase 5 — Advanced strategy
- [ ] Opponent range estimates with uncertainty and sample-size warnings.
- [ ] Simplified game trees / CFR experiments.
- [ ] Solver integration with explicit model assumptions and versions.
- [ ] Compare actions using counterfactual EV rather than whether a hand happened to win.

## Out of scope for v1
- Live in-game assistance or real-time overlays.
- Multi-user authentication, cloud hosting, payments.
- Claims of universal GTO correctness from incomplete logs.
