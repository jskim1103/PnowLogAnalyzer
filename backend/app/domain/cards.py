"""Observed starting-card classifications, without inferred strength or ranges."""

from collections import Counter

from app.domain.hands import Card

RANKS = "23456789TJQKA"


def nlhe_class(cards: tuple[Card, ...]) -> str:
    if len(cards) != 2 or len(set(cards)) != 2:
        raise ValueError("Two distinct observed hole cards required")
    first, second = sorted(cards, key=lambda c: RANKS.index(c.code[0]), reverse=True)
    ranks = first.code[0] + second.code[0]
    if first.code[0] == second.code[0]:
        return ranks
    return ranks + ("s" if first.code[1] == second.code[1] else "o")


def plo5_features(cards: tuple[Card, ...]) -> dict[str, str]:
    if len(cards) != 5 or len(set(cards)) != 5:
        raise ValueError("Five distinct observed hole cards required")
    suits = sorted(Counter(c.code[1] for c in cards).values(), reverse=True)
    ranks = sorted(Counter(c.code[0] for c in cards).values(), reverse=True)
    return {
        "suit_pattern": "-".join(map(str, suits)),
        "rank_pattern": "-".join(map(str, ranks)),
        "ace_count": str(sum(c.code[0] == "A" for c in cards)),
        "broadway_count": str(sum(c.code[0] in "TJQKA" for c in cards)),
    }
