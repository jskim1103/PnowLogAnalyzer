"""Deterministic chip ledger, betting state and observable settlement checks."""

from collections import deque
from dataclasses import dataclass
from decimal import Decimal

from app.domain.hands import (
    Board,
    Card,
    Decision,
    Diagnostic,
    Hand,
    HandHistory,
    PlayerResult,
    PlayerState,
    Pot,
    Street,
)
from app.domain.hands import (
    EventKind as K,
)
from app.domain.players import PlayerId
from app.domain.preflop import GameVariant

ZERO = Decimal(0)
FORCED = {K.SMALL_BLIND, K.BIG_BLIND}
DECISIONS = {K.FOLD, K.CHECK, K.CALL, K.BET, K.RAISE}


@dataclass
class _Player:
    remaining: Decimal
    committed: Decimal = ZERO
    contributed: Decimal = ZERO
    returned: Decimal = ZERO
    awarded: Decimal = ZERO
    folded: bool = False


def positions(history: HandHistory) -> dict[PlayerId, str]:
    ordered = sorted(history.players, key=lambda p: p.seat)
    ids = [p.player_id for p in ordered]
    if history.button not in ids or len(ids) < 2:
        return {}
    if history.dead_small_blind:
        big_blind = next(
            (e.player_id for e in history.events if e.kind == K.BIG_BLIND), None
        )
        roles = {history.button: "BTN"}
        if big_blind is not None and big_blind != history.button and big_blind in ids:
            roles[big_blind] = "BB"
        return roles
    index = ids.index(history.button)
    rotated = ids[index:] + ids[:index]
    if len(ids) == 2:
        return dict(zip(rotated, ("BTN/SB", "BB"), strict=True))
    remaining = len(ids) - 3
    if remaining <= 2:
        early = ["HJ", "CO"][-remaining:] if remaining else []
    else:
        early = ["UTG"] + [f"UTG+{i}" for i in range(1, remaining - 2)] + ["HJ", "CO"]
    return dict(zip(rotated, ["BTN", "SB", "BB"] + early, strict=True))


def side_pots(
    contributions: dict[PlayerId, Decimal], folded: set[PlayerId]
) -> tuple[Pot, ...]:
    levels = sorted({amount for amount in contributions.values() if amount > 0})
    previous = ZERO
    pots = []
    for level in levels:
        members = [p for p, amount in contributions.items() if amount >= level]
        amount = (level - previous) * len(members)
        pots.append(Pot(amount, tuple(p for p in members if p not in folded), level))
        previous = level
    return tuple(pots)


def _awards_feasible(pots: tuple[Pot, ...], awards: dict[PlayerId, Decimal]) -> bool:
    """Exact max flow checks award eligibility without inventing source allocation."""
    source, sink = "source", "sink"
    capacity: dict[tuple[str, str], Decimal] = {}
    neighbors: dict[str, set[str]] = {}

    def edge(a: str, b: str, value: Decimal) -> None:
        capacity[a, b] = value
        capacity[b, a] = ZERO
        neighbors.setdefault(a, set()).add(b)
        neighbors.setdefault(b, set()).add(a)

    for i, pot in enumerate(pots):
        node = f"pot:{i}"
        edge(source, node, pot.amount)
        for player in pot.eligible:
            edge(node, "player:" + player.value, pot.amount)
    for player, amount in awards.items():
        edge("player:" + player.value, sink, amount)
    flow = ZERO
    while True:
        parent: dict[str, str] = {}
        queue = deque([source])
        visited = {source}
        while queue and sink not in visited:
            node = queue.popleft()
            for neighbor in sorted(neighbors.get(node, set())):
                if neighbor not in visited and capacity[node, neighbor] > 0:
                    visited.add(neighbor)
                    parent[neighbor] = node
                    queue.append(neighbor)
        if sink not in visited:
            break
        node = sink
        limit: Decimal | None = None
        while node != source:
            prev = parent[node]
            limit = (
                capacity[prev, node]
                if limit is None
                else min(limit, capacity[prev, node])
            )
            node = prev
        assert limit is not None
        node = sink
        while node != source:
            prev = parent[node]
            capacity[prev, node] -= limit
            capacity[node, prev] += limit
            node = prev
        flow += limit
    return flow == sum(awards.values(), ZERO)


def reconstruct(history: HandHistory) -> Hand:
    diagnostics = list(history.diagnostics)
    states = {p.player_id: _Player(p.starting_stack) for p in history.players}
    players = {p.player_id: p for p in history.players}
    seats = sorted(states, key=lambda pid: players[pid].seat)
    labels = positions(history)
    street = Street.PREFLOP
    boards: dict[int, tuple[Card, ...]] = {}
    holes: dict[PlayerId, tuple[Card, ...]] = {}
    decisions: list[Decision] = []
    pending: set[PlayerId] = set(states)
    responded: dict[PlayerId, Decimal] = {}
    aggressor: PlayerId | None = None
    cursor: PlayerId | None = None
    first_postflop: PlayerId | None = history.button
    small: Decimal | None = None
    big: Decimal | None = None
    minimum = ZERO
    awards_started = False
    betting_started = False
    expected_runs = 1

    def issue(
        code: str, message: str, order: int | None = None, severity: str = "error"
    ) -> None:
        diagnostics.append(Diagnostic(code, message, order, severity))

    if not history.boundaries_valid:
        issue("invalid_boundaries", "Matching unique hand boundaries are required")
    if history.variant == GameVariant.UNKNOWN:
        issue("unsupported_variant", "Unknown betting variant")
    if (
        len(states) < 2
        or len(states) != len(history.players)
        or len({p.seat for p in history.players}) != len(states)
        or any(p.starting_stack <= 0 or p.seat <= 0 for p in history.players)
    ):
        issue("invalid_roster", "Starting participants, seats or stacks are invalid")
    if history.button is None:
        issue(
            "unknown_button",
            "Dead/missing button: named positions unavailable",
            severity="warning",
        )
    elif history.dead_small_blind:
        issue(
            "partial_positions",
            "Dead small blind: only explicit button/BB roles assigned",
            severity="warning",
        )

    def live() -> set[PlayerId]:
        return {p for p, s in states.items() if not s.folded}

    def able() -> set[PlayerId]:
        return {p for p in live() if states[p].remaining > 0}

    def pot() -> Decimal:
        return sum(
            (s.contributed - s.returned - s.awarded for s in states.values()), ZERO
        )

    def close_pending() -> set[PlayerId]:
        needed = pending & able()
        active = live()
        if len(active) <= 1:
            return set()
        capable = able()
        if len(capable) == 1:
            p = next(iter(capable))
            if states[p].committed >= max(
                (states[o].committed for o in active - {p}), default=ZERO
            ):
                needed.discard(p)
        return needed

    def next_player(
        after: PlayerId | None, candidates: set[PlayerId]
    ) -> PlayerId | None:
        if not seats or not candidates:
            return None
        start = seats.index(after) + 1 if after in seats else 0
        rotated = seats[start:] + seats[:start]
        return next((p for p in rotated if p in candidates), None)

    orders = [e.order for e in history.events]
    if orders != sorted(set(orders)):
        issue(
            "invalid_event_order", "Events must have unique ascending sequence values"
        )
    for event in history.events:
        kind = event.kind
        if kind == K.RUN_TWICE:
            expected_runs = 2
            continue
        if kind == K.UNKNOWN:
            issue("unknown_event", "Unrecognized event preserved", event.order)
            continue
        if kind == K.BOARD:
            run = event.run or 1
            expected_runs = max(expected_runs, run)
            target_street = event.street
            lengths = {Street.FLOP: 3, Street.TURN: 4, Street.RIVER: 5}
            if (
                target_street not in lengths
                or len(event.cards) != lengths[target_street]
            ):
                issue(
                    "invalid_board", "Board length disagrees with street", event.order
                )
                continue
            prior = boards.get(run, ())
            if prior and event.cards[: len(prior)] != prior:
                issue(
                    "changed_board",
                    "Previously observed board cards changed",
                    event.order,
                )
            if run == 1:
                if close_pending():
                    issue(
                        "incomplete_betting_round",
                        "Street advanced with pending decisions",
                        event.order,
                    )
                expected = {
                    Street.PREFLOP: Street.FLOP,
                    Street.FLOP: Street.TURN,
                    Street.TURN: Street.RIVER,
                }
                if expected.get(street) != target_street:
                    issue(
                        "invalid_street_transition",
                        "Skipped or repeated betting street",
                        event.order,
                    )
                street = target_street
                for s in states.values():
                    s.committed = ZERO
                pending = able()
                responded.clear()
                minimum = big or ZERO
                aggressor = None
                cursor = first_postflop
            elif len(able()) > 1:
                issue(
                    "second_run_with_betting",
                    "Second board while two players can still bet",
                    event.order,
                )
            boards[run] = event.cards
            continue
        if kind in {K.SHOW, K.PRIVATE_CARDS}:
            if event.player_id is not None:
                if event.player_id not in states:
                    issue(
                        "unknown_card_owner",
                        "Cards attributed to a non-participant",
                        event.order,
                    )
                    continue
                prior = holes.get(event.player_id, ())
                observed = tuple(dict.fromkeys(prior + event.cards))
                required = 2 if history.variant == GameVariant.NLHE else 5
                if len(observed) > required or len(set(event.cards)) != len(
                    event.cards
                ):
                    issue(
                        "invalid_hole_cards",
                        "Too many or repeated observed hole cards",
                        event.order,
                    )
                holes[event.player_id] = observed
            continue
        if kind == K.OBSERVATION:
            continue
        pid = event.player_id
        if pid not in states:
            issue(
                "unknown_actor", "Event actor is not a dealt participant", event.order
            )
            continue
        assert pid is not None
        state = states[pid]
        amount = event.amount
        if kind == K.RETURN:
            if (
                amount is None
                or amount <= 0
                or amount > state.committed
                or amount > state.contributed - state.returned
            ):
                issue(
                    "invalid_return", "Return exceeds recorded commitment", event.order
                )
                continue
            other_max = max(
                (s.committed for p, s in states.items() if p != pid), default=ZERO
            )
            if amount > max(ZERO, state.committed - other_max):
                issue("invalid_return", "Returned chips are not unmatched", event.order)
            state.returned += amount
            state.remaining += amount
            state.committed -= amount
            continue
        if kind == K.AWARD:
            awards_started = True
            if close_pending():
                issue(
                    "incomplete_betting_round",
                    "Award before betting completes",
                    event.order,
                )
            if amount is None or amount <= 0:
                issue("invalid_award", "Award must be positive", event.order)
                continue
            if state.folded:
                issue("folded_winner", "Folded player received an award", event.order)
            state.awarded += amount
            # Remain separate from the betting stack until final settlement.
            continue
        if kind not in FORCED | DECISIONS:
            issue("unsupported_event", "Unsupported normalized event", event.order)
            continue
        if awards_started:
            issue(
                "action_after_award",
                "Betting occurred after settlement began",
                event.order,
            )
        if state.folded:
            issue("action_after_fold", "Folded player acted again", event.order)
        if state.remaining == 0:
            issue("action_after_all_in", "All-in player acted again", event.order)
        wager = max((s.committed for s in states.values()), default=ZERO)
        facing = max(ZERO, wager - state.committed)
        can_raise = (pid not in responded or wager - responded[pid] >= minimum) and (
            state.remaining > facing
            and any(states[p].remaining > 0 for p in live() if p != pid)
        )
        before = tuple(
            PlayerState(
                p, s.remaining, s.committed, s.contributed, s.folded, s.remaining == 0
            )
            for p, s in states.items()
        )
        active = tuple(p for p in seats if p in live())
        others = [states[p].remaining for p in live() if p != pid]
        effective = min(state.remaining, max(others, default=ZERO))
        prior_pot = pot()
        actor_remaining = state.remaining
        previous_aggressor = aggressor
        if kind in FORCED:
            if street != Street.PREFLOP or betting_started or state.committed != 0:
                issue(
                    "invalid_forced_post",
                    "Forced blind posted outside initial setup",
                    event.order,
                )
            if kind == K.SMALL_BLIND:
                if small is not None:
                    issue("duplicate_blind", "Multiple small blinds", event.order)
                small = amount
                if history.button is None:
                    first_postflop = (
                        pid
                        if len(seats) == 2
                        else seats[(seats.index(pid) - 1) % len(seats)]
                    )
            else:
                if big is not None:
                    issue("duplicate_blind", "Multiple big blinds", event.order)
                big = amount
                minimum = amount or ZERO
                cursor = pid
                if history.button is None and small is None:
                    first_postflop = seats[(seats.index(pid) - 1) % len(seats)]
            added = amount or ZERO
        else:
            betting_started = True
            expected_player = next_player(cursor, close_pending())
            if expected_player is not None and pid != expected_player:
                issue(
                    "out_of_turn",
                    "Actor does not match active-seat turn order",
                    event.order,
                )
            if pid not in close_pending():
                issue(
                    "unexpected_action",
                    "Actor has no pending betting decision",
                    event.order,
                )
            added = ZERO
            if kind == K.FOLD:
                state.folded = True
            elif kind == K.CHECK:
                if facing:
                    issue(
                        "check_facing_bet",
                        "Cannot check facing an unmatched bet",
                        event.order,
                    )
            elif kind in {K.CALL, K.BET, K.RAISE}:
                if amount is None or amount <= 0:
                    issue("invalid_amount", "Investment must be positive", event.order)
                target = (
                    amount if event.street_total else state.committed + (amount or ZERO)
                )
                target = target or ZERO
                added = target - state.committed
                if added <= 0:
                    issue(
                        "nonpositive_investment", "No positive chips added", event.order
                    )
                is_all_in = added == state.remaining
                if kind == K.CALL:
                    if (
                        target > wager
                        or (target < wager and not is_all_in)
                        or facing == 0
                    ):
                        issue(
                            "invalid_call",
                            "Call does not match the wager or close an all-in",
                            event.order,
                        )
                else:
                    if kind == K.BET and wager > 0:
                        issue(
                            "bet_facing_bet",
                            "Use raise when a wager already exists",
                            event.order,
                        )
                    if kind == K.RAISE and wager == 0:
                        issue(
                            "raise_without_bet",
                            "Raise requires an existing bet",
                            event.order,
                        )
                    if target <= wager:
                        issue(
                            "invalid_raise",
                            "Aggression must increase the wager",
                            event.order,
                        )
                    if not can_raise:
                        issue(
                            "raise_not_reopened",
                            "Short all-in did not reopen raising rights",
                            event.order,
                        )
                    increment = target - wager
                    if increment < minimum and not is_all_in:
                        issue(
                            "undersized_raise",
                            "Below minimum increase without being all-in",
                            event.order,
                        )
                    if (
                        history.variant == GameVariant.PLO5
                        and added > prior_pot + 2 * facing
                    ):
                        issue(
                            "pot_limit_exceeded",
                            "Investment exceeds pot-limit maximum",
                            event.order,
                        )
                    if increment >= minimum:
                        minimum = increment
                    pending = able() - {pid}
                    aggressor = pid
            pending.discard(pid)
            responded[pid] = max(wager, state.committed + added)
            cursor = pid
        if added < 0 or added > state.remaining:
            issue(
                "stack_exceeded",
                "Contribution exceeds available stack or is negative",
                event.order,
            )
            # Preserve the invalid event, but do not corrupt the recoverable ledger.
            added = ZERO
        state.remaining -= added
        state.committed += added
        state.contributed += added
        if event.all_in and state.remaining != 0:
            issue(
                "inconsistent_all_in",
                "All-in flag disagrees with available stack",
                event.order,
            )
        if state.remaining == 0:
            pending.discard(pid)
        if kind in DECISIONS:
            ip: bool | None = None
            if history.button is not None and len(active) > 1:
                order = []
                start = seats.index(history.button) + 1
                for p in seats[start:] + seats[:start]:
                    if p in active:
                        order.append(p)
                ip = bool(order and order[-1] == pid)
            decisions.append(
                Decision(
                    event,
                    street,
                    boards.get(1, ()),
                    prior_pot,
                    facing,
                    min(facing, actor_remaining),
                    effective,
                    previous_aggressor,
                    active,
                    before,
                    can_raise,
                    ip,
                    labels.get(pid),
                    added,
                    state.committed,
                    pot(),
                )
            )
    if big is None or (small is None and not history.dead_small_blind):
        issue("missing_blinds", "Required blind evidence is missing")
    if close_pending():
        issue("incomplete_betting_round", "Hand ended with pending decisions")
    # Validate card identities, allowing only the identical positional shared prefix
    # across runouts. Unattributed private observations are never assigned by guess.
    owners: dict[Card, str] = {}
    for pid, cards in holes.items():
        for card in cards:
            if card in owners and owners[card] != pid.value:
                issue("duplicate_card", "Same card attributed to different players")
            owners[card] = pid.value
    board_seen: dict[Card, int] = {}
    for run, cards in sorted(boards.items()):
        if len(set(cards)) != len(cards):
            issue("duplicate_card", "Repeated card on a board")
        for i, card in enumerate(cards):
            if card in owners:
                issue("duplicate_card", "Hole card also appears on a board")
            if card in board_seen:
                first = boards[1] if 1 in boards else ()
                common = 0
                for a, b in zip(first, cards):
                    if a != b:
                        break
                    common += 1
                if i >= common or board_seen[card] != i:
                    issue("duplicate_card", "Repeated card beyond shared runout prefix")
            else:
                board_seen[card] = i
    contributions = {p: s.contributed - s.returned for p, s in states.items()}
    pots = side_pots(contributions, {p for p, s in states.items() if s.folded})
    levels = sorted(contributions.values(), reverse=True)
    if len(levels) >= 2 and levels[0] > levels[1]:
        issue("missing_uncalled_return", "Unique excess contribution was not returned")
    if any(not p.eligible for p in pots):
        issue("empty_pot_eligibility", "Pot has no eligible recipient")
    if pots and sum(s.awarded for s in states.values()) != sum(contributions.values()):
        issue(
            "unbalanced_settlement",
            "Awards differ from net contributions (no rake assumed)",
        )
    if not awards_started:
        issue("missing_settlement", "No pot award was observed")
    if (
        awards_started
        and len(live()) > 1
        and any(len(boards.get(run, ())) != 5 for run in range(1, expected_runs + 1))
    ):
        issue("incomplete_showdown_board", "Showdown requires every announced runout")
    awards = {p: s.awarded for p, s in states.items()}
    feasible = _awards_feasible(pots, awards)
    if not feasible:
        issue(
            "ineligible_awards",
            "Awards cannot be funded by eligible side-pot layers",
        )
    accounting_codes = {
        "invalid_roster",
        "invalid_boundaries",
        "unknown_actor",
        "invalid_return",
        "invalid_award",
        "stack_exceeded",
        "unbalanced_settlement",
        "missing_settlement",
        "ineligible_awards",
        "missing_uncalled_return",
        "empty_pot_eligibility",
        "unknown_event",
        "folded_winner",
    }
    accounting = (
        awards_started
        and history.boundaries_valid
        and feasible
        and not any(
            d.code in accounting_codes and d.severity == "error" for d in diagnostics
        )
    )
    consistent = not any(d.severity == "error" for d in diagnostics)
    required = 2 if history.variant == GameVariant.NLHE else 5
    results = tuple(
        PlayerResult(
            p,
            labels.get(p),
            s.contributed,
            s.returned,
            s.awarded,
            s.awarded - s.contributed + s.returned if accounting else None,
            players[p].starting_stack + s.awarded - s.contributed + s.returned
            if accounting
            else None,
            holes.get(p, ()),
            len(holes.get(p, ())) == required,
            s.folded,
        )
        for p, s in states.items()
    )
    incomplete_codes = {
        "invalid_boundaries",
        "unknown_event",
        "missing_or_multiple_rosters",
        "malformed_event",
        "unsupported_variant",
        "incomplete_showdown_board",
    }
    if accounting and consistent:
        status = "reconciled"
    elif any(d.code in incomplete_codes for d in diagnostics):
        status = "partial"
    else:
        status = "invalid"
    return Hand(
        history,
        tuple(decisions),
        tuple(Board(run, cards) for run, cards in sorted(boards.items())),
        pots,
        results,
        small,
        big,
        accounting,
        consistent,
        status,
        tuple(diagnostics),
    )
