"""Transactional DuckDB imports with cached typed histories and provenance."""

import hashlib
from dataclasses import dataclass
from pathlib import Path
from tempfile import TemporaryDirectory
from threading import RLock
from typing import Any

import duckdb
from pydantic import TypeAdapter

from app.domain.hands import Hand
from app.domain.players import PlayerId
from app.ingestion.hands import normalize_session
from app.ingestion.importer import ImportReport, import_session
from app.reconstruction.engine import reconstruct

SCHEMA_VERSION = 1
RECONSTRUCTION_VERSION = "2"
HAND_ADAPTER = TypeAdapter(Hand)
REPORT_ADAPTER = TypeAdapter(ImportReport)


@dataclass(frozen=True)
class ImportOutcome:
    session_id: str
    new_sources: int
    new_records: int
    hands: int
    reconciled: int
    issues: int


class Store:
    def __init__(self, path: Path) -> None:
        self.path = path
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self.lock = RLock()
        with self.lock, duckdb.connect(str(path)) as connection:
            connection.execute(
                "CREATE TABLE IF NOT EXISTS schema_info(version INTEGER)"
            )
            versions = connection.execute("SELECT version FROM schema_info").fetchall()
            if versions and versions != [(SCHEMA_VERSION,)]:
                raise ValueError("Unsupported database schema version")
            if not versions:
                connection.execute(
                    "INSERT INTO schema_info VALUES (?)", [SCHEMA_VERSION]
                )
            connection.execute("""CREATE TABLE IF NOT EXISTS sessions(
                session_id VARCHAR PRIMARY KEY, owner VARCHAR, report VARCHAR NOT NULL,
                reconstruction_version VARCHAR NOT NULL)""")
            connection.execute("""CREATE TABLE IF NOT EXISTS sources(
                session_id VARCHAR, sha256 VARCHAR, content BLOB NOT NULL,
                PRIMARY KEY(session_id,sha256))""")
            connection.execute("""CREATE TABLE IF NOT EXISTS hands(
                session_id VARCHAR, hand_id VARCHAR, number INTEGER, variant VARCHAR,
                occurred_at VARCHAR, reconciled BOOLEAN,
                consistent BOOLEAN, payload VARCHAR,
                PRIMARY KEY(session_id,hand_id))""")
            connection.execute("""CREATE TABLE IF NOT EXISTS hand_players(
                session_id VARCHAR, hand_id VARCHAR, player_id VARCHAR, name VARCHAR,
                seat INTEGER, position VARCHAR, starting_stack VARCHAR, net VARCHAR,
                PRIMARY KEY(session_id,hand_id,player_id))""")
            connection.execute("""CREATE TABLE IF NOT EXISTS actions(
                session_id VARCHAR, hand_id VARCHAR, sequence BIGINT, player_id VARCHAR,
                street VARCHAR, kind VARCHAR, amount_added VARCHAR, pot_before VARCHAR,
                PRIMARY KEY(session_id,hand_id,sequence))""")
            stale_sessions = connection.execute(
                "SELECT session_id FROM sessions WHERE reconstruction_version<>?",
                [RECONSTRUCTION_VERSION],
            ).fetchall()
        # Raw sources survive parser updates. Only obsolete cached reconstructions
        # are rebuilt; an ordinary launch does not reparse unchanged sessions.
        for (session_id,) in stale_sessions:
            self.rebuild(session_id)

    def import_paths(
        self, paths: list[Path], *, session_id: str, owner: str | None = None
    ) -> ImportOutcome:
        if not session_id.strip() or len(session_id) > 200:
            raise ValueError("A session label of 1–200 characters is required")
        if not paths:
            raise ValueError("At least one CSV is required")
        incoming = {
            hashlib.sha256(content).hexdigest(): content
            for content in (path.read_bytes() for path in paths)
        }
        with self.lock, duckdb.connect(str(self.path)) as connection:
            connection.execute("BEGIN TRANSACTION")
            try:
                previous = connection.execute(
                    "SELECT owner, report FROM sessions WHERE session_id=?",
                    [session_id],
                ).fetchone()
                previous_owner = previous[0] if previous else None
                if (
                    owner is not None
                    and previous_owner is not None
                    and owner != previous_owner
                ):
                    raise ValueError(
                        "Session export owner conflicts with the stored owner"
                    )
                effective_owner = owner if owner is not None else previous_owner
                stored = dict(
                    connection.execute(
                        "SELECT sha256, content FROM sources WHERE session_id=?",
                        [session_id],
                    ).fetchall()
                )
                other_sessions = connection.execute(
                    "SELECT session_id, sha256 FROM sources WHERE session_id<>?",
                    [session_id],
                ).fetchall()
                if any(sha in incoming for _, sha in other_sessions):
                    raise ValueError(
                        "This exact source was already assigned to another session"
                    )
                new_sources = len(set(incoming) - set(stored))
                old_report = (
                    REPORT_ADAPTER.validate_json(previous[1]) if previous else None
                )
                old_count = len(old_report.records) if old_report else 0
                combined = stored | incoming
                with TemporaryDirectory(prefix="pnow-import-") as temporary:
                    exports = []
                    for index, (_, content) in enumerate(sorted(combined.items())):
                        target = Path(temporary) / f"{index}.csv"
                        target.write_bytes(content)
                        exports.append(target)
                    report = import_session(exports, session_id=session_id)
                if len({h.hand_id for h in report.hands}) != len(report.hands):
                    raise ValueError(
                        "Conflicting duplicate hand boundaries cannot be persisted"
                    )
                hands = tuple(
                    reconstruct(h)
                    for h in normalize_session(
                        report,
                        owner=PlayerId(effective_owner) if effective_owner else None,
                    )
                )
                connection.execute(
                    "DELETE FROM actions WHERE session_id=?", [session_id]
                )
                connection.execute(
                    "DELETE FROM hand_players WHERE session_id=?", [session_id]
                )
                connection.execute("DELETE FROM hands WHERE session_id=?", [session_id])
                connection.execute(
                    "INSERT OR REPLACE INTO sessions VALUES (?,?,?,?)",
                    [
                        session_id,
                        effective_owner,
                        REPORT_ADAPTER.dump_json(report).decode(),
                        RECONSTRUCTION_VERSION,
                    ],
                )
                for sha, content in incoming.items():
                    connection.execute(
                        "INSERT OR IGNORE INTO sources VALUES (?,?,?)",
                        [session_id, sha, content],
                    )
                for hand in hands:
                    metadata = hand.history
                    connection.execute(
                        "INSERT INTO hands VALUES (?,?,?,?,?,?,?,?)",
                        [
                            session_id,
                            metadata.hand_id,
                            metadata.number,
                            metadata.variant.value,
                            metadata.timestamp.isoformat()
                            if metadata.timestamp
                            else None,
                            hand.accounting_reconciled,
                            hand.action_consistent,
                            HAND_ADAPTER.dump_json(hand).decode(),
                        ],
                    )
                    results = {r.player_id: r for r in hand.results}
                    for player in metadata.players:
                        result = results[player.player_id]
                        connection.execute(
                            "INSERT INTO hand_players VALUES (?,?,?,?,?,?,?,?)",
                            [
                                session_id,
                                metadata.hand_id,
                                player.player_id.value,
                                player.display_name,
                                player.seat,
                                result.position,
                                str(player.starting_stack),
                                str(result.net) if result.net is not None else None,
                            ],
                        )
                    for decision in hand.decisions:
                        connection.execute(
                            "INSERT INTO actions VALUES (?,?,?,?,?,?,?,?)",
                            [
                                session_id,
                                metadata.hand_id,
                                decision.event.order,
                                decision.event.player_id.value
                                if decision.event.player_id
                                else None,
                                decision.street.value,
                                decision.event.kind.value,
                                str(decision.amount_added),
                                str(decision.pot_before),
                            ],
                        )
                connection.execute("COMMIT")
            except BaseException:
                connection.execute("ROLLBACK")
                raise
        return ImportOutcome(
            session_id,
            new_sources,
            len(report.records) - old_count,
            len(hands),
            sum(h.accounting_reconciled for h in hands),
            len(report.issues)
            + sum(d.severity == "error" for h in hands for d in h.diagnostics),
        )

    def rebuild(self, session_id: str) -> ImportOutcome:
        with self.lock, duckdb.connect(str(self.path)) as connection:
            row = connection.execute(
                "SELECT content FROM sources WHERE session_id=? LIMIT 1", [session_id]
            ).fetchone()
        if row is None:
            raise ValueError("Session has no sources")
        with TemporaryDirectory(prefix="pnow-rebuild-") as temporary:
            target = Path(temporary) / "source.csv"
            target.write_bytes(row[0])
            return self.import_paths([target], session_id=session_id)

    def reports(self) -> tuple[ImportReport, ...]:
        with self.lock, duckdb.connect(str(self.path)) as connection:
            rows = connection.execute(
                "SELECT report FROM sessions ORDER BY session_id"
            ).fetchall()
        return tuple(REPORT_ADAPTER.validate_json(row[0]) for row in rows)

    def sessions(self) -> list[dict[str, Any]]:
        with self.lock, duckdb.connect(str(self.path)) as connection:
            rows = connection.execute("""SELECT s.session_id, s.owner,
                (SELECT COUNT(*) FROM sources x WHERE x.session_id=s.session_id),
                COUNT(h.hand_id), COALESCE(SUM(CAST(h.reconciled AS INTEGER)),0),
                MIN(h.occurred_at), MAX(h.occurred_at),s.reconstruction_version
                FROM sessions s LEFT JOIN hands h ON h.session_id=s.session_id
                GROUP BY s.session_id,s.owner,s.reconstruction_version
                ORDER BY MIN(h.occurred_at),s.session_id""").fetchall()
        return [
            dict(
                zip(
                    (
                        "session_id",
                        "owner",
                        "sources",
                        "hands",
                        "reconciled",
                        "start",
                        "end",
                        "reconstruction_version",
                    ),
                    row,
                    strict=True,
                )
            )
            for row in rows
        ]

    def hands(
        self,
        *,
        session_id: str | None = None,
        player_id: str | None = None,
        variant: str | None = None,
    ) -> tuple[Hand, ...]:
        conditions = []
        parameters: list[str] = []
        if session_id is not None:
            conditions.append("h.session_id=?")
            parameters.append(session_id)
        if variant is not None:
            conditions.append("h.variant=?")
            parameters.append(variant)
        if player_id is not None:
            conditions.append(
                "EXISTS (SELECT 1 FROM hand_players p "
                "WHERE p.session_id=h.session_id AND p.hand_id=h.hand_id "
                "AND p.player_id=?)"
            )
            parameters.append(player_id)
        where = " WHERE " + " AND ".join(conditions) if conditions else ""
        with self.lock, duckdb.connect(str(self.path)) as connection:
            rows = connection.execute(
                "SELECT payload FROM hands h"
                + where
                + " ORDER BY h.occurred_at,h.session_id,h.number",
                parameters,
            ).fetchall()
        return tuple(HAND_ADAPTER.validate_json(row[0]) for row in rows)
