from decimal import Decimal as D

import pytest
from app.domain.preflop import GameVariant as V
from app.equity.ranges import WeightedCombo, range_equity
from test_equity import cards


def test_exact_weighted_equity_and_joint_blocker_conditioning():
    board = cards("3h 4c 7d 9s Tc")
    ranges = (
        (WeightedCombo(cards("Ah Ad"), D(3)), WeightedCombo(cards("2c 2d"), D(1))),
        (WeightedCombo(cards("Kc Kd"), D(1)),),
    )
    result = range_equity(ranges, board, V.NLHE)
    assert result.equities == (0.75, 0.25)
    assert result.outcomes == 2 and result.valid_assignments == 2
    blocked = (
        (WeightedCombo(cards("Ah Ad"), D(3)), WeightedCombo(cards("Kc Kd"), D(100))),
        ranges[1],
    )
    assert range_equity(blocked, board, V.NLHE).equities == (1, 0)
    mc = range_equity(ranges, board, V.NLHE, method="monte_carlo", seed=7)
    assert mc.equities[0] == pytest.approx(0.75, abs=0.03)
    assert mc == range_equity(ranges, board, V.NLHE, method="monte_carlo", seed=7)


def test_impossible_ranges_and_duplicate_combo_are_rejected():
    same = (WeightedCombo(cards("Ah Ad"), D(1)),)
    with pytest.raises(ValueError, match="compatible"):
        range_equity((same, same), (), V.NLHE)
    with pytest.raises(ValueError, match="Duplicate"):
        range_equity((same + same, (WeightedCombo(cards("Kc Kd"), D(1)),)), (), V.NLHE)


def test_omaha_weighted_known_ranges_share_a_king_high_straight():
    first = cards("Ts 9h 8d 7c 6h")
    second = cards("Td 9d 8c 7h 6c")
    board = cards("As Ks Qs Js 2h")
    ranges = ((WeightedCombo(first, D(1)),), (WeightedCombo(second, D(1)),))
    assert range_equity(ranges, board, V.PLO5).equities == (0.5, 0.5)
