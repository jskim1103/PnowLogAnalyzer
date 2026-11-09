from collections import Counter
from itertools import combinations

from app.domain.cards import nlhe_class, plo5_features
from app.domain.hands import Card

DECK = tuple(Card(rank + suit) for rank in "23456789TJQKA" for suit in "cdhs")


def test_all_1326_combinations_map_to_169_classes_with_known_multiplicities():
    counts = Counter(nlhe_class(tuple(combo)) for combo in combinations(DECK, 2))
    assert len(counts) == 169 and sum(counts.values()) == 1326
    assert counts["AA"] == 6 and counts["AKs"] == 4 and counts["AKo"] == 12
    assert nlhe_class((Card("Kh"), Card("Ah"))) == "AKs"


def test_plo5_descriptive_features_are_not_holdem_classes():
    cards = tuple(Card(code) for code in ("As", "Ks", "Qh", "Jh", "Ac"))
    assert plo5_features(cards) == {
        "suit_pattern": "2-2-1",
        "rank_pattern": "2-1-1-1",
        "ace_count": "2",
        "broadway_count": "5",
    }
