"""Translate PokerNow preflop records into a source-independent typed contract."""

import re
from decimal import Decimal

from app.domain.preflop import (
    GameVariant,
    PreflopAction,
    PreflopActionKind,
    PreflopHand,
    StartingPlayer,
)
from app.ingestion.events import AMOUNT, REFERENCE, STACK, classify_event
from app.ingestion.importer import HandEnvelope, ImportReport
from app.ingestion.players import PlayerReferenceError, parse_player_reference

ACTION = re.compile(
    rf"(?P<player>{REFERENCE}) (?P<kind>folds|checks|calls|bets|raises to|"
    rf"posts a small blind of|posts a big blind of)"
    rf"(?: (?P<amount>{AMOUNT}))?(?P<all_in> and go all in)?"
)
KINDS = {
    "folds": PreflopActionKind.FOLD,
    "checks": PreflopActionKind.CHECK,
    "calls": PreflopActionKind.CALL,
    "bets": PreflopActionKind.BET,
    "raises to": PreflopActionKind.RAISE,
    "posts a small blind of": PreflopActionKind.SMALL_BLIND,
    "posts a big blind of": PreflopActionKind.BIG_BLIND,
}


def _normalize(hand: HandEnvelope) -> PreflopHand:
    players: tuple[StartingPlayer, ...] = ()
    actions: list[PreflopAction] = []
    issues: list[str] = [] if hand.boundaries_valid else ["invalid_hand_boundaries"]
    snapshots = 0
    dead = False
    for record in hand.records:
        text = record.entry
        if text.startswith(
            (
                "Flop:",
                "Turn:",
                "River:",
                "Flop (second run):",
                "Turn (second run):",
                "River (second run):",
            )
        ):
            if not text.startswith("Flop:"):
                issues.append("unsupported_street_transition")
            try:
                if classify_event(text).kind != "board_observation":
                    issues.append("unknown_preflop_record")
            except PlayerReferenceError:
                issues.append("unknown_preflop_record")
            break
        try:
            event = classify_event(text)
        except PlayerReferenceError:
            issues.append("malformed_preflop_record")
            continue
        if event.kind == "unknown":
            issues.append("unknown_preflop_record")
        if event.kind == "stacks":
            snapshots += 1
            if actions:
                issues.append("late_roster")
            parsed = tuple(
                StartingPlayer(
                    parse_player_reference(match["player"]).player_id,
                    int(match["seat"]),
                    Decimal(match["amount"]),
                )
                for match in STACK.finditer(text.removeprefix("Player stacks: "))
            )
            if snapshots == 1:
                players = parsed
        if text == "Dead Small Blind":
            dead = True
        match = ACTION.fullmatch(text)
        if match:
            # Require the stricter observed event grammar as well as extraction.
            if event.kind != "player_event":
                issues.append("malformed_preflop_action")
                continue
            actions.append(
                PreflopAction(
                    parse_player_reference(match["player"]).player_id,
                    KINDS[match["kind"]],
                    record.order,
                    Decimal(match["amount"]) if match["amount"] else None,
                    bool(match["all_in"]),
                )
            )
    if snapshots != 1:
        issues.append("missing_or_multiple_rosters")
    return PreflopHand(
        hand.session_id,
        hand.hand_id,
        {
            "No Limit Texas Hold'em": GameVariant.NLHE,
            "Pot Limit Omaha 5 Hi": GameVariant.PLO5,
        }.get(hand.variant, GameVariant.UNKNOWN),
        players,
        tuple(actions),
        dead,
        tuple(dict.fromkeys(issues)),
    )


def extract_preflop_hands(report: ImportReport) -> tuple[PreflopHand, ...]:
    """Roster snapshots define dealt participants, not session joins or names."""
    return tuple(_normalize(hand) for hand in report.hands)
