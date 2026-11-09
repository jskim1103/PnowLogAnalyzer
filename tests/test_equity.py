from decimal import Decimal as D
from fractions import Fraction

import pytest
from app.domain.hands import Card
from app.domain.preflop import GameVariant as V
from app.equity.calculator import calculate_equity, draw_probability
from app.equity.evaluator import evaluate, evaluate_five
from app.strategy.ev import bluff_model, call_ev


def cards(text):
    return tuple(Card(c) for c in text.split())


@pytest.mark.parametrize(
    "text,category",
    [
        ("As Ks Qs Js Ts", 8),
        ("As Ah Ad Ac 2s", 7),
        ("As Ah Ad 2s 2h", 6),
        ("As Js 8s 5s 2s", 5),
        ("As 2h 3d 4c 5s", 4),
        ("As Ah Ad 3s 2s", 3),
        ("As Ah 2d 2c 5s", 2),
        ("As Ah Kd Qc 5s", 1),
        ("As Kh 8d 6c 2s", 0),
    ],
)
def test_independent_rank_categories(text, category):
    assert evaluate_five(cards(text))[0] == category


def test_wheel_kickers_and_omaha_exactly_two_hole_cards():
    assert evaluate_five(cards("As 2h 3d 4c 5s")) < evaluate_five(
        cards("2s 3h 4d 5c 6s")
    )
    assert evaluate_five(cards("As Ah Kd Qc 5s")) > evaluate_five(
        cards("As Ah Jd Tc 9s")
    )
    board = cards("As Ks Qs Js 2h")
    assert evaluate(cards("Ts 9h"), board, V.NLHE)[0] == 8
    assert evaluate(cards("Ts 9h 8d 7c 6h"), board, V.PLO5)[0] != 8
    assert evaluate(cards("Ts 9s 8d 7c 6h"), board, V.PLO5)[0] == 8


def test_exact_equity_counts_blockers_and_ties():
    aa, kk = cards("Ac Ad"), cards("Kc Kd")
    result = calculate_equity((aa, kk), cards("2s 3h 7c 9h"), V.NLHE)
    assert result.outcomes == 44
    assert result.equities == (42 / 44, 2 / 44)
    tied = calculate_equity(
        (cards("2c 3c"), cards("4c 5c")), cards("As Ks Qs Js Ts"), V.NLHE
    )
    assert tied.equities == (0.5, 0.5) and tied.ties == (1, 1)


def test_seeded_monte_carlo_tracks_exact_and_rejects_duplicate_cards():
    hands = (cards("Ac Ad"), cards("Kc Kd"))
    board = cards("2s 3h 7c 9h")
    result = calculate_equity(hands, board, V.NLHE, method="monte_carlo", seed=41)
    assert result == calculate_equity(
        hands, board, V.NLHE, method="monte_carlo", seed=41
    )
    assert result.equities[0] == pytest.approx(42 / 44, abs=0.025)
    assert sum(result.equities) == pytest.approx(1)
    with pytest.raises(ValueError, match="Duplicate"):
        calculate_equity((hands[0], hands[0]), board, V.NLHE)
    with pytest.raises(ValueError, match="budget"):
        calculate_equity(hands, (), V.NLHE)


def test_draw_and_ev_math_assumptions():
    assert draw_probability(47, 9, 1) == Fraction(9, 47)
    assert draw_probability(47, 9, 2) == 1 - Fraction(38 * 37, 47 * 46)
    result = call_ev(D(100), D(50), D(".4"))
    assert result["call_ev"] == 10 and result["required_equity"] == D(1) / 3
    with pytest.raises(ValueError, match="close"):
        call_ev(D(100), D(50), D(".4"), closes_betting=False)
    assert abs(bluff_model(D(100), D(50), D(1) / 3)["ev"]) < D("1e-24")
