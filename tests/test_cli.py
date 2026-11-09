import csv
import json
from pathlib import Path

from app.cli import main


def sample(tmp_path: Path) -> Path:
    path = tmp_path / "synthetic.csv"
    with path.open("w", newline="", encoding="utf-8") as file:
        writer = csv.writer(file)
        writer.writerow(["entry", "at", "order"])
        entries = [
            "-- starting hand #1 (id: synthetic)  "
            "Pot Limit Omaha 5 Hi (dead button) --",
            'Player stacks: #1 "Alpha 🐣 @ synthetic_a" (50.00)',
            "-- ending hand #1 --",
        ]
        for order, entry in enumerate(entries, 1):
            writer.writerow([entry, "2026-01-01T00:00:00Z", order])
    return path


def test_cli_prints_scoped_counts_and_player_ids(tmp_path, capsys) -> None:
    assert main([str(sample(tmp_path)), "--session-id", "synthetic-session"]) == 0
    output = capsys.readouterr().out
    assert "Hands detected: 1" in output
    assert "Valid hand boundaries: 1" in output
    assert "Fully validated poker hands: 0 (not implemented)" in output
    assert "synthetic_a" in output and "Alpha 🐣" in output


def test_json_retains_records_and_provenance(tmp_path, capsys) -> None:
    assert main([str(sample(tmp_path)), "--session-id", "s", "--json"]) == 0
    report = json.loads(capsys.readouterr().out)
    assert report["session_id"] == "s"
    assert report["hands"][0]["boundaries_valid"] is True
    assert report["records"][0]["sources"][0]["record_number"] == 1
    assert report["players"][0]["player_id"]["value"] == "synthetic_a"
    assert report["validation_scope"] == "hand_boundaries_only"


def test_strict_mode_reports_unknown_entries(tmp_path, capsys) -> None:
    path = sample(tmp_path)
    with path.open("a", encoding="utf-8") as file:
        file.write("future unknown event,2026-01-01T00:00:00Z,4\n")
    assert main([str(path), "--session-id", "s", "--strict"]) == 1
    assert "Unrecognized records: 1" in capsys.readouterr().out


def test_missing_file_has_concise_error(tmp_path, capsys) -> None:
    assert main([str(tmp_path / "missing.csv"), "--session-id", "s"]) == 2
    assert "Import failed:" in capsys.readouterr().err


def test_vpip_json_exposes_null_denominators_and_exclusions(tmp_path, capsys):
    # The CLI sample has a roster but no blind/action evidence.
    assert main([str(sample(tmp_path)), "--session-id", "s", "--vpip", "--json"]) == 0
    payload = json.loads(capsys.readouterr().out)["vpip"]
    assert payload["results"][0]["percentage"] is None
    assert payload["results"][0]["sample_size"] == 0
    assert payload["results"][0]["excluded"] == 1
    assert payload["excluded_hands"][0]["reasons"] == ["invalid_roster"]
    assert main([str(sample(tmp_path)), "--session-id", "s", "--vpip", "--strict"]) == 1


def test_vpip_conflicting_hand_identity_has_concise_error(tmp_path, capsys):
    path = sample(tmp_path)
    with path.open("a", encoding="utf-8", newline="") as file:
        writer = csv.writer(file)
        writer.writerow(
            [
                "-- starting hand #1 (id: synthetic)  "
                "Pot Limit Omaha 5 Hi (dead button) --",
                "2026-01-01T00:00:00Z",
                4,
            ]
        )
        writer.writerow(["-- ending hand #1 --", "2026-01-01T00:00:00Z", 5])
    assert main([str(path), "--session-id", "s", "--vpip"]) == 2
    assert "Duplicate hand" in capsys.readouterr().err


def test_new_cli_reconstruction_metrics_and_persistence(tmp_path, capsys):
    from test_api import input_file

    path = input_file(tmp_path)
    database = tmp_path / "cli.duckdb"
    assert (
        main(
            [
                str(path),
                "--session-id",
                "s",
                "--database",
                str(database),
                "--reconstruct",
                "--metrics",
                "--json",
            ]
        )
        == 0
    )
    payload = json.loads(capsys.readouterr().out)
    assert payload["persistence"]["new_records"] == 13
    assert payload["reconstructed_hands"][0]["accounting_reconciled"]
    assert any(
        row["metric_id"] == "preflop.vpip" and row["value"] == "1"
        for row in payload["metrics"]
    )
