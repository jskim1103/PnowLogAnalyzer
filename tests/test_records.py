import csv
import hashlib
import io
from pathlib import Path

import pytest
from app.ingestion.players import parse_player_reference
from app.ingestion.records import CsvDecodeError, read_records


def test_quoted_unicode_multiline_records_and_provenance(tmp_path: Path) -> None:
    stream = io.StringIO(newline="")
    writer = csv.writer(stream)
    writer.writerow(["entry", "at", "order"])
    writer.writerow(['"Comma, 🐣 @ synthetic_1"', "2026-01-01T00:00:00Z", "102"])
    writer.writerow(["Game Config Changes\n* synthetic change", "unchanged", "101"])
    raw = stream.getvalue().encode("utf-8-sig")
    path = tmp_path / "synthetic.csv"
    path.write_bytes(raw)
    first, second = read_records(path)
    assert parse_player_reference(first.entry).display_name == "Comma, 🐣"
    assert first.at == "2026-01-01T00:00:00Z"
    assert first.order == "102"
    assert second.order == "101"  # Decoder must not reorder records.
    assert second.entry == "Game Config Changes\n* synthetic change"
    assert second.at == "unchanged"  # Timestamp validation is a later stage.
    assert first.source.file_sha256 == hashlib.sha256(raw).hexdigest()
    assert first.source.record_number == 1
    assert (first.source.line_start, first.source.line_end) == (2, 2)
    assert second.source.record_number == 2
    assert (second.source.line_start, second.source.line_end) == (3, 4)
    assert read_records(path) == (first, second)


@pytest.mark.parametrize(
    "contents",
    [
        b"",
        b"other,at,order\n",
        b"entry,at,order\na,b\n",
        b"entry,at,order\na,b,c,d\n",
        b"entry,at,order\n\n",
        b'entry,at,order\n"unterminated,b,c',
        b"entry,at,order\n\xff,b,c\n",
    ],
)
def test_bad_input_is_not_silently_skipped(tmp_path: Path, contents: bytes) -> None:
    path = tmp_path / "bad.csv"
    path.write_bytes(contents)
    with pytest.raises(CsvDecodeError):
        read_records(path)


def test_header_only_export_is_empty(tmp_path: Path) -> None:
    path = tmp_path / "empty.csv"
    path.write_text("entry,at,order\n", encoding="utf-8")
    assert read_records(path) == ()
