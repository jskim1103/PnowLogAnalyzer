"""PokerNow-to-domain adapter for complete observed hand histories."""

import re
from datetime import UTC, datetime
from decimal import Decimal

from app.domain.hands import (
    Card,
    Diagnostic,
    HandEvent,
    HandHistory,
    HandPlayer,
    Provenance,
    Street,
)
from app.domain.hands import (
    EventKind as K,
)
from app.domain.players import PlayerId
from app.domain.preflop import GameVariant
from app.ingestion.events import AMOUNT, CARDS, REFERENCE, STACK, START, classify_event
from app.ingestion.importer import HandEnvelope, ImportReport
from app.ingestion.players import PlayerReferenceError, parse_player_reference
from app.ingestion.preflop import ACTION, KINDS

SUITS = {"♣": "c", "♦": "d", "♥": "h", "♠": "s"}
BOARD_EVENT = re.compile(
    rf"(?P<street>Flop|Turn|River)(?P<second> \(second run\))?: "
    rf"(?P<prefix>{CARDS})? \[(?P<new>{CARDS})\]"
)
SHOW = re.compile(rf"(?P<player>{REFERENCE}) shows a (?P<cards>{CARDS})\.")
RETURN = re.compile(
    rf"Uncalled bet of (?P<amount>{AMOUNT}) returned to (?P<player>{REFERENCE})"
)
AWARD = re.compile(
    rf"(?P<player>{REFERENCE}) collected (?P<amount>{AMOUNT}) from pot(?: with .+)?"
)


def cards_from_text(text: str) -> tuple[Card, ...]:
    return tuple(
        Card(("T" if token[:-1] == "10" else token[:-1]) + SUITS[token[-1]])
        for token in text.split(", ")
        if token
    )


def normalize_hand(
    envelope: HandEnvelope, *, owner: PlayerId | None = None
) -> HandHistory:
    issues: list[Diagnostic] = []
    events: list[HandEvent] = []
    players: tuple[HandPlayer, ...] = ()
    button: PlayerId | None = None
    timestamp: datetime | None = None
    snapshots = 0
    betting_started = False
    for record in envelope.records:
        text = record.entry
        sources = tuple(
            Provenance(s.file_sha256, s.record_number, s.line_start, s.line_end)
            for s in record.sources
        )
        kind = K.OBSERVATION
        actor: PlayerId | None = None
        amount: Decimal | None = None
        cards: tuple[Card, ...] = ()
        total = False
        all_in = False
        street: Street | None = None
        run: int | None = None
        try:
            classified = classify_event(text)
            if classified.kind == "unknown":
                kind = K.UNKNOWN
            if text == "All players in hand choose to run it twice.":
                kind = K.RUN_TWICE
            if classified.kind == "hand_start":
                match = START.fullmatch(text)
                assert match is not None
                if match["dealer"]:
                    button = parse_player_reference(match["dealer"]).player_id
                try:
                    timestamp = datetime.fromisoformat(record.at.replace("Z", "+00:00"))
                    if timestamp.tzinfo is None:
                        raise ValueError("Missing timestamp timezone")
                    timestamp = timestamp.astimezone(UTC)
                except ValueError:
                    issues.append(
                        Diagnostic(
                            "invalid_timestamp",
                            "Timestamp needs an explicit timezone",
                            record.order,
                        )
                    )
                    timestamp = None
            elif classified.kind == "stacks":
                snapshots += 1
                if betting_started:
                    issues.append(
                        Diagnostic(
                            "late_roster",
                            "Starting stacks recorded after betting",
                            record.order,
                        )
                    )
                if snapshots == 1:
                    players = tuple(
                        HandPlayer(
                            parse_player_reference(m["player"]).player_id,
                            parse_player_reference(m["player"]).display_name,
                            int(m["seat"]),
                            Decimal(m["amount"]),
                        )
                        for m in STACK.finditer(text.removeprefix("Player stacks: "))
                    )
            action = ACTION.fullmatch(text)
            if action and classified.kind == "player_event":
                kind = K(KINDS[action["kind"]].value)
                actor = parse_player_reference(action["player"]).player_id
                amount = Decimal(action["amount"]) if action["amount"] else None
                total = kind in {K.CALL, K.RAISE}
                all_in = bool(action["all_in"])
                betting_started = True
            board = BOARD_EVENT.fullmatch(text)
            if board:
                kind = K.BOARD
                street = Street(board["street"].lower())
                cards = cards_from_text(
                    ", ".join(part for part in (board["prefix"], board["new"]) if part)
                )
                run = 2 if board["second"] else 1
            show = SHOW.fullmatch(text)
            if show:
                kind = K.SHOW
                actor = parse_player_reference(show["player"]).player_id
                cards = cards_from_text(show["cards"])
            if classified.kind == "unattributed_cards":
                kind = K.PRIVATE_CARDS
                actor = owner
                cards = cards_from_text(text.removeprefix("Your hand is "))
            returned = RETURN.fullmatch(text)
            awarded = AWARD.fullmatch(text)
            money = returned or awarded
            if money:
                kind = K.RETURN if returned else K.AWARD
                actor = parse_player_reference(money["player"]).player_id
                amount = Decimal(money["amount"])
                if awarded and " on the second run " in text:
                    run = 2
        except (PlayerReferenceError, ValueError, KeyError) as exc:
            issues.append(Diagnostic("malformed_event", str(exc), record.order))
            kind = K.UNKNOWN
        events.append(
            HandEvent(
                record.order,
                kind,
                actor,
                amount,
                total,
                all_in,
                cards,
                street,
                run,
                sources,
                text,
            )
        )
    if snapshots != 1:
        issues.append(
            Diagnostic(
                "missing_or_multiple_rosters",
                "Exactly one starting stack snapshot required",
            )
        )
    if button is not None and button not in {p.player_id for p in players}:
        issues.append(Diagnostic("invalid_button", "Button is not in the dealt roster"))
    return HandHistory(
        envelope.session_id,
        envelope.hand_id,
        envelope.number,
        {
            "No Limit Texas Hold'em": GameVariant.NLHE,
            "Pot Limit Omaha 5 Hi": GameVariant.PLO5,
        }.get(envelope.variant, GameVariant.UNKNOWN),
        timestamp,
        button,
        players,
        tuple(events),
        envelope.boundaries_valid,
        tuple(dict.fromkeys(s for event in events for s in event.sources)),
        tuple(issues),
        any(record.entry == "Dead Small Blind" for record in envelope.records),
    )


def normalize_session(
    report: ImportReport, *, owner: PlayerId | None = None
) -> tuple[HandHistory, ...]:
    return tuple(normalize_hand(hand, owner=owner) for hand in report.hands)
