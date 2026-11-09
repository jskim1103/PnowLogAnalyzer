"""Explicit weighted-combination models; never estimates ranges from folds."""

from dataclasses import dataclass
from decimal import Decimal
from fractions import Fraction
from itertools import combinations, product
from math import comb, log, prod, sqrt
from random import Random

from app.domain.hands import Card
from app.domain.preflop import GameVariant
from app.equity.calculator import DECK
from app.equity.evaluator import evaluate


@dataclass(frozen=True)
class WeightedCombo:
    cards: tuple[Card, ...]
    weight: Decimal


@dataclass(frozen=True)
class RangeEquityResult:
    method: str
    outcomes: int
    valid_assignments: int
    equities: tuple[float, ...]
    confidence_intervals: tuple[tuple[float, float], ...] | None
    seed: int | None
    assumptions: str = (
        "User-supplied independent combination weights, conditioned on mutually "
        "disjoint cards and the known board. Uniform remaining runouts. One equal "
        "pot, ties shared, no rake/future betting. Ranges are assumptions, never "
        "inferred observations. Monte Carlo uses 95% per-player Hoeffding bounds."
    )


def range_equity(
    ranges: tuple[tuple[WeightedCombo, ...], ...],
    board: tuple[Card, ...],
    variant: GameVariant,
    *,
    method: str = "exact",
    trials: int = 2000,
    seed: int = 0,
) -> RangeEquityResult:
    required = {GameVariant.NLHE: 2, GameVariant.PLO5: 5}.get(variant)
    if (
        required is None
        or not 2 <= len(ranges) <= 6
        or len(board) > 5
        or len(set(board)) != len(board)
        or any(not r for r in ranges)
    ):
        raise ValueError("Require 2–6 nonempty ranges and a distinct 0–5 card board")
    if method not in {"exact", "monte_carlo"} or not 1 <= trials <= 10000:
        raise ValueError("Invalid method or trial count")
    if prod(len(r) for r in ranges) > 10000:
        raise ValueError("Range assignment product exceeds 10000 combinations")
    for player_range in ranges:
        seen: set[frozenset[Card]] = set()
        for combo in player_range:
            if (
                len(combo.cards) != required
                or len(set(combo.cards)) != required
                or not combo.weight.is_finite()
                or combo.weight <= 0
            ):
                raise ValueError(
                    "Range combinations need distinct variant-sized cards "
                    "and positive finite weights"
                )
            identity = frozenset(combo.cards)
            if identity in seen:
                raise ValueError("Duplicate combination in one player range")
            seen.add(identity)
    assignments = []
    weights = []
    for combo_selection in product(*ranges):
        known_cards = board + tuple(c for combo in combo_selection for c in combo.cards)
        if len(set(known_cards)) != len(known_cards):
            continue
        assignments.append(tuple(combo.cards for combo in combo_selection))
        weights.append(
            prod(
                (Fraction(combo.weight) for combo in combo_selection), start=Fraction(1)
            )
        )
    if not assignments:
        raise ValueError("No compatible range assignments after card removal")
    draws = 5 - len(board)
    runout_count = comb(52 - len(board) - required * len(ranges), draws)
    outcomes = len(assignments) * runout_count if method == "exact" else trials
    cost = 21 if variant == GameVariant.NLHE else 100
    if outcomes * len(ranges) * cost > 500000:
        raise ValueError(
            "Range evaluation exceeds budget; "
            "use fewer combinations or Monte Carlo trials"
        )
    rng = Random(seed)
    shares = [Fraction(0) for _ in ranges]
    total_weight = sum(weights, Fraction(0))
    if method == "exact":
        for assignment, weight in zip(assignments, weights, strict=True):
            known = set(board + tuple(c for hand in assignment for c in hand))
            remaining = tuple(c for c in DECK if c not in known)
            for runout in combinations(remaining, draws):
                scores = [
                    evaluate(hand, board + tuple(runout), variant)
                    for hand in assignment
                ]
                best = max(scores)
                count = scores.count(best)
                for i, score in enumerate(scores):
                    if score == best:
                        shares[i] += weight / count
        equities = tuple(
            float(value / (total_weight * runout_count)) for value in shares
        )
        intervals = None
    else:
        # Scaling normalized weights is safe for the bounded API weight inputs;
        # incompatibility was conditioned jointly before sampling, avoiding the
        # bias of sequentially selecting ranges without the correct joint prior.
        normalized = [float(weight / total_weight) for weight in weights]
        for _ in range(trials):
            assignment = rng.choices(assignments, weights=normalized, k=1)[0]
            known = set(board + tuple(c for hand in assignment for c in hand))
            remaining = tuple(c for c in DECK if c not in known)
            runout = tuple(rng.sample(remaining, draws))
            scores = [evaluate(hand, board + runout, variant) for hand in assignment]
            best = max(scores)
            count = scores.count(best)
            for i, score in enumerate(scores):
                if score == best:
                    shares[i] += Fraction(1, count)
        equities = tuple(float(value / trials) for value in shares)
        radius = sqrt(log(40) / (2 * trials))
        intervals = tuple(
            (max(0, value - radius), min(1, value + radius)) for value in equities
        )
    return RangeEquityResult(
        method,
        outcomes,
        len(assignments),
        equities,
        intervals,
        seed if method == "monte_carlo" else None,
    )
