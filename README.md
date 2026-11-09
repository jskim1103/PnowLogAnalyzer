# PnowLogAnalyzer

A full-stack poker analytics project for parsing PokerNow hand histories, tracking player performance across sessions, studying poker probabilities, and eventually comparing decisions with solver-based strategy models.

> **Status:** A working CLI imports CSV exports, indexes player IDs and observed
> names, merges overlapping records, and validates hand boundaries. Optional VPIP
> reports use typed preflop observations and explicit eligibility checks. Full
> hand reconstruction and poker/accounting validation are still pending.

## Goals

- Import multiple PokerNow logs without counting duplicate hands twice.
- Reconstruct hands from actions, positions, stacks, betting rounds, and settlements.
- Track player identities across sessions with explicit aliases.
- Compute reproducible poker statistics (VPIP, PFR, 3-bet, positional and postflop metrics).
- Build a probabilistic equity and expected-value engine for learning and validation.
- Visualize cumulative results, starting-hand distributions, and hand replays.
- Eventually evaluate decisions using **explicit** ranges and solver assumptions; observed outcomes do not establish GTO correctness.

## Proposed stack

- **Backend:** Python 3.12+, FastAPI, Pydantic, pytest
- **Storage/analytics:** DuckDB, Polars
- **Probability:** Python reference implementations first; NumPy/SciPy where appropriate
- **Frontend (later):** React, TypeScript, Vite, Tailwind CSS, Recharts
- **Tooling:** uv, GitHub, VS Code, Codex

Start with a headless, tested Python parser and domain model. Do **not** build the UI before validating game reconstruction and chip accounting.

## Architecture

```text
PokerNow logs -> ingestion/parser -> normalized game model -> DuckDB
                                      |                 |
                              stats/probability <------+
                                      |
                                  FastAPI
                                      |
                               React dashboard
```

The PokerNow adapter must remain separate from the poker rules, statistical definitions, and probability implementations. Initial game support targets No-Limit Texas Hold'em; keep the schema extensible for PLO5 without pretending its hand evaluation is identical.

## First milestone: trustworthy ingestion

1. Inspect real PokerNow CSV samples (including unusual hands) before finalizing the parser.
2. Create typed models for sessions, hands, players, seats, actions, streets, and payouts.
3. Reconstruct preflop/flop/turn/river decisions in order.
4. Correctly handle blinds, incomplete hands, folds, uncalled bets, all-ins, side pots, and run-it-twice variants when present.
5. Detect duplicate logs/hands and reconcile settlements.
6. Produce a simple CLI summary and test fixtures.

See [the roadmap](docs/roadmap.md), [metrics definitions](docs/metrics.md), and [Codex instructions](AGENTS.md).

## Privacy

**Never commit raw private PokerNow logs**, identifying player mappings, payment records, local database files, or credentials. Use small synthetic or carefully anonymized fixtures in tests. Treat a public repository as permanently public, including its Git history.

## Development

Requires Python 3.12+ and uv:

```sh
uv python install 3.12
uv sync --extra dev
uv run --extra dev pytest
uv run --extra dev ruff check .
uv run --extra dev ruff format --check .
uv run --extra dev mypy
```

The `.python-version` file selects Python 3.12 for local development, and
`uv.lock` records resolved dependencies. The project environment lives in `.venv/`.
In VS Code, select `.venv/bin/python` as the Python interpreter.

## Import a session

```sh
uv run pnow-import --session-id my-session /path/to/export.csv
```

Give each real session a stable label. For overlapping exports from that same
session, pass all files together:

```sh
uv run pnow-import --session-id my-session /path/to/first.csv /path/to/second.csv
```

The summary reports player IDs and all observed names, per-variant hand counts,
valid hand boundaries, unknown entries, and import issues. A matching start/end
pair does not establish valid poker actions or chip accounting; the CLI explicitly
reports that full poker validation is not implemented. Recognized event syntax
also does not establish legal actions, correct hand ranks, or ownership of private
cards. Unrecognized entries remain available for inspection.

Add `--vpip` to calculate voluntary preflop investment for each player, separated
by NLHE/PLO5:

```sh
uv run pnow-import --session-id my-session /path/to/export.csv --vpip
```

Each row shows the percentage, numerator, eligible denominator/sample size, and
excluded participant hands. JSON includes percentages (`null` when undefined) and
hand-level exclusion reasons. See [metric definitions](docs/metrics.md) for exact
eligibility and limitations. Statistics live in `backend/app/stats/`, with one
module per metric; PokerNow parsing remains in ingestion.

Use `--strict` to exit with status 1 on unknown entries, import issues, or (when
`--vpip` is requested) metric exclusions. File,
CSV, order and overlap-conflict errors return status 2. Default inspection returns
0 when a report is produced, even if it contains issues. Use `--json` for the full
report, including raw entries and their source locations. This output contains
private player/game information; keep redirected reports outside Git or under
`data/private/`. No database or files are written by the importer.

The provisional [parser contract](docs/parser-contract.md) documents identity,
provenance, deduplication, validation scope, and the next increment.

## License

See [LICENSE](LICENSE).
