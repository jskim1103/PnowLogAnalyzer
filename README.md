# PnowLogAnalyzer

A full-stack poker analytics project for parsing PokerNow hand histories, tracking player performance across sessions, studying poker probabilities, and eventually comparing decisions with solver-based strategy models.

> **Status:** Planning / pre-parser. No metrics or solver evaluations are implemented yet.

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

The implementation and setup commands will be added alongside the first code milestone. No executable application has been scaffolded yet.

## License

See [LICENSE](LICENSE).
