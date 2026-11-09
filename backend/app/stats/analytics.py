"""Metric-specific opportunity extraction and deterministic aggregation."""

from collections.abc import Callable
from dataclasses import dataclass
from decimal import Decimal
from math import sqrt

from app.domain.cards import nlhe_class
from app.domain.hands import Decision, Hand, Street
from app.domain.hands import EventKind as K
from app.domain.players import PlayerId
from app.domain.preflop import GameVariant
from app.stats.registry import REGISTRY


@dataclass(frozen=True)
class MetricResult:
    metric_id: str
    player_id: str
    variant: str
    numerator: Decimal
    denominator: int
    value: Decimal | None
    sample_size: int
    excluded_hands: int
    confidence_interval: tuple[float, float] | None


@dataclass
class _Tally:
    numerator: Decimal = Decimal(0)
    denominator: int = 0
    excluded: int = 0


def wilson(successes: int, n: int) -> tuple[float, float] | None:
    if n == 0:
        return None
    if not 0 <= successes <= n:
        raise ValueError("Binomial successes must be within the sample")
    z = 1.959963984540054
    p = successes / n
    center = (p + z * z / (2 * n)) / (1 + z * z / n)
    radius = z * sqrt(p * (1 - p) / n + z * z / (4 * n * n)) / (1 + z * z / n)
    return max(0, center - radius), min(1, center + radius)


def _samples(hand: Hand, pid: PlayerId) -> dict[str, list[tuple[Decimal, int]]]:
    output: dict[str, list[tuple[Decimal, int]]] = {}

    def add(metric: str, success: bool | int | Decimal, n: int = 1) -> None:
        output.setdefault(metric, []).append((Decimal(success), n))

    pre = [d for d in hand.decisions if d.street == Street.PREFLOP]
    my_pre = [d for d in pre if d.event.player_id == pid]
    add("hands.dealt", 1)
    checks: tuple[tuple[str, Callable[[Decision], bool]], ...] = (
        ("vpip", lambda d: d.event.kind in {K.CALL, K.RAISE} and d.amount_added > 0),
        ("pfr", lambda d: d.event.kind == K.RAISE),
        ("call", lambda d: d.event.kind == K.CALL),
        ("fold", lambda d: d.event.kind == K.FOLD),
        (
            "all_in",
            lambda d: (
                d.amount_added > 0
                and next(s.remaining for s in d.states_before if s.player_id == pid)
                == d.amount_added
            ),
        ),
    )
    for metric, test in checks:
        add("preflop." + metric, any(test(d) for d in my_pre))
    voluntary = False
    limpers: set[PlayerId] = set()
    invested: set[PlayerId] = set()
    raises = 0
    opener: PlayerId | None = None
    three_bettor: PlayerId | None = None
    steal_open = False
    calls_after_open = 0
    mine_limp = False
    mine_open_limp = False
    mine_overlimp = False
    limper_response_used = False
    blind_ids = {
        e.player_id
        for e in hand.history.events
        if e.kind in {K.SMALL_BLIND, K.BIG_BLIND}
    }
    small_blind_id = next(
        (e.player_id for e in hand.history.events if e.kind == K.SMALL_BLIND), None
    )
    big_blind_id = next(
        (e.player_id for e in hand.history.events if e.kind == K.BIG_BLIND), None
    )
    for d in pre:
        actor = d.event.player_id
        assert actor is not None
        kind = d.event.kind
        capable = (
            d.can_raise
            and next(s.remaining for s in d.states_before if s.player_id == actor)
            > d.to_call
        )
        if actor == pid:
            if not voluntary and capable:
                add("preflop.rfi", kind == K.RAISE)
                if d.position in {"CO", "BTN", "BTN/SB", "SB"} and capable:
                    add("preflop.steal", kind == K.RAISE)
            if raises in {1, 2, 3} and d.facing > 0 and capable:
                metric = {1: "three_bet", 2: "four_bet", 3: "five_bet"}[raises]
                add("preflop." + metric, kind == K.RAISE)
                if raises == 1 and calls_after_open > 0:
                    add("preflop.squeeze", kind == K.RAISE)
            if not raises and limpers and capable:
                add("preflop.isolation", kind == K.RAISE)
            if actor == small_blind_id and raises == 0 and d.facing > 0:
                add("preflop.sb_complete", kind == K.CALL)
            if raises == 1 and d.facing > 0:
                if actor == big_blind_id:
                    add("preflop.bb_defend", kind != K.FOLD)
                    add("preflop.bb_call_open", kind == K.CALL)
                    if capable:
                        add("preflop.bb_three_bet_open", kind == K.RAISE)
                    if steal_open:
                        add("preflop.bb_fold_steal", kind == K.FOLD)
                if actor == small_blind_id:
                    add("preflop.sb_fold_open", kind == K.FOLD)
                    if capable:
                        add("preflop.sb_three_bet_open", kind == K.RAISE)
            if raises == 3 and actor == three_bettor and d.facing > 0:
                add("preflop.fold_to_four_bet", kind == K.FOLD)
                add("preflop.call_four_bet", kind == K.CALL)
            if raises == 2 and actor not in invested and d.facing > 0 and capable:
                add("preflop.cold_four_bet", kind == K.RAISE)
            if kind == K.RAISE and raises in {0, 1, 2}:
                family = {0: "open", 1: "three_bet", 2: "four_bet"}[raises]
                if hand.big_blind:
                    add(
                        "preflop." + family + "_size_bb",
                        d.street_commitment / hand.big_blind,
                    )
                last_raise = next(
                    (
                        action
                        for action in reversed(pre)
                        if action.event.kind == K.RAISE
                    ),
                    None,
                )
                success = (
                    not hand.boards
                    and last_raise is not None
                    and last_raise.event.order == d.event.order
                    and sum(not r.folded for r in hand.results) == 1
                    and not next(r for r in hand.results if r.player_id == pid).folded
                )
                add("preflop." + family + "_success", success)
            if raises == 1 and actor not in invested and d.facing > 0:
                add("preflop.call_open", kind == K.CALL)
                if actor not in blind_ids:
                    add("preflop.cold_call", kind == K.CALL)
            if raises == 2 and opener == actor and d.facing > 0:
                add("preflop.fold_to_three_bet", kind == K.FOLD)
                add("preflop.call_three_bet", kind == K.CALL)
            if (
                actor in limpers
                and raises == 1
                and d.facing > 0
                and not limper_response_used
            ):
                add("preflop.limp_fold", kind == K.FOLD)
                add("preflop.limp_call", kind == K.CALL)
                if capable:
                    add("preflop.limp_raise", kind == K.RAISE)
                limper_response_used = True
            big = next(
                (e.player_id for e in hand.history.events if e.kind == K.BIG_BLIND),
                None,
            )
            if pid == big and d.facing == 0:
                add("preflop.check_option", kind == K.CHECK)
        if kind == K.CALL and raises == 0:
            if actor == pid:
                mine_limp = True
                mine_open_limp = not voluntary
                mine_overlimp = bool(limpers)
            limpers.add(actor)
        if kind in {K.CALL, K.RAISE}:
            invested.add(actor)
            voluntary = True
        if kind == K.CALL and raises == 1:
            calls_after_open += 1
        if kind == K.RAISE:
            if raises == 0:
                steal_open = not limpers and d.position in {"CO", "BTN", "BTN/SB", "SB"}
            if raises == 1:
                three_bettor = actor
            raises += 1
            if opener is None:
                opener = actor
    for name, value in (
        ("limp", mine_limp),
        ("open_limp", mine_open_limp),
        ("overlimp", mine_overlimp),
    ):
        add("preflop." + name, value)
    add(
        "preflop.vpip_minus_pfr",
        any(d.event.kind == K.CALL for d in my_pre)
        and not any(d.event.kind == K.RAISE for d in my_pre),
    )
    for d in hand.decisions:
        if d.street == Street.PREFLOP or d.event.player_id != pid:
            continue
        if d.event.kind in {K.BET, K.RAISE, K.CALL, K.FOLD}:
            add("postflop.afq", d.event.kind in {K.BET, K.RAISE})
        add(
            "postflop.af", d.event.kind in {K.BET, K.RAISE}, int(d.event.kind == K.CALL)
        )
    if any(e.kind == K.BIG_BLIND and e.player_id == pid for e in hand.history.events):
        add(
            "preflop.walk",
            not my_pre
            and sum(not r.folded for r in hand.results) == 1
            and not next(r for r in hand.results if r.player_id == pid).folded,
        )
    # Continuation lines are evaluated once per street using the full action order.
    previous_agg = next(
        (d.event.player_id for d in reversed(pre) if d.event.kind == K.RAISE), None
    )
    for street in (Street.FLOP, Street.TURN, Street.RIVER):
        street_name = street.value
        ds = [d for d in hand.decisions if d.street == street]
        cbetter: PlayerId | None = None
        seen_actors: set[PlayerId] = set()
        aggression = False
        checked: set[PlayerId] = set()
        faced_after_check: set[PlayerId] = set()
        qualified_next: PlayerId | None = None
        for d in ds:
            actor = d.event.player_id
            assert actor is not None
            kind = d.event.kind
            capable = (
                d.can_raise
                and next(s.remaining for s in d.states_before if s.player_id == actor)
                > d.to_call
            )
            has_opponent = any(
                not s.folded and s.player_id != actor and s.remaining > 0
                for s in d.states_before
            )
            cbet_opportunity = (
                actor == previous_agg
                and actor not in seen_actors
                and not aggression
                and d.facing == 0
                and has_opponent
            )
            if cbet_opportunity:
                if actor == pid:
                    add(street_name + ".cbet", kind == K.BET)
                if kind == K.BET:
                    cbetter = actor
                    qualified_next = actor
            if actor == pid:
                if kind == K.BET and d.pot_before > 0:
                    add(street_name + ".bet_size_pot", d.amount_added / d.pot_before)
                    add(street_name + ".overbet", d.amount_added > d.pot_before)
                add(
                    street_name + ".all_in",
                    d.amount_added > 0
                    and next(s.remaining for s in d.states_before if s.player_id == pid)
                    == d.amount_added,
                )
                for action in ("bet", "raise", "call", "check", "fold"):
                    add(street_name + "." + action, kind.value == action)
                if kind in {K.BET, K.RAISE, K.CALL, K.FOLD}:
                    add(street_name + ".afq", kind in {K.BET, K.RAISE})
                add(street_name + ".af", kind in {K.BET, K.RAISE}, int(kind == K.CALL))
                if d.facing > 0:
                    for response in ("fold", "call", "raise"):
                        if response != "raise" or capable:
                            add(
                                street_name + "." + response + "_facing_bet",
                                kind.value == response,
                            )
                    if actor in checked and actor not in faced_after_check:
                        for response in ("fold", "call", "raise"):
                            if response != "raise" or capable:
                                add(
                                    street_name + ".check_" + response,
                                    kind.value == response,
                                )
                    if cbetter is not None and d.previous_aggressor == cbetter:
                        for response in ("fold", "call", "raise"):
                            if response != "raise" or capable:
                                add(
                                    street_name + "." + response + "_to_cbet",
                                    kind.value == response,
                                )
            if d.facing > 0 and actor in checked:
                faced_after_check.add(actor)
            if kind == K.CHECK:
                checked.add(actor)
            if kind in {K.BET, K.RAISE}:
                aggression = True
                if actor != cbetter:
                    cbetter = None
            seen_actors.add(actor)
        last_street_aggressor = next(
            (
                d.event.player_id
                for d in reversed(ds)
                if d.event.kind in {K.BET, K.RAISE}
            ),
            None,
        )
        previous_agg = (
            qualified_next if last_street_aggressor == qualified_next else None
        )
        board_event = next(
            (
                e
                for e in hand.history.events
                if e.kind == K.BOARD and e.street == street and e.run == 1
            ),
            None,
        )
        folded_before = any(
            d.event.kind == K.FOLD
            and d.event.player_id == pid
            and board_event is not None
            and d.event.order < board_event.order
            for d in hand.decisions
        )
        saw = board_event is not None and not folded_before
        add(street_name + ".seen", saw)
        if street == Street.FLOP and saw:
            live_at_end = [r for r in hand.results if not r.folded]
            river = next(
                (b for b in hand.boards if b.run == 1 and len(b.cards) == 5), None
            )
            showdown = (
                river is not None
                and len(live_at_end) > 1
                and pid in {r.player_id for r in live_at_end}
            )
            result = next(r for r in hand.results if r.player_id == pid)
            add("showdown.wtsd", showdown)
            add("showdown.wwsf", result.awarded > 0)
            if showdown:
                add("showdown.wsd", result.awarded > 0)
    result = next(r for r in hand.results if r.player_id == pid)
    if hand.accounting_reconciled and result.net is not None:
        add("results.net_chips", result.net)
        add("results.mean_net", result.net)
        if hand.big_blind:
            add("results.bb100", result.net / hand.big_blind)
            add("results.bb_hand", result.net / hand.big_blind)
    if hand.history.variant == GameVariant.NLHE and result.complete_hole_cards:
        first, second = result.observed_cards
        add("starting.pair", first.code[0] == second.code[0])
        add("starting.suited", first.code[1] == second.code[1])
    return output


def compute_statistics(
    hands: tuple[Hand, ...],
    *,
    player_id: str | None = None,
    position: str | None = None,
    starting_hand: str | None = None,
    min_stack_bb: float | None = None,
    max_stack_bb: float | None = None,
) -> tuple[MetricResult, ...]:
    tallies: dict[tuple[str, str, str], _Tally] = {}
    seen: set[tuple[str, str]] = set()
    for hand in hands:
        identity = (hand.history.session_id, hand.history.hand_id)
        if identity in seen:
            raise ValueError("Duplicate hand in analytical input")
        seen.add(identity)
        for player in hand.history.players:
            pid = player.player_id
            if player_id is not None and pid.value != player_id:
                continue
            result = next(r for r in hand.results if r.player_id == pid)
            if starting_hand is not None and (
                hand.history.variant != GameVariant.NLHE
                or not result.complete_hole_cards
                or nlhe_class(result.observed_cards) != starting_hand
            ):
                continue
            if position is not None and result.position != position:
                continue
            if min_stack_bb is not None or max_stack_bb is not None:
                if not hand.big_blind:
                    continue
                depth = player.starting_stack / hand.big_blind
                if min_stack_bb is not None and depth < Decimal(str(min_stack_bb)):
                    continue
                if max_stack_bb is not None and depth > Decimal(str(max_stack_bb)):
                    continue
            samples = _samples(hand, pid) if hand.action_consistent else {}
            for metric, definition in REGISTRY.items():
                tally = tallies.setdefault(
                    (pid.value, hand.history.variant.value, metric), _Tally()
                )
                unavailable = (
                    not hand.action_consistent
                    or (
                        "known_positions" in definition.required_data
                        and any(r.position is None for r in hand.results)
                    )
                    or (
                        "reconciled_accounting" in definition.required_data
                        and not hand.accounting_reconciled
                    )
                    or (
                        "observed_nlhe_hole_cards" in definition.required_data
                        and (
                            hand.history.variant != GameVariant.NLHE
                            or not result.complete_hole_cards
                        )
                    )
                )
                if unavailable:
                    tally.excluded += 1
                    continue
                for observed_value, n in samples.get(metric, []):
                    tally.numerator += observed_value
                    tally.denominator += n
    output = []
    for (player_value, variant, metric), tally in sorted(tallies.items()):
        definition = REGISTRY[metric]
        value: Decimal | None = None
        interval = None
        if tally.denominator:
            value = (
                tally.numerator
                if definition.unit in {"count", "chips"}
                else tally.numerator / tally.denominator
            )
            if definition.unit == "bb100":
                value *= 100
            if definition.unit == "frequency":
                interval = wilson(int(tally.numerator), tally.denominator)
        output.append(
            MetricResult(
                metric,
                player_value,
                variant,
                tally.numerator,
                tally.denominator,
                value,
                tally.denominator,
                tally.excluded,
                interval,
            )
        )
    return tuple(output)
