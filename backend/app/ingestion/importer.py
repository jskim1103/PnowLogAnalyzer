"""Session-scoped import, source merging, identity indexing and hand boundaries."""

import hashlib
from collections import Counter
from dataclasses import dataclass
from pathlib import Path

from app.domain.players import PlayerId
from app.ingestion.events import END, START, classify_event
from app.ingestion.players import PlayerReferenceError
from app.ingestion.records import SourceReference, read_records

PARSER_VERSION = "0.1.0"


class ImportConflictError(ValueError):
    """Overlapping exports disagree on the content of an ordered record."""


@dataclass(frozen=True)
class ImportedRecord:
    entry: str
    at: str
    order: int
    sources: tuple[SourceReference, ...]


@dataclass(frozen=True)
class ImportIssue:
    code: str
    message: str
    order: int


@dataclass(frozen=True)
class NameObservation:
    display_name: str
    order: int
    sources: tuple[SourceReference, ...]


@dataclass(frozen=True)
class IndexedPlayer:
    player_id: PlayerId
    observations: tuple[NameObservation, ...]


@dataclass(frozen=True)
class HandEnvelope:
    session_id: str
    hand_id: str
    number: int
    variant: str
    records: tuple[ImportedRecord, ...]
    boundaries_valid: bool


@dataclass(frozen=True)
class ImportReport:
    session_id: str
    parser_version: str
    source_hashes: tuple[str, ...]
    records: tuple[ImportedRecord, ...]
    players: tuple[IndexedPlayer, ...]
    hands: tuple[HandEnvelope, ...]
    outside_records: tuple[ImportedRecord, ...]
    unknown_records: tuple[ImportedRecord, ...]
    issues: tuple[ImportIssue, ...]
    duplicate_records: int


def import_session(paths: list[Path], *, session_id: str) -> ImportReport:
    """Merge overlapping exports belonging to a caller-specified single session."""
    if not session_id.strip():
        raise ValueError("A nonempty session ID is required")
    if not paths:
        raise ValueError("At least one export is required")
    merged: dict[int, ImportedRecord] = {}
    hashes: set[str] = set()
    duplicates = 0
    for path in paths:
        decoded_records = read_records(path)
        # Header-only files have no record from which to obtain a fingerprint.
        hashes.add(
            decoded_records[0].source.file_sha256
            if decoded_records
            else hashlib.sha256(path.read_bytes()).hexdigest()
        )
        for source_record in decoded_records:
            if not source_record.order.isascii() or not source_record.order.isdecimal():
                raise ValueError(
                    f"Record {source_record.source.record_number}: invalid order"
                )
            order = int(source_record.order)
            previous = merged.get(order)
            if previous:
                if (previous.entry, previous.at) != (
                    source_record.entry,
                    source_record.at,
                ):
                    raise ImportConflictError(f"Conflicting records at order {order}")
                duplicates += 1
                sources = previous.sources
                if source_record.source not in sources:
                    sources += (source_record.source,)
                merged[order] = ImportedRecord(
                    source_record.entry, source_record.at, order, sources
                )
            else:
                merged[order] = ImportedRecord(
                    source_record.entry,
                    source_record.at,
                    order,
                    (source_record.source,),
                )
    records = tuple(merged[key] for key in sorted(merged))
    names: dict[PlayerId, list[NameObservation]] = {}
    issues: list[ImportIssue] = []
    unknown: list[ImportedRecord] = []
    outside: list[ImportedRecord] = []
    hands: list[HandEnvelope] = []
    current: list[ImportedRecord] = []
    header: tuple[str, int, str] | None = None
    seen_ids: set[str] = set()
    seen_numbers: set[int] = set()
    boundary_problem = False

    def finish(valid: bool) -> None:
        if header is not None:
            hand_id, number, variant = header
            hands.append(
                HandEnvelope(
                    session_id, hand_id, number, variant, tuple(current), valid
                )
            )

    for record in records:
        try:
            event = classify_event(record.entry)
        except PlayerReferenceError as exc:
            issues.append(ImportIssue("malformed_player_event", str(exc), record.order))
            unknown.append(record)
        else:
            if event.kind == "unknown":
                unknown.append(record)
            for player in event.players:
                names.setdefault(player.player_id, []).append(
                    NameObservation(player.display_name, record.order, record.sources)
                )
        start = START.fullmatch(record.entry)
        end = END.fullmatch(record.entry)
        if start:
            if header is not None:
                issues.append(
                    ImportIssue(
                        "nested_start",
                        "New hand began before previous hand ended",
                        record.order,
                    )
                )
                finish(False)
            hand_id, number, variant = start[2], int(start[1]), start[3]
            boundary_problem = False
            if hand_id in seen_ids:
                issues.append(
                    ImportIssue(
                        "duplicate_hand_id",
                        "Hand ID appears in another boundary",
                        record.order,
                    )
                )
                boundary_problem = True
            if number in seen_numbers:
                issues.append(
                    ImportIssue(
                        "duplicate_hand_number", "Hand number is repeated", record.order
                    )
                )
                boundary_problem = True
            seen_ids.add(hand_id)
            seen_numbers.add(number)
            header = (hand_id, number, variant)
            current = [record]
        elif end:
            if header is None:
                issues.append(
                    ImportIssue("orphan_end", "End without start", record.order)
                )
                outside.append(record)
            else:
                current.append(record)
                matches = int(end[1]) == header[1]
                if not matches:
                    issues.append(
                        ImportIssue(
                            "end_number_mismatch",
                            "End number differs from start",
                            record.order,
                        )
                    )
                finish(matches and not boundary_problem)
                header = None
                current = []
        else:
            if record.entry.startswith(("-- starting hand", "-- ending hand")):
                issues.append(
                    ImportIssue(
                        "malformed_boundary", "Unrecognized hand boundary", record.order
                    )
                )
                boundary_problem = True
            if header is None:
                outside.append(record)
            else:
                current.append(record)
    if header is not None:
        issues.append(
            ImportIssue("missing_end", "Export ends inside a hand", current[-1].order)
        )
        finish(False)
    # Every occurrence of a repeated hand ID/number is structurally suspect.
    id_counts = Counter(h.hand_id for h in hands)
    number_counts = Counter(h.number for h in hands)
    repeated_ids = {key for key, count in id_counts.items() if count > 1}
    repeated_numbers = {key for key, count in number_counts.items() if count > 1}
    hands = [
        HandEnvelope(
            h.session_id,
            h.hand_id,
            h.number,
            h.variant,
            h.records,
            h.boundaries_valid
            and h.hand_id not in repeated_ids
            and h.number not in repeated_numbers,
        )
        for h in hands
    ]
    return ImportReport(
        session_id,
        PARSER_VERSION,
        tuple(sorted(hashes)),
        records,
        tuple(
            IndexedPlayer(player, tuple(names[player]))
            for player in sorted(names, key=lambda p: p.value)
        ),
        tuple(hands),
        tuple(outside),
        tuple(unknown),
        tuple(issues),
        duplicates,
    )
