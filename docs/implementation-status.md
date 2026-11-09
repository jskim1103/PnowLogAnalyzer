# Full implementation progress

## Scope and baseline (2026-11-09)

The full-project handoff supersedes the earlier division of responsibilities and
frontend deferral once reconstruction and API prerequisites are satisfied. Preserve
all existing parser/VPIP interfaces and tests. Baseline: 89 pytest tests, Ruff lint,
Ruff formatting, and strict mypy pass on Python 3.12.16. The feature branch contains
uncommitted work from the preceding implementation sessions; no files are discarded.

## Plan and acceptance gates

1. **Audit / stabilization**: retain the 89-test baseline. Check malformed data,
   unknown records, duplicate imports, and compatibility before refactoring.
2. **Domain / reconstruction**: source-independent immutable Hand, Action,
   decision state, board observations, card revelations, returns, awards, results,
   and provenance. Normalize all observed CSV grammar in ingestion. Pure state
   machine owns chips, streets, active players and pending betting decisions.
   Verify hand-calculated heads-up/multiway hands, returns, short all-ins, split
   awards, layered side pots, incomplete and invalid logs, and shared-prefix second
   runouts. Keep accounting reconciliation separate from complete poker legality.
3. **Persistence**: transactionally merge records in DuckDB per explicit session,
   reject conflicting orders, rebuild normalized data on parser-version changes.
   Gate: restart, duplicate import, partial-to-complete overlapping export, rollback,
   multiple sessions and same hand IDs in different sessions.
4. **Registry / statistics**: shared declarative definitions, opportunity events,
   fractions, sample/exclusion counts, Wilson intervals, variant and contextual
   filters. Input tiers are catalogued in `metric-catalog.md`. Gate: manually
   computed numerator/denominator for each family; null zero denominators; preserve
   original VPIP answers. No planned metric is advertised as implemented.
5. **Mathematics**: deterministic five-card reference evaluator, NLHE best five,
   PLO5 exactly two plus three, exact/seeded known-card equity and pot-odds/EV toy
   models. Gate: independent ranks, ties, wheel, Omaha restrictions, duplicate
   cards, exact-versus-Monte-Carlo checks and resource limits.
6. **API**: validated FastAPI endpoints for import, sessions, players, hands,
   replay, catalog, analytics and supported mathematics. Gate: API integration,
   pagination/filter validation, persistence and malformed upload tests.
7. **Frontend**: React/TS/Vite local UI connected to API, import manager, searchable
   metric catalog, filters, hand replay, observed-card exploration and cumulative
   results where accounting supports them. Gate: TypeScript/build and browser
   inspection, empty/error states, no fabricated live data.
8. **Polish / extensions**: local startup docs, synthetic demonstration, limits,
   coverage audit, benchmarks. Solver models remain unavailable until a genuine
   solver and explicit assumptions are implemented and verified.

## Architecture decisions

Keep `domain.preflop` and `stats.vpip` compatible. Add a richer Hand contract beside
that provisional contract, rather than making existing callers parse new formats.
Keep source references in a generic domain provenance type; ingestion adapters
translate existing source references. Decimal is authoritative for chip amounts.
Store exact decimal strings when serializing, not binary floats. Never attribute
`Your hand is` unless an explicitly supplied export owner identifies a participant.
Partial reveals remain observations, not assumed complete hole-card sets.

A hand has independent reconstruction, accounting and legality diagnostics. Balanced
money alone must never upgrade a hand to fully validated. Dead buttons, unsupported
rake/forced posts and unverified rules remain explicit limitations. Side-pot layers
can be derived from net contributions, but unknown source award allocation must not
be invented. Runout-indexed awards preserve only explicit run labels.

## Current checkpoint: local application 0.2

Implemented and integrated:

- The original 89-test baseline and CLI VPIP interface are preserved.
- Immutable full-hand observations/decisions/results; all-street chip ledger,
  pending turns, short-all-in rights, pot-limit caps, refunds, feasible side pots,
  partial reveals, multiple boards, UTC timestamps and source provenance.
- Transactional DuckDB multi-session imports with raw-source retention, caching,
  duplicate prevention, restart, conflict rollback and version-aware automatic/manual rebuilds.
- 116 executable registry metrics: preflop participation/opening/reraising and
  responses, blind defense, steals, isolation, immediate raise success, sizes,
  street decisions, aggression, check-responses, continuation/double/triple barrels
  and responses, showdown frequencies, observed card features and financial results.
- Player/session/variant/date, known-position, starting-stack-BB and observed NLHE
  class filters; numerator/denominator/exclusions, Wilson intervals and generated
  documentation. The original VPIP answers match all eight player/variant pairs
  from the local real sample.
- NLHE/PLO5 reference evaluation, exact and deterministic Monte Carlo equity,
  explicit weighted-combination range equity with joint blocker conditioning,
  draw probabilities, closing-call EV, pure-bluff and MDF toy models.
- Validated FastAPI import, session, player, catalog, statistics, paginated hand,
  replay, performance, observed-card and math endpoints. Local-origin mutation
  guard, bounded upload/calculation sizes, parameterized SQL and exact serialization.
- React/TS/Vite UI with eight workspace views, searchable definitions, filters,
  comparisons, persistent imports, private CSV exports, event stepping, charts,
  observed Hold'em 169 classes, PLO5 feature distributions and explicit range input.
  Fonts are bundled locally; no fabricated production data is loaded.

Verification checkpoint:

- 188 real local hands reconstruct and reconcile; five dead buttons retain
  unknown named positions and three dead-small-blind cases preserve only explicit
  BTN/BB roles. Blind-specific metrics use actual posts. No real data is committed.
- Synthetic tests cover accounting/state/side-pot/runout/card-removal/metric/math/
  database/API cases, including all 1,326 NLHE combinations mapping to 169 classes.
- Live loopback HTTP tests returned 200 for the built frontend, health, sessions,
  catalog, hands, replay, statistics, date filters and known-hand equity.
- The reference evaluator exhaustively classifies all 2,598,960 five-card hands;
  all nine category totals match independent combinatorial formulas.
- TypeScript and production build run locally; visual and browser interaction QA
  could not run because the browser runtime returned no available connections.
  This is an unresolved verification limit, not a claim that UI workflows passed
  browser tests.

## Not complete / unsupported

This is a usable implementation checkpoint, **not completion of the entire handoff**.
The following remain explicit, without placeholder numerical results:

| Remaining family | Why / next acceptance gate |
|---|---|
| New CSV grammar, antes, straddles, explicit rake, unusual forced posts | Need representative real exports and synthetic regression cases; unknown entries remain partial. |
| Full house-rule legality and pot/run award certification | Current checks validate the implemented subset and ledger, not every PokerNow rule or hidden showdown winner. Unlabeled awards are not assigned to invented pots/runs. |
| Multiple export owners within one session | Owner assignment is session-scoped. Different perspectives can conflict at the same order; preserve conflict errors until per-source private observations are modeled. |
| Broader postflop situational metrics | Probe/donk/delayed bets, floats, success frequencies and deeper opponent/opener-position contexts need separate eligibility conventions and independent fixtures. They are not executable catalog entries. |
| Per-exact-combination explorer, richer textures and draws | The 169-class matrix and PLO5 descriptive features are implemented; fine-grained card-conditioned analytics need exposure/selection-bias handling and additional tests. |
| Win-rate uncertainty, Bayesian/heuristic opponent models | Wilson frequency intervals are implemented; correlated chip-result inference and heuristic thresholds need explicit statistical models. No skill labels are invented. |
| All-in adjusted EV and multi-pot equity | Requires correctly timed all-in states, all eligible observed holdings or explicit ranges, runout allocation, and side-pot equity validation. Current equity models explicitly cover one equal pot. |
| Solver/CFR strategy and estimated EV loss | No actual game-tree solver is integrated. Requires specified stacks, ranges, rake, sizes and independently verified model output; no GTO scores are exposed. |
| Large-data query/feature optimization | Current cached Python analytics are a reference implementation. Benchmark larger supplied corpora before introducing Polars/vectorization/materialized caches. |
| Browser/end-to-end visual QA and accessibility audit | Browser connection unavailable. Run real import/replay/filter/math workflows and responsive/keyboard checks before claiming the final polish phase complete. |
| Multiple real-export certification | Only one real local session is supplied; multiple sessions/overlaps are tested synthetically. Add independent NLHE, stakes, rake and variant examples. |

## Resume order

1. Browser QA and independent review of the state machine/metric denominators.
2. More supplied real formats, including overlapping exports and NLHE sessions.
3. Broader situational opportunity features, opponent/position contexts, histogram
   and filtered performance support, then side-pot/all-in equity with observed cards.
4. Statistical inference and genuine solver research only after explicit models
   and test references exist.

No cloud deployment, authentication service, live assistance, or automatic play is
introduced. The local program is runnable from the README commands.
