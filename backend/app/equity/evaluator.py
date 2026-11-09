"""Transparent reference evaluator, higher lexicographic ranks are stronger."""

from collections import Counter
from functools import lru_cache
from itertools import combinations

from app.domain.hands import Card
from app.domain.preflop import GameVariant

RANKS = "23456789TJQKA"
CATEGORIES = (
    "High card",
    "Pair",
    "Two pair",
    "Three of a kind",
    "Straight",
    "Flush",
    "Full house",
    "Four of a kind",
    "Straight flush",
)


@lru_cache(maxsize=32768)
def _five(codes: tuple[str, ...]) -> tuple[int, ...]:
    ranks = sorted((RANKS.index(code[0]) + 2 for code in codes), reverse=True)
    counts = Counter(ranks)
    grouped = sorted(((count, rank) for rank, count in counts.items()), reverse=True)
    unique = sorted(counts, reverse=True)
    straight = 0
    if len(unique) == 5:
        if unique[0] - unique[-1] == 4:
            straight = unique[0]
        elif unique == [14, 5, 4, 3, 2]:
            straight = 5
    flush = len({code[1] for code in codes}) == 1
    if flush and straight:
        return 8, straight
    if grouped[0][0] == 4:
        return 7, grouped[0][1], grouped[1][1]
    if [g[0] for g in grouped] == [3, 2]:
        return 6, grouped[0][1], grouped[1][1]
    if flush:
        return (5, *ranks)
    if straight:
        return 4, straight
    if grouped[0][0] == 3:
        return (
            3,
            grouped[0][1],
            *sorted((r for r in ranks if r != grouped[0][1]), reverse=True),
        )
    if [g[0] for g in grouped[:2]] == [2, 2]:
        pair_ranks = sorted((g[1] for g in grouped if g[0] == 2), reverse=True)
        return (2, *pair_ranks, next(g[1] for g in grouped if g[0] == 1))
    if grouped[0][0] == 2:
        return (
            1,
            grouped[0][1],
            *sorted((r for r in ranks if r != grouped[0][1]), reverse=True),
        )
    return (0, *ranks)


def evaluate_five(cards: tuple[Card, ...]) -> tuple[int, ...]:
    if len(cards) != 5 or len(set(cards)) != 5:
        raise ValueError("Exactly five distinct cards required")
    return _five(tuple(sorted(card.code for card in cards)))


def evaluate(
    hole: tuple[Card, ...], board: tuple[Card, ...], variant: GameVariant
) -> tuple[int, ...]:
    required = {GameVariant.NLHE: 2, GameVariant.PLO5: 5}.get(variant)
    if required is None or len(hole) != required or not 3 <= len(board) <= 5:
        raise ValueError("Known complete hole cards and a 3–5 card board are required")
    if len(set(hole + board)) != len(hole + board):
        raise ValueError("Duplicate cards")
    if variant == GameVariant.NLHE:
        return max(evaluate_five(tuple(hand)) for hand in combinations(hole + board, 5))
    return max(
        evaluate_five(tuple(h) + tuple(b))
        for h in combinations(hole, 2)
        for b in combinations(board, 3)
    )
