# Codex / AI contributor instructions

## Product intent
PnowLogAnalyzer is a learning-focused PokerNow log analyzer. Prioritize correct, explainable results and tests over a quickly generated interface.

## Architecture
- Keep PokerNow-specific parsing in `backend/app/ingestion/`; poker rules/domain models must not depend on CSV column layout.
- Keep metrics in `backend/app/stats/`, equity/probability in `backend/app/equity/`, and solver/range analysis in `backend/app/strategy/`.
- Prefer Python 3.12+, static type hints, small pure functions, Pydantic for API validation, pytest, and DuckDB for persisted analytics.
- Frontend comes after a verified parser and minimal API; use React + TypeScript + Vite.
- Document any substantial architecture change before implementing it. Avoid microservices, premature cloud infrastructure, or unneeded abstractions.

## Correctness rules
- **Never infer hidden opponent hole cards from a fold.** Distinguish observed cards from assumptions and modeled ranges.
- Do not label decisions GTO-correct without a specified game tree, ranges, stacks, positions, rake, bet sizes, and solver/model settings.
- All metrics must define eligible opportunities, numerator, denominator, sample size, and exclusions; undefined denominators return null/not available, not zero.
- Carefully reconcile blinds, forced bets, uncalled bets, all-ins, split pots, rake, side pots, run-it-twice, and incomplete logs.
- Calculate statistics for each game variant separately; No-Limit Hold'em and PLO5 have distinct evaluation rules.
- Preserve source provenance, session IDs, hand IDs, source versions, and idempotent import behavior.
- Use deterministic seeds for stochastic tests; compare hand ranks/equity with independently verified test cases.
- For EV, explicitly document assumptions: tie equity, rake, future betting, folds, and whether action closes betting.

## Workflow
1. Inspect sample logs and write tests before creating complicated ingestion logic.
2. Keep changes scoped and incremental; use a feature branch and pull request, not direct changes to main.
3. Run relevant tests and formatting/type checks locally when possible; clearly state if they were not run.
4. Include tests for edge cases and regressions, especially hand accounting and metric opportunity denominators.
5. Update `docs/metrics.md` when implementing new metrics, and `docs/roadmap.md` as milestones change.
6. Avoid committing notebooks with sensitive outputs or raw logs.

## Privacy and security
- This repository is public. Never commit private game logs, player names/aliases tied to real identities, transactions, credentials, .env files, local databases, or generated artifacts with identifying metadata.
- Store any real sample logs locally only; commit synthetic or anonymized fixtures.
- Do not delete or overwrite user work without checking the repository state.

## First task for Codex
Inspect at least one real PokerNow log supplied locally by the user. Propose the smallest typed data model and parsing tests first; then implement a CLI that imports the log and prints a validated hand count. Do not yet implement GTO analysis or a dashboard.
