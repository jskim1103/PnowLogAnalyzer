"""Exhaustively compare all five-card categories to independent combinatorics."""

from collections import Counter
from itertools import combinations
from math import comb
from time import perf_counter

from app.domain.hands import Card
from app.equity.evaluator import evaluate_five

if __name__ == "__main__":
    # Derive category counts from ranks and suits, independently of the evaluator.
    expected = {
        8: 4 * 10,
        7: 13 * 12 * 4,
        6: 13 * comb(4, 3) * 12 * comb(4, 2),
        5: 4 * comb(13, 5) - 4 * 10,
        4: 10 * 4**5 - 4 * 10,
        3: 13 * comb(4, 3) * comb(12, 2) * 4**2,
        2: comb(13, 2) * comb(4, 2) ** 2 * 11 * 4,
        1: 13 * comb(4, 2) * comb(12, 3) * 4**3,
        0: (comb(13, 5) - 10) * (4**5 - 4),
    }
    assert sum(expected.values()) == comb(52, 5)
    deck = tuple(Card(rank + suit) for rank in "23456789TJQKA" for suit in "cdhs")
    print(f"Verifying all {comb(52, 5):,} distinct five-card hands...", flush=True)
    start = perf_counter()
    actual = Counter(evaluate_five(tuple(hand))[0] for hand in combinations(deck, 5))
    if dict(actual) != expected:
        raise SystemExit(f"Category mismatch: {dict(actual)} != {expected}")
    print(
        "All nine category counts match independent formulas "
        f"({perf_counter() - start:.2f}s)."
    )
