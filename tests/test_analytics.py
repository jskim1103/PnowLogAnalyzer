from decimal import Decimal as D

import pytest
from app.domain.hands import EventKind as K
from app.reconstruction.engine import reconstruct
from app.stats.analytics import compute_statistics, wilson
from app.stats.registry import REGISTRY
from test_reconstruction import A, B, C, ev, flop, history


def rows_for(events, stacks=("50", "50")):
    hand = reconstruct(history(events, stacks))
    assert hand.action_consistent, [d.code for d in hand.diagnostics]
    return {(r.player_id, r.metric_id): r for r in compute_statistics((hand,))}


def raised_prefix():
    return [
        ev(1, K.SMALL_BLIND, A, ".25"),
        ev(2, K.BIG_BLIND, B, ".50"),
        ev(3, K.RAISE, A, "1.50", street_total=True),
        ev(4, K.CALL, B, "1.50", street_total=True),
    ]


def test_hand_calculated_preflop_cbet_and_profit_families():
    rows = rows_for(
        raised_prefix()
        + [
            flop(),
            ev(6, K.CHECK, B),
            ev(7, K.BET, A, "1"),
            ev(8, K.FOLD, B),
            ev(9, K.RETURN, A, "1"),
            ev(10, K.AWARD, A, "3"),
        ]
    )
    for metric in ("preflop.vpip", "preflop.pfr", "preflop.rfi", "flop.cbet"):
        assert rows[A.value, metric].value == 1
    assert rows[B.value, "preflop.pfr"].value == 0
    assert rows[B.value, "preflop.three_bet"].denominator == 1
    assert rows[B.value, "flop.fold_to_cbet"].value == 1
    assert rows[A.value, "results.net_chips"].value == D("1.5")
    assert rows[A.value, "results.bb100"].value == 300
    assert rows[B.value, "showdown.wtsd"].value == 0
    assert rows[A.value, "flop.af"].value is None  # No calls, not infinite AF.


def test_donk_removes_cbet_opportunity():
    rows = rows_for(
        raised_prefix()
        + [
            flop(),
            ev(6, K.BET, B, "1"),
            ev(7, K.FOLD, A),
            ev(8, K.RETURN, B, "1"),
            ev(9, K.AWARD, B, "3"),
        ]
    )
    assert rows[A.value, "flop.cbet"].denominator == 0
    assert rows[A.value, "flop.fold_facing_bet"].value == 1


def test_check_raise_denominator_is_facing_bet_after_check():
    rows = rows_for(
        raised_prefix()
        + [
            flop(),
            ev(6, K.CHECK, B),
            ev(7, K.BET, A, "1"),
            ev(8, K.RAISE, B, "3", street_total=True),
            ev(9, K.FOLD, A),
            ev(10, K.RETURN, B, "2"),
            ev(11, K.AWARD, B, "5"),
        ]
    )
    assert rows[B.value, "flop.check_raise"].value == 1
    assert rows[A.value, "flop.fold_to_cbet"].denominator == 0
    assert rows[B.value, "flop.raise_to_cbet"].value == 1


def test_three_bet_and_response_use_opportunities_not_dealt_hands():
    rows = rows_for(
        [
            ev(1, K.SMALL_BLIND, A, ".25"),
            ev(2, K.BIG_BLIND, B, ".50"),
            ev(3, K.RAISE, A, "1.50", street_total=True),
            ev(4, K.RAISE, B, "4.50", street_total=True),
            ev(5, K.FOLD, A),
            ev(6, K.RETURN, B, "3"),
            ev(7, K.AWARD, B, "3"),
        ]
    )
    assert rows[B.value, "preflop.three_bet"].value == 1
    assert rows[A.value, "preflop.three_bet"].value is None
    assert rows[A.value, "preflop.fold_to_three_bet"].value == 1
    assert rows[A.value, "preflop.four_bet"].value == 0


def test_squeeze_after_call_and_eligible_population():
    rows = rows_for(
        [
            ev(1, K.SMALL_BLIND, B, ".25"),
            ev(2, K.BIG_BLIND, C, ".50"),
            ev(3, K.RAISE, A, "1.50", street_total=True),
            ev(4, K.CALL, B, "1.50", street_total=True),
            ev(5, K.RAISE, C, "6", street_total=True),
            ev(6, K.FOLD, A),
            ev(7, K.FOLD, B),
            ev(8, K.RETURN, C, "4.50"),
            ev(9, K.AWARD, C, "4.50"),
        ],
        ("50", "50", "50"),
    )
    assert rows[C.value, "preflop.squeeze"].value == 1
    assert rows[B.value, "preflop.squeeze"].value is None
    assert rows[B.value, "preflop.call_open"].value == 1


def test_wilson_and_registry_definitions():
    assert wilson(0, 0) is None
    lower, upper = wilson(5, 10)
    assert lower == pytest.approx(0.236593, abs=1e-6)
    assert upper == pytest.approx(0.763407, abs=1e-6)
    for identifier, definition in REGISTRY.items():
        assert identifier == definition.id
        assert definition.formula and definition.numerator and definition.denominator
        assert definition.required_data and definition.assumptions


def test_all_street_action_families_and_showdown_have_independent_counts():
    from app.domain.hands import Card, Street

    events = [
        ev(1, K.SMALL_BLIND, A, ".25"),
        ev(2, K.BIG_BLIND, B, ".50"),
        ev(3, K.CALL, A, ".50", street_total=True),
        ev(4, K.CHECK, B),
        flop(),
        ev(6, K.BET, B, "1"),
        ev(7, K.CALL, A, "1", street_total=True),
        ev(
            8,
            K.BOARD,
            cards=tuple(Card(c) for c in ("As", "Kd", "2c", "3h")),
            street=Street.TURN,
            run=1,
        ),
        ev(9, K.CHECK, B),
        ev(10, K.BET, A, "2"),
        ev(11, K.CALL, B, "2", street_total=True),
        ev(
            12,
            K.BOARD,
            cards=tuple(Card(c) for c in ("As", "Kd", "2c", "3h", "4s")),
            street=Street.RIVER,
            run=1,
        ),
        ev(13, K.CHECK, B),
        ev(14, K.BET, A, "3"),
        ev(15, K.CALL, B, "3", street_total=True),
        ev(16, K.AWARD, A, "13"),
    ]
    rows = rows_for(events)
    for street in ("turn", "river"):
        assert rows[B.value, street + ".check"].value == D(".5")
        assert rows[B.value, street + ".call"].value == D(".5")
        assert rows[B.value, street + ".afq"].value == 0
        assert rows[B.value, street + ".af"].value == 0
        assert rows[B.value, street + ".check_call"].value == 1
        assert rows[B.value, street + ".check_fold"].value == 0
        assert rows[B.value, street + ".check_raise"].value == 0
        assert rows[A.value, street + ".bet"].value == 1
    assert rows[A.value, "flop.call"].value == 1
    assert rows[A.value, "showdown.wtsd"].value == 1
    assert rows[B.value, "showdown.wsd"].value == 0
    assert rows[A.value, "showdown.wsd"].value == 1
    assert rows[A.value, "results.net_chips"].value == D("6.5")


def test_double_and_triple_barrel_responses():
    from app.domain.hands import Card, Street

    events = raised_prefix() + [
        flop(),
        ev(6, K.CHECK, B),
        ev(7, K.BET, A, "1"),
        ev(8, K.CALL, B, "1", street_total=True),
        ev(
            9,
            K.BOARD,
            cards=tuple(Card(c) for c in ("As", "Kd", "2c", "3h")),
            street=Street.TURN,
            run=1,
        ),
        ev(10, K.CHECK, B),
        ev(11, K.BET, A, "2"),
        ev(12, K.CALL, B, "2", street_total=True),
        ev(
            13,
            K.BOARD,
            cards=tuple(Card(c) for c in ("As", "Kd", "2c", "3h", "4s")),
            street=Street.RIVER,
            run=1,
        ),
        ev(14, K.CHECK, B),
        ev(15, K.BET, A, "3"),
        ev(16, K.FOLD, B),
        ev(17, K.RETURN, A, "3"),
        ev(18, K.AWARD, A, "9"),
    ]
    rows = rows_for(events)
    for street in ("flop", "turn", "river"):
        assert rows[A.value, street + ".cbet"].value == 1
    assert rows[B.value, "flop.call_to_cbet"].value == 1
    assert rows[B.value, "turn.call_to_cbet"].value == 1
    assert rows[B.value, "river.fold_to_cbet"].value == 1


def test_raise_sizes_success_blind_defense_and_four_bet_responses():
    rows = rows_for(
        [
            ev(1, K.SMALL_BLIND, A, ".25"),
            ev(2, K.BIG_BLIND, B, ".50"),
            ev(3, K.RAISE, A, "1.50", street_total=True),
            ev(4, K.RAISE, B, "4.50", street_total=True),
            ev(5, K.RAISE, A, "12", street_total=True),
            ev(6, K.FOLD, B),
            ev(7, K.RETURN, A, "7.50"),
            ev(8, K.AWARD, A, "9"),
        ]
    )
    assert rows[A.value, "preflop.open_size_bb"].value == 3
    assert rows[B.value, "preflop.three_bet_size_bb"].value == 9
    assert rows[A.value, "preflop.four_bet_size_bb"].value == 24
    assert rows[A.value, "preflop.four_bet_success"].value == 1
    assert rows[A.value, "preflop.open_success"].value == 0
    assert rows[B.value, "preflop.fold_to_four_bet"].value == 1
    assert rows[B.value, "preflop.call_four_bet"].value == 0
    assert rows[B.value, "preflop.bb_defend"].value == 1
    assert rows[B.value, "preflop.bb_three_bet_open"].value == 1
    assert rows[B.value, "preflop.bb_fold_steal"].value == 0


def test_isolation_and_limp_response_opportunities():
    rows = rows_for(
        [
            ev(1, K.SMALL_BLIND, B, ".25"),
            ev(2, K.BIG_BLIND, C, ".50"),
            ev(3, K.CALL, A, ".50", street_total=True),
            ev(4, K.FOLD, B),
            ev(5, K.RAISE, C, "2", street_total=True),
            ev(6, K.FOLD, A),
            ev(7, K.RETURN, C, "1.50"),
            ev(8, K.AWARD, C, "1.25"),
        ],
        ("50", "50", "50"),
    )
    assert rows[C.value, "preflop.isolation"].value == 1
    assert rows[A.value, "preflop.limp_fold"].value == 1
    assert rows[A.value, "preflop.open_limp"].value == 1
    assert rows[A.value, "preflop.vpip_minus_pfr"].value == 1
    assert rows[C.value, "preflop.steal"].value is None


def test_bet_sizing_and_aggregate_aggression():
    rows = rows_for(
        raised_prefix()
        + [
            flop(),
            ev(6, K.CHECK, B),
            ev(7, K.BET, A, "1"),
            ev(8, K.FOLD, B),
            ev(9, K.RETURN, A, "1"),
            ev(10, K.AWARD, A, "3"),
        ]
    )
    assert rows[A.value, "flop.bet_size_pot"].value == D(1) / 3
    assert rows[A.value, "flop.overbet"].value == 0
    assert rows[A.value, "postflop.afq"].value == 1
    assert rows[B.value, "preflop.bb_call_open"].value == 1
    assert rows[A.value, "preflop.vpip_minus_pfr"].value == 0


def test_blind_metrics_use_posts_even_when_button_role_is_unknown():
    from dataclasses import replace

    from test_reconstruction import hu_prefix

    hand = replace(
        history(
            hu_prefix()
            + [
                flop(),
                ev(6, K.CHECK, B),
                ev(7, K.BET, A, "1"),
                ev(8, K.FOLD, B),
                ev(9, K.RETURN, A, "1"),
                ev(10, K.AWARD, A, "1"),
            ]
        ),
        button=None,
    )
    rows = {
        (r.player_id, r.metric_id): r for r in compute_statistics((reconstruct(hand),))
    }
    assert rows[A.value, "preflop.sb_complete"].value == 1
    assert rows[A.value, "preflop.steal"].excluded_hands == 1
