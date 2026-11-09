"""Resource-bounded exact and deterministic Monte Carlo known-hand equity."""

from dataclasses import dataclass
from fractions import Fraction
from itertools import combinations
from math import comb, log, sqrt
from random import Random

from app.domain.hands import Card
from app.domain.preflop import GameVariant
from app.equity.evaluator import evaluate

DECK = tuple(Card(rank + suit) for rank in "23456789TJQKA" for suit in "cdhs")


@dataclass(frozen=True)
class EquityResult:
    method: str
    outcomes: int
    equities: tuple[float, ...]
    wins: tuple[int, ...]
    ties: tuple[int, ...]
    confidence_intervals: tuple[tuple[float, float], ...] | None
    seed: int | None
    assumptions: str = (
        "Known fixed hole cards, uniform remaining deck, one equal pot, "
        "no rake or future betting. Ties split equally. No inferred ranges. "
        "Monte Carlo intervals are 95% per-player Hoeffding bounds."
    )


def calculate_equity(
    hands: tuple[tuple[Card, ...], ...],
    board: tuple[Card, ...],
    variant: GameVariant,
    *,
    method: str = "exact",
    trials: int = 2000,
    seed: int = 0,
) -> EquityResult:
    if method not in {"exact", "monte_carlo"}:
        raise ValueError("Method must be exact or monte_carlo")
    if not 2 <= len(hands) <= 6 or not 0 <= len(board) <= 5 or not 1 <= trials <= 10000:
        raise ValueError("Require 2–6 players, 0–5 board cards and 1–10000 trials")
    needed = {GameVariant.NLHE: 2, GameVariant.PLO5: 5}.get(variant)
    if needed is None or any(len(hand) != needed for hand in hands):
        raise ValueError("Hole-card count disagrees with the variant")
    known = board + tuple(card for hand in hands for card in hand)
    if len(set(known)) != len(known):
        raise ValueError("Duplicate known cards")
    remaining = tuple(card for card in DECK if card not in set(known))
    draws = 5 - len(board)
    possibilities = comb(len(remaining), draws)
    outcomes = possibilities if method == "exact" else trials
    cost_per_player = 21 if variant == GameVariant.NLHE else 100
    if outcomes * len(hands) * cost_per_player > 500000:
        raise ValueError(
            "Calculation exceeds the reference evaluator budget; "
            "use Monte Carlo or fewer trials"
        )
    rng = Random(seed)
    runouts = (
        combinations(remaining, draws)
        if method == "exact"
        else (tuple(rng.sample(remaining, draws)) for _ in range(trials))
    )
    shares = [Fraction(0) for _ in hands]
    wins = [0 for _ in hands]
    ties = [0 for _ in hands]
    for runout in runouts:
        scores = [evaluate(hand, board + tuple(runout), variant) for hand in hands]
        best = max(scores)
        winners = [i for i, score in enumerate(scores) if score == best]
        for i in winners:
            share = Fraction(1, len(winners))
            shares[i] += share
            if len(winners) == 1:
                wins[i] += 1
            else:
                ties[i] += 1
    means = tuple(float(share / outcomes) for share in shares)
    intervals = None
    if method == "monte_carlo":
        # Hoeffding bounds apply to bounded fractional pot shares, including ties.
        # Unlike a normal approximation, all sampled wins do not imply certainty.
        radius = sqrt(log(40) / (2 * outcomes))
        intervals = tuple(
            (max(0, mean - radius), min(1, mean + radius)) for mean in means
        )
    return EquityResult(
        method,
        outcomes,
        means,
        tuple(wins),
        tuple(ties),
        intervals,
        seed if method == "monte_carlo" else None,
    )


def draw_probability(unseen: int, outs: int, draws: int) -> Fraction:
    if not 0 <= outs <= unseen or not 0 <= draws <= unseen:
        raise ValueError("Outs and draws must be within the unseen deck")
    misses = comb(unseen - outs, draws) if unseen - outs >= draws else 0
    return 1 - Fraction(misses, comb(unseen, draws))
