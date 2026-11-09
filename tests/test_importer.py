import csv
from pathlib import Path

import pytest
from app.ingestion.importer import ImportConflictError, import_session

START = (
    "-- starting hand #1 (id: synthetic-hand)  Pot Limit Omaha 5 Hi (dead button) --"
)
STACKS = (
    'Player stacks: #1 "Alpha 🐣 @ synthetic_a" (50.00) | '
    '#9 "Beta @ synthetic_b" (50.00)'
)
END = "-- ending hand #1 --"


def export(tmp_path: Path, entries: list[tuple[int, str]], name: str = "a.csv") -> Path:
    path = tmp_path / name
    with path.open("w", encoding="utf-8", newline="") as file:
        writer = csv.writer(file)
        writer.writerow(["entry", "at", "order"])
        for order, entry in entries:
            writer.writerow([entry, "2026-01-01T00:00:00Z", str(order)])
    return path


def test_overlapping_reverse_exports_merge_and_preserve_sources(tmp_path: Path) -> None:
    first = export(tmp_path, [(30, END), (20, STACKS), (10, START)])
    second = export(tmp_path, [(20, STACKS), (30, END)], "b.csv")
    report = import_session([first, second], session_id="test-session")
    assert len(report.hands) == 1
    hand = report.hands[0]
    assert hand.hand_id == "synthetic-hand"
    assert hand.variant == "Pot Limit Omaha 5 Hi"
    assert hand.boundaries_valid
    assert [record.order for record in hand.records] == [10, 20, 30]
    assert len(hand.records[1].sources) == 2
    assert len(report.players) == 2
    assert report.issues == ()
    assert report.duplicate_records == 2
    assert import_session([first], session_id="test-session") == import_session(
        [first], session_id="test-session"
    )


def test_name_observations_track_renames_without_merging_ids(tmp_path: Path) -> None:
    path = export(
        tmp_path,
        [
            (
                1,
                'The player "Alpha @ synthetic_a" '
                "joined the game with a stack of 50.00.",
            ),
            (2, '"Renamed 🐣 @ synthetic_a" folds'),
            (3, '"Alpha @ synthetic_b" checks'),
        ],
    )
    report = import_session([path], session_id="s")
    assert [p.player_id.value for p in report.players] == ["synthetic_a", "synthetic_b"]
    assert [o.display_name for o in report.players[0].observations] == [
        "Alpha",
        "Renamed 🐣",
    ]
    assert report.players[1].observations[0].display_name == "Alpha"


def test_unknown_and_outside_records_are_retained(tmp_path: Path) -> None:
    path = export(
        tmp_path,
        [(1, "unrecognized outside"), (2, START), (3, "unrecognized inside"), (4, END)],
    )
    report = import_session([path], session_id="s")
    assert len(report.unknown_records) == 2
    assert report.outside_records[0].entry == "unrecognized outside"
    assert report.hands[0].records[1].entry == "unrecognized inside"
    assert report.hands[0].boundaries_valid  # Not a poker-validation claim.


@pytest.mark.parametrize(
    "entries,code",
    [
        ([(1, START)], "missing_end"),
        ([(1, END)], "orphan_end"),
        ([(1, START), (2, "-- ending hand #2 --")], "end_number_mismatch"),
        ([(1, START), (2, START), (3, END)], "nested_start"),
        ([(1, "-- starting hand malformed --")], "malformed_boundary"),
        ([(1, START), (2, END), (3, START), (4, END)], "duplicate_hand_id"),
        (
            [(1, START), (2, "Player stacks: malformed"), (3, END)],
            "malformed_player_event",
        ),
    ],
)
def test_problem_records_produce_explicit_issues(tmp_path: Path, entries, code) -> None:
    report = import_session([export(tmp_path, entries)], session_id="s")
    assert code in {issue.code for issue in report.issues}


def test_same_order_different_contents_is_not_silently_deduplicated(
    tmp_path: Path,
) -> None:
    a = export(tmp_path, [(1, START)])
    b = export(tmp_path, [(1, END)], "b.csv")
    with pytest.raises(ImportConflictError):
        import_session([a, b], session_id="s")


def test_invalid_order_and_empty_session_are_rejected(tmp_path: Path) -> None:
    path = export(tmp_path, [(1, START)])
    path.write_text(path.read_text().replace(",1\n", ",not-an-order\n"))
    with pytest.raises(ValueError, match="order"):
        import_session([path], session_id="s")
    with pytest.raises(ValueError, match="session"):
        import_session([path], session_id=" ")
