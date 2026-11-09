# PnowLogAnalyzer

A local PokerNow hand-history research application: exact chip reconstruction,
source-level replay, persistent sessions, a searchable poker metric catalog, and
explicit equity/probability models. Supports observed NLHE and PLO5 exports.

**Current release: 0.2, an end-to-end implementation checkpoint.** The full research
roadmap is not complete. See [implementation status](docs/implementation-status.md)
for tested capabilities and remaining work. No GTO recommendations are fabricated.

## Run locally

Requirements: Python 3.12+, [uv](https://docs.astral.sh/uv/), and Node.js 22+ with npm.
From the repository root:

```sh
uv python install 3.12
uv sync --locked --extra dev
npm ci --prefix frontend
npm run build --prefix frontend
uv run pnow-serve
```

Open **http://127.0.0.1:8000**. The backend serves the built React application.
API documentation: **http://127.0.0.1:8000/docs**. Stop with Ctrl+C.

The application opens without demo data. Use **Import manager** to upload CSVs.
Assign the same session label to overlapping exports of the same game. Select a
player and game variant; NLHE and PLO5 statistics are never pooled. Import reports
show new records, reconciled hands, and diagnostics. Importing the same file twice
adds no duplicate hands. Upload limits: 25 MB/file, 50 MB/import, 20 files/import.

**Export owner ID is optional.** Supply a stable player ID only when you know who
exported the log; it attributes `Your hand is` observations. Leaving it blank keeps
those cards unassigned. A display name, a fold, or a guessed identity never reveals
an opponent's hidden cards.

Data persists in `data/private/analysis.duckdb`, which Git ignores. To use a separate
database:

```sh
PNOW_DATABASE=/absolute/path/to/private.duckdb uv run pnow-serve
```

Use one application process per database. Stop the server before running a CLI
writer against that same file. Do not place private databases, logs, reports, or
screenshots in public source directories.

## What you can explore

- **Overview:** player/game/session/date filters, VPIP/PFR/3-bet, reconciled results.
- **Statistics explorer:** all 116 executable definitions; numerator, eligible
  denominator, exclusions, confidence intervals, position, starting-stack depth,
  and observed Hold'em class filters. Export the current statistics as private CSV.
- **Hand browser/replay:** all observed events, board/runouts, stacks and pot over
  time, observed cards, unknown cards, diagnostics, and source hashes/record lines.
- **Starting hands:** Hold'em 13×13 observed-class matrix with hand drill-down;
  PLO5 five-card suit/rank patterns, ace counts and broadway counts. Showdown-selected
  card observations are not an unbiased sample of dealt hands.
- **Performance:** cumulative net chips, hand-specific bb/100, observed drawdown.
  These are chips, not dollars; no chip-to-currency conversion is assumed.
- **Player comparison:** side-by-side observed tendencies with eligible samples.
- **Math lab:** NLHE/PLO5 known-hand or explicitly weighted-combination equity,
  exact or seeded Monte Carlo; draw probabilities; pot odds, closing-call EV and
  pure-bluff/MDF toy models. Ties split correctly. Expensive jobs are bounded.

## Command-line imports

The original CLI and `--vpip` interface remain available:

```sh
uv run pnow-import --session-id my-session /path/to/export.csv --vpip
uv run pnow-import --session-id my-session /path/to/first.csv /path/to/overlap.csv \
  --database data/private/analysis.duckdb --reconstruct --metrics --strict
```

`--owner PLAYER_ID` optionally attributes export-owner cards. `--json` prints the
full private report; `--metrics --json` adds the executable catalog's results.
Without `--database`, imports are in-memory. Cached histories survive restarts and
automatically rebuild when the reconstruction version changes. A session’s
**Rebuild** button also recomputes cached hands from retained sources.
Sources and source locations are retained locally for diagnosis.

Default inspection returns 0 when a report is produced, including reports with
issues; `--strict` returns 1 for unknown entries, import/VPIP exclusions, or failed
requested reconstruction checks. Input/conflict errors return 2.

## Correctness and limits

A **reconciled** hand passes the implemented action checks and exact contribution /
refund / award ledger, including feasible side-pot recipients. This does not certify
hidden winning hands, every house rule, or full poker legality. Side-pot allocations
between unlabeled awards/runouts are not invented. Partial or invalid evidence is
preserved with diagnostics. Explicit rake, ante/straddle and new log grammars are
unsupported until verified samples establish their meaning.

The legacy VPIP API uses its documented preflop-only eligibility; the broader
registry currently requires a consistent reconstructed hand. Unknown denominators
produce null/“—”, not zero. Definitions and limitations:
[metrics](docs/metrics.md), [catalog](docs/metric-catalog.md),
[domain/reconstruction](docs/reconstruction.md).

Solver output, all-in adjusted EV, range inference, and several advanced situational
families remain unavailable. See [coverage and next work](docs/implementation-status.md).

## Development and checks

```sh
uv run --extra dev pytest
uv run --extra dev ruff check .
uv run --extra dev ruff format --check .
uv run --extra dev mypy
uv run python scripts/update_metric_catalog.py --check
uv run python scripts/verify_evaluator.py
npm run check --prefix frontend
npm run format:check --prefix frontend
npm run build --prefix frontend
```

For frontend development, run `uv run pnow-serve` and `npm run dev --prefix frontend`
in separate terminals. Vite at http://127.0.0.1:5173 proxies `/api` to port 8000.
In VS Code choose `.venv/bin/python` as the interpreter.

An optional synthetic demonstration CSV can be generated with
`uv run python scripts/create_demo.py`. Import it under a clearly named **demo**
session; it is never loaded into the application automatically.

Architecture, exact serialization, and validation grades are documented in
[the reconstruction contract](docs/reconstruction.md).

This is retrospective analysis, not live assistance or automated play.
[MIT license](LICENSE).
