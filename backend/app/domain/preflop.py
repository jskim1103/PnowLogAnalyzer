"""Provisional source-independent input for preflop descriptive statistics."""

from dataclasses import dataclass
from decimal import Decimal
from enum import StrEnum

from app.domain.players import PlayerId


class GameVariant(StrEnum):
    NLHE = "NLHE"
    PLO5 = "PLO5"
    UNKNOWN = "UNKNOWN"


class PreflopActionKind(StrEnum):
    SMALL_BLIND = "small_blind"
    BIG_BLIND = "big_blind"
    FOLD = "fold"
    CHECK = "check"
    CALL = "call"
    BET = "bet"
    RAISE = "raise"


@dataclass(frozen=True)
class StartingPlayer:
    player_id: PlayerId
    seat: int
    stack: Decimal


@dataclass(frozen=True)
class PreflopAction:
    player_id: PlayerId
    kind: PreflopActionKind
    order: int
    amount: Decimal | None = None
    all_in: bool = False


@dataclass(frozen=True)
class PreflopHand:
    session_id: str
    hand_id: str
    variant: GameVariant
    players: tuple[StartingPlayer, ...]
    actions: tuple[PreflopAction, ...]
    dead_small_blind: bool = False
    input_issues: tuple[str, ...] = ()
