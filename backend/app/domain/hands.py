"""Immutable, source-independent hand histories and reconstructed decisions."""

from dataclasses import dataclass
from datetime import datetime
from decimal import Decimal
from enum import StrEnum

from app.domain.players import PlayerId
from app.domain.preflop import GameVariant


class Street(StrEnum):
    PREFLOP = "preflop"
    FLOP = "flop"
    TURN = "turn"
    RIVER = "river"


class EventKind(StrEnum):
    SMALL_BLIND = "small_blind"
    BIG_BLIND = "big_blind"
    FOLD = "fold"
    CHECK = "check"
    CALL = "call"
    BET = "bet"
    RAISE = "raise"
    BOARD = "board"
    SHOW = "show"
    PRIVATE_CARDS = "private_cards"
    RUN_TWICE = "run_twice"
    RETURN = "return"
    AWARD = "award"
    OBSERVATION = "observation"
    UNKNOWN = "unknown"


@dataclass(frozen=True, order=True)
class Card:
    code: str

    def __post_init__(self) -> None:
        if (
            len(self.code) != 2
            or self.code[0] not in "23456789TJQKA"
            or self.code[1] not in "cdhs"
        ):
            raise ValueError(f"Invalid canonical card: {self.code!r}")


@dataclass(frozen=True)
class Provenance:
    file_sha256: str
    record_number: int
    line_start: int
    line_end: int


@dataclass(frozen=True)
class HandPlayer:
    player_id: PlayerId
    display_name: str
    seat: int
    starting_stack: Decimal


@dataclass(frozen=True)
class HandEvent:
    order: int
    kind: EventKind
    player_id: PlayerId | None = None
    amount: Decimal | None = None
    street_total: bool = False
    all_in: bool = False
    cards: tuple[Card, ...] = ()
    street: Street | None = None
    run: int | None = None
    sources: tuple[Provenance, ...] = ()
    raw: str = ""


@dataclass(frozen=True)
class Diagnostic:
    code: str
    message: str
    order: int | None = None
    severity: str = "error"


@dataclass(frozen=True)
class HandHistory:
    session_id: str
    hand_id: str
    number: int
    variant: GameVariant
    timestamp: datetime | None
    button: PlayerId | None
    players: tuple[HandPlayer, ...]
    events: tuple[HandEvent, ...]
    boundaries_valid: bool
    sources: tuple[Provenance, ...] = ()
    diagnostics: tuple[Diagnostic, ...] = ()
    dead_small_blind: bool = False


@dataclass(frozen=True)
class PlayerState:
    player_id: PlayerId
    remaining: Decimal
    street_commitment: Decimal
    total_contribution: Decimal
    folded: bool
    all_in: bool


@dataclass(frozen=True)
class Decision:
    event: HandEvent
    street: Street
    board: tuple[Card, ...]
    pot_before: Decimal
    facing: Decimal
    to_call: Decimal
    effective_stack: Decimal
    previous_aggressor: PlayerId | None
    active_players: tuple[PlayerId, ...]
    states_before: tuple[PlayerState, ...]
    can_raise: bool
    in_position: bool | None
    position: str | None
    amount_added: Decimal
    street_commitment: Decimal
    pot_after: Decimal


@dataclass(frozen=True)
class Board:
    run: int
    cards: tuple[Card, ...]


@dataclass(frozen=True)
class Pot:
    amount: Decimal
    eligible: tuple[PlayerId, ...]
    contribution_cap: Decimal


@dataclass(frozen=True)
class PlayerResult:
    player_id: PlayerId
    position: str | None
    contributed: Decimal
    returned: Decimal
    awarded: Decimal
    net: Decimal | None
    ending_stack: Decimal | None
    observed_cards: tuple[Card, ...]
    complete_hole_cards: bool
    folded: bool


@dataclass(frozen=True)
class Hand:
    history: HandHistory
    decisions: tuple[Decision, ...]
    boards: tuple[Board, ...]
    pots: tuple[Pot, ...]
    results: tuple[PlayerResult, ...]
    small_blind: Decimal | None
    big_blind: Decimal | None
    accounting_reconciled: bool
    action_consistent: bool
    status: str
    diagnostics: tuple[Diagnostic, ...]
