"""VPIP from typed preflop observations, independent of PokerNow formatting."""

from collections import Counter
from dataclasses import dataclass
from decimal import Decimal

from app.domain.players import PlayerId
from app.domain.preflop import GameVariant, PreflopHand
from app.domain.preflop import PreflopActionKind as Kind

SUPPORTED_VARIANTS = {GameVariant.NLHE, GameVariant.PLO5}


@dataclass(frozen=True)
class VpipResult:
    player_id: PlayerId
    variant: GameVariant
    numerator: int
    denominator: int
    excluded: int

    @property
    def sample_size(self) -> int:
        return self.denominator

    @property
    def percentage(self) -> float | None:
        return 100 * self.numerator / self.denominator if self.denominator else None


@dataclass(frozen=True)
class HandExclusion:
    session_id: str
    hand_id: str
    variant: GameVariant
    reasons: tuple[str, ...]


@dataclass(frozen=True)
class VpipReport:
    results: tuple[VpipResult, ...]
    excluded_hands: tuple[HandExclusion, ...]


def _investors(hand: PreflopHand) -> tuple[set[PlayerId], tuple[str, ...]]:
    if hand.input_issues:
        return set(), hand.input_issues
    if hand.variant not in SUPPORTED_VARIANTS:
        return set(), ("unsupported_variant",)
    roster = {p.player_id: p for p in hand.players}
    if (
        len(roster) != len(hand.players)
        or len(roster) < 2
        or len({p.seat for p in hand.players}) != len(roster)
        or any(p.stack <= 0 or p.seat <= 0 for p in hand.players)
    ):
        return set(), ("invalid_roster",)
    orders = [a.order for a in hand.actions]
    if orders != sorted(set(orders)):
        return set(), ("invalid_action_order",)
    committed = dict.fromkeys(roster, Decimal(0))
    folded: set[PlayerId] = set()
    pending = set(roster)
    investors: set[PlayerId] = set()
    blinds: list[Kind] = []
    decisions_started = False
    for action in hand.actions:
        player = action.player_id
        if player not in roster:
            return set(), ("unknown_actor",)
        if player in folded:
            return set(), ("action_after_fold",)
        if committed[player] == roster[player].stack:
            return set(), ("action_after_all_in",)
        wager = max(committed.values())
        if action.kind in {Kind.SMALL_BLIND, Kind.BIG_BLIND}:
            if decisions_started or action.kind in blinds or committed[player] != 0:
                return set(), ("invalid_blinds",)
            blinds.append(action.kind)
            target = action.amount
            if target is None or target <= 0:
                return set(), ("invalid_amount",)
            committed[player] = target
        else:
            decisions_started = True
            if player not in pending:
                return set(), ("unexpected_preflop_action",)
            if action.kind == Kind.FOLD:
                folded.add(player)
                pending.discard(player)
                continue
            if action.kind == Kind.CHECK:
                if committed[player] != wager:
                    return set(), ("check_facing_bet",)
                pending.discard(player)
                continue
            if action.kind == Kind.BET:
                return set(), ("unsupported_preflop_bet",)
            target = action.amount
            if target is None:
                return set(), ("invalid_amount",)
            if target <= committed[player]:
                return set(), ("nonpositive_investment",)
            if action.kind == Kind.CALL:
                if target > wager or (
                    target < wager and target != roster[player].stack
                ):
                    return set(), ("invalid_call",)
            elif action.kind == Kind.RAISE:
                if target <= wager:
                    return set(), ("invalid_raise",)
                pending = {
                    p
                    for p in roster
                    if p not in folded and committed[p] < roster[p].stack
                }
            else:
                return set(), ("unsupported_action",)
            committed[player] = target
            investors.add(player)
            pending.discard(player)
        if committed[player] > roster[player].stack:
            return set(), ("stack_exceeded",)
        if action.all_in and committed[player] != roster[player].stack:
            return set(), ("inconsistent_all_in",)
        if committed[player] == roster[player].stack:
            pending.discard(player)
    expected_blinds = {Kind.BIG_BLIND}
    if not hand.dead_small_blind:
        expected_blinds.add(Kind.SMALL_BLIND)
    if set(blinds) != expected_blinds:
        return set(), ("missing_blinds",)
    live = set(roster) - folded
    able = {p for p in live if committed[p] < roster[p].stack}
    if not live:
        return set(), ("no_live_players",)
    if len(live) > 1:
        # A sole non-all-in player need not check when nobody can bet against them.
        if len(able) == 1:
            sole = next(iter(able))
            if committed[sole] >= max(committed[p] for p in live - {sole}):
                pending.discard(sole)
        if pending & live:
            return set(), ("incomplete_preflop",)
        if able and any(committed[p] < max(committed.values()) for p in able):
            return set(), ("incomplete_preflop",)
    return investors, ()


def calculate_vpip(hands: tuple[PreflopHand, ...]) -> VpipReport:
    """Count eligible dealt hands once per player and game variant.

    Entire hands with ambiguous/incomplete preflop evidence are excluded. These
    eligibility checks do not establish complete poker legality or pot accounting.
    """
    numerator: Counter[tuple[GameVariant, PlayerId]] = Counter()
    denominator: Counter[tuple[GameVariant, PlayerId]] = Counter()
    excluded: Counter[tuple[GameVariant, PlayerId]] = Counter()
    exclusions: list[HandExclusion] = []
    keys: set[tuple[GameVariant, PlayerId]] = set()
    seen: set[tuple[str, str]] = set()
    for hand in hands:
        identity = (hand.session_id, hand.hand_id)
        if identity in seen:
            raise ValueError("Duplicate hand in statistics input")
        seen.add(identity)
        investors, reasons = _investors(hand)
        if reasons:
            exclusions.append(HandExclusion(*identity, hand.variant, reasons))
        for player in {p.player_id for p in hand.players}:
            key = (hand.variant, player)
            keys.add(key)
            if reasons:
                excluded[key] += 1
            else:
                denominator[key] += 1
                numerator[key] += player in investors
    return VpipReport(
        tuple(
            VpipResult(
                player,
                variant,
                numerator[(variant, player)],
                denominator[(variant, player)],
                excluded[(variant, player)],
            )
            for variant, player in sorted(keys, key=lambda key: (key[0], key[1].value))
        ),
        tuple(exclusions),
    )
