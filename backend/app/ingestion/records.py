"""Strict CSV decoding with source provenance, independent of event grammar."""

import csv
import hashlib
import io
from dataclasses import dataclass
from pathlib import Path


class CsvDecodeError(ValueError):
    """An export cannot be decoded without losing or guessing records."""


@dataclass(frozen=True)
class SourceReference:
    file_sha256: str
    record_number: int
    line_start: int
    line_end: int


@dataclass(frozen=True)
class SourceRecord:
    entry: str
    at: str
    order: str
    source: SourceReference


def read_records(path: Path) -> tuple[SourceRecord, ...]:
    """Read an export in original order; retain decoded field values verbatim."""
    raw = path.read_bytes()
    fingerprint = hashlib.sha256(raw).hexdigest()
    try:
        decoded = raw.decode("utf-8-sig")
    except UnicodeDecodeError as exc:
        raise CsvDecodeError("Export is not valid UTF-8") from exc
    reader = csv.reader(io.StringIO(decoded, newline=""), strict=True)
    records: list[SourceRecord] = []
    try:
        if next(reader, None) != ["entry", "at", "order"]:
            raise CsvDecodeError("Expected CSV header: entry,at,order")
        previous_line = reader.line_num
        for number, fields in enumerate(reader, start=1):
            start_line = previous_line + 1
            previous_line = reader.line_num
            if len(fields) != 3:
                raise CsvDecodeError(f"Record {number}: expected exactly three fields")
            records.append(
                SourceRecord(
                    entry=fields[0],
                    at=fields[1],
                    order=fields[2],
                    source=SourceReference(
                        fingerprint, number, start_line, reader.line_num
                    ),
                )
            )
    except csv.Error as exc:
        raise CsvDecodeError(f"Malformed CSV near line {reader.line_num}") from exc
    return tuple(records)
