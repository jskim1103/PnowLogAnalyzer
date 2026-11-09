"""Headless PokerNow import and source-inspection interface."""

import argparse
import json
import sys
from collections import Counter
from dataclasses import asdict
from pathlib import Path

from pydantic import TypeAdapter

from app.database.store import Store
from app.domain.hands import Hand
from app.domain.players import PlayerId
from app.ingestion.hands import normalize_session
from app.ingestion.importer import import_session
from app.ingestion.preflop import extract_preflop_hands
from app.reconstruction.engine import reconstruct
from app.stats.analytics import MetricResult, compute_statistics
from app.stats.registry import REGISTRY
from app.stats.vpip import calculate_vpip


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="Inspect overlapping PokerNow exports from one session."
    )
    parser.add_argument(
        "files", nargs="+", type=Path, help="CSV exports from one session"
    )
    parser.add_argument(
        "--session-id", required=True, help="Explicit stable session label"
    )
    parser.add_argument(
        "--json", action="store_true", help="Print private detailed JSON"
    )
    parser.add_argument(
        "--strict", action="store_true", help="Fail on issues or unrecognized entries"
    )
    parser.add_argument(
        "--vpip", action="store_true", help="Report per-player VPIP by game variant"
    )
    parser.add_argument(
        "--database", type=Path, help="Persist session in this local DuckDB"
    )
    parser.add_argument("--owner", help="Explicit export-owner player ID")
    parser.add_argument(
        "--reconstruct",
        action="store_true",
        help="Check all streets and chip settlement",
    )
    parser.add_argument(
        "--metrics", action="store_true", help="Compute the executable metric catalog"
    )
    args = parser.parse_args(argv)
    try:
        outcome = None
        if args.database:
            store = Store(args.database)
            outcome = store.import_paths(
                args.files, session_id=args.session_id, owner=args.owner
            )
            report = next(r for r in store.reports() if r.session_id == args.session_id)
        else:
            report = import_session(args.files, session_id=args.session_id)
        reconstructed: tuple[Hand, ...] = ()
        if args.reconstruct or args.metrics:
            if args.database:
                reconstructed = store.hands(session_id=args.session_id)
            else:
                reconstructed = tuple(
                    reconstruct(h)
                    for h in normalize_session(
                        report, owner=PlayerId(args.owner) if args.owner else None
                    )
                )
        metrics = compute_statistics(reconstructed) if args.metrics else ()
        vpip = calculate_vpip(extract_preflop_hands(report)) if args.vpip else None
    except (OSError, ValueError) as exc:
        print(f"Import failed: {exc}", file=sys.stderr)
        return 2
    if args.json:
        payload = asdict(report)
        payload["validation_scope"] = (
            "reconstruction_and_accounting"
            if args.reconstruct or args.metrics
            else "hand_boundaries_only"
        )
        payload["fully_validated_hands"] = 0
        if outcome is not None:
            payload["persistence"] = asdict(outcome)
        if args.reconstruct or args.metrics:
            payload["reconstructed_hands"] = TypeAdapter(tuple[Hand, ...]).dump_python(
                reconstructed, mode="json"
            )
        if args.metrics:
            payload["metrics"] = TypeAdapter(tuple[MetricResult, ...]).dump_python(
                metrics, mode="json"
            )
        if vpip is not None:
            payload["vpip"] = {
                "results": [
                    {
                        **asdict(row),
                        "sample_size": row.sample_size,
                        "percentage": row.percentage,
                    }
                    for row in vpip.results
                ],
                "excluded_hands": [asdict(hand) for hand in vpip.excluded_hands],
            }
        print(json.dumps(payload, ensure_ascii=False, indent=2))
    else:
        print(f"Session: {report.session_id}")
        if outcome is not None:
            print(
                f"Persisted: {outcome.new_records} new records, "
                f"{outcome.new_sources} new files"
            )
        if args.reconstruct or args.metrics:
            print(
                f"Accounting reconciled: "
                f"{sum(h.accounting_reconciled for h in reconstructed)}"
                f"/{len(reconstructed)}"
            )
            print(
                f"Action consistent: "
                f"{sum(h.action_consistent for h in reconstructed)}"
                f"/{len(reconstructed)}"
            )
        if args.metrics:
            print(f"Executable metrics: {len(REGISTRY)} (use --json for full results)")
        print(f"Unique records: {len(report.records)}")
        print(f"Duplicate records merged: {report.duplicate_records}")
        print(f"Players: {len(report.players)}")
        for player in report.players:
            observed_names = list(
                dict.fromkeys(
                    observation.display_name for observation in player.observations
                )
            )
            # JSON quoting prevents names from injecting lines into the summary.
            print(
                f"  {player.player_id.value}: "
                f"{json.dumps(observed_names, ensure_ascii=False)}"
            )
        print(f"Hands detected: {len(report.hands)}")
        print(f"Valid hand boundaries: {sum(h.boundaries_valid for h in report.hands)}")
        print("Fully validated poker hands: 0 (not implemented)")
        for variant, count in sorted(Counter(h.variant for h in report.hands).items()):
            print(f"  {variant}: {count}")
        print(f"Unrecognized records: {len(report.unknown_records)}")
        print(f"Import issues: {len(report.issues)}")
        for issue in report.issues:
            print(f"  order {issue.order}: {issue.code}: {issue.message}")
        if vpip is not None:
            print("VPIP (voluntary preflop hands / eligible dealt hands):")
            labels = {
                p.player_id: p.observations[-1].display_name for p in report.players
            }
            for row in vpip.results:
                percent = (
                    f"{row.percentage:.2f}%" if row.percentage is not None else "N/A"
                )
                name = json.dumps(labels[row.player_id], ensure_ascii=False)
                print(
                    f"  {row.variant} | {name} ({row.player_id.value}): "
                    f"{percent} ({row.numerator}/{row.denominator}; "
                    f"sample {row.sample_size}; excluded {row.excluded})"
                )
            print(f"VPIP excluded hands: {len(vpip.excluded_hands)}")
            for hand in vpip.excluded_hands:
                print(f"  {hand.hand_id}: {', '.join(hand.reasons)}")
    failed = bool(
        report.issues
        or report.unknown_records
        or (vpip is not None and vpip.excluded_hands)
        or any(not h.action_consistent for h in reconstructed)
    )
    return 1 if args.strict and failed else 0


if __name__ == "__main__":
    raise SystemExit(main())
