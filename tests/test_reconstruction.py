from dataclasses import replace
from datetime import UTC, datetime
from decimal import Decimal as D

import pytest
from app.domain.hands import Card, HandEvent, HandHistory, HandPlayer, Street
from app.domain.hands import EventKind as K
from app.domain.players import PlayerId
from app.domain.preflop import GameVariant
from app.reconstruction.engine import reconstruct

A, B, C = (PlayerId(x) for x in ("a", "b", "c"))


def ev(order, kind, player=None, amount=None, **kwargs):
    return HandEvent(
        order, kind, player, D(str(amount)) if amount is not None else None, **kwargs
    )


def history(events, stacks=("50", "50"), variant=GameVariant.NLHE):
    ids = (A, B, C)
    return HandHistory(
        "s",
        "h",
        1,
        variant,
        datetime(2026, 1, 1, tzinfo=UTC),
        A,
        tuple(
            HandPlayer(ids[i], f"Player {i}", i + 1, D(stack))
            for i, stack in enumerate(stacks)
        ),
        tuple(events),
        True,
    )


def hu_prefix():
    return [
        ev(1, K.SMALL_BLIND, A, ".25"),
        ev(2, K.BIG_BLIND, B, ".50"),
        ev(3, K.CALL, A, ".50", street_total=True),
        ev(4, K.CHECK, B),
    ]


def flop(order=5, cards=("As", "Kd", "2c"), run=1):
    return ev(
        order, K.BOARD, cards=tuple(Card(c) for c in cards), street=Street.FLOP, run=run
    )


def test_exact_ledger_return_and_decision_context():
    h = reconstruct(
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
        )
    )
    assert h.accounting_reconciled and h.action_consistent
    a, b = h.results
    assert (a.net, b.net, a.ending_stack, b.ending_stack) == (
        D(".50"),
        D("-.50"),
        D("50.50"),
        D("49.50"),
    )
    assert a.returned == 1 and a.contributed == D("1.50")
    assert sum(p.amount for p in h.pots) == 1
    assert h.decisions[3].street == Street.FLOP  # Forced posts aren't decisions.
    fold = h.decisions[-1]
    assert (fold.pot_before, fold.facing, fold.to_call) == (2, 1, 1)
    assert fold.previous_aggressor == A
    assert h.results[0].position == "BTN/SB"
    assert h.results[1].position == "BB"


def test_three_way_side_pots_short_all_in_and_split_awards():
    events = [
        ev(1, K.SMALL_BLIND, B, ".25"),
        ev(2, K.BIG_BLIND, C, ".50"),
        ev(3, K.RAISE, A, "10", street_total=True, all_in=True),
        ev(4, K.RAISE, B, "20", street_total=True, all_in=True),
        ev(5, K.CALL, C, "20", street_total=True),
        flop(6),
        ev(
            7,
            K.BOARD,
            cards=tuple(Card(c) for c in ("As", "Kd", "2c", "3h")),
            street=Street.TURN,
            run=1,
        ),
        ev(
            8,
            K.BOARD,
            cards=tuple(Card(c) for c in ("As", "Kd", "2c", "3h", "4s")),
            street=Street.RIVER,
            run=1,
        ),
        ev(9, K.AWARD, A, "30"),
        ev(10, K.AWARD, B, "20"),
    ]
    h = reconstruct(history(events, ("10", "20", "30")))
    assert h.accounting_reconciled and h.action_consistent
    assert [(p.amount, p.eligible) for p in h.pots] == [
        (D("30"), (A, B, C)),
        (D("20"), (B, C)),
    ]
    assert [p.net for p in h.results] == [D("20"), D("0"), D("-20")]


def test_ineligible_side_pot_winner_is_not_reconciled():
    events = [
        ev(1, K.SMALL_BLIND, B, ".25"),
        ev(2, K.BIG_BLIND, C, ".50"),
        ev(3, K.RAISE, A, "10", street_total=True, all_in=True),
        ev(4, K.RAISE, B, "20", street_total=True, all_in=True),
        ev(5, K.CALL, C, "20", street_total=True),
        ev(6, K.AWARD, A, "50"),
    ]
    h = reconstruct(history(events, ("10", "20", "30")))
    assert not h.accounting_reconciled
    assert "ineligible_awards" in {d.code for d in h.diagnostics}


def test_split_pot_and_unobserved_cards_stay_unknown():
    h = reconstruct(
        history(
            hu_prefix()
            + [
                flop(),
                ev(6, K.CHECK, B),
                ev(7, K.CHECK, A),
                ev(
                    8,
                    K.BOARD,
                    cards=tuple(Card(c) for c in ("As", "Kd", "2c", "3h")),
                    street=Street.TURN,
                    run=1,
                ),
                ev(9, K.CHECK, B),
                ev(10, K.CHECK, A),
                ev(
                    11,
                    K.BOARD,
                    cards=tuple(Card(c) for c in ("As", "Kd", "2c", "3h", "4s")),
                    street=Street.RIVER,
                    run=1,
                ),
                ev(12, K.CHECK, B),
                ev(13, K.CHECK, A),
                ev(14, K.AWARD, A, ".50"),
                ev(15, K.AWARD, B, ".50"),
            ]
        )
    )
    assert h.accounting_reconciled
    assert all(p.net == 0 and p.observed_cards == () for p in h.results)


def test_run_twice_preserves_common_prefix_without_betting_again():
    events = hu_prefix() + [
        flop(),
        ev(6, K.BET, B, "49.50", all_in=True),
        ev(7, K.CALL, A, "49.50", street_total=True, all_in=True),
        ev(
            8,
            K.BOARD,
            cards=tuple(Card(c) for c in ("As", "Kd", "2c", "3h")),
            street=Street.TURN,
            run=1,
        ),
        ev(
            9,
            K.BOARD,
            cards=tuple(Card(c) for c in ("As", "Kd", "2c", "3h", "4s")),
            street=Street.RIVER,
            run=1,
        ),
        ev(
            10,
            K.BOARD,
            cards=tuple(Card(c) for c in ("As", "Kd", "2c", "5h")),
            street=Street.TURN,
            run=2,
        ),
        ev(
            11,
            K.BOARD,
            cards=tuple(Card(c) for c in ("As", "Kd", "2c", "5h", "6s")),
            street=Street.RIVER,
            run=2,
        ),
        ev(12, K.AWARD, A, "50", run=1),
        ev(13, K.AWARD, B, "50", run=2),
    ]
    h = reconstruct(history(events))
    assert h.accounting_reconciled and len(h.boards) == 2
    assert h.boards[0].cards[:3] == h.boards[1].cards[:3]


@pytest.mark.parametrize(
    "events,code",
    [
        (hu_prefix() + [flop(), ev(6, K.CHECK, A)], "out_of_turn"),
        (hu_prefix() + [flop(), ev(6, K.BET, B, "100")], "stack_exceeded"),
        (
            hu_prefix() + [flop(), ev(6, K.BET, B, "1"), ev(7, K.CHECK, A)],
            "check_facing_bet",
        ),
        (
            [
                ev(1, K.SMALL_BLIND, A, ".25"),
                ev(2, K.BIG_BLIND, B, ".50"),
                ev(3, K.FOLD, A),
                ev(4, K.CALL, A, ".50", street_total=True),
            ],
            "action_after_fold",
        ),
        (hu_prefix() + [flop(), ev(6, K.UNKNOWN)], "unknown_event"),
        (hu_prefix() + [flop(), ev(6, K.RETURN, A, "5")], "invalid_return"),
    ],
)
def test_invalid_sequences_preserve_diagnostics(events, code):
    h = reconstruct(history(events))
    assert code in {d.code for d in h.diagnostics}
    assert not h.action_consistent


def test_missing_settlement_and_incomplete_boundaries_do_not_create_results():
    h = reconstruct(replace(history(hu_prefix()), boundaries_valid=False))
    assert not h.accounting_reconciled
    assert all(p.net is None and p.ending_stack is None for p in h.results)


def test_omaha_pot_limit_and_short_raise_reopening():
    h = reconstruct(
        history(
            [
                ev(1, K.SMALL_BLIND, A, ".25"),
                ev(2, K.BIG_BLIND, B, ".50"),
                ev(3, K.RAISE, A, "10", street_total=True),
            ],
            variant=GameVariant.PLO5,
        )
    )
    assert "pot_limit_exceeded" in {d.code for d in h.diagnostics}
    # B's short all-in raises from 4 to 5: A cannot reraise after its full raise.
    h = reconstruct(
        history(
            [
                ev(1, K.SMALL_BLIND, A, ".25"),
                ev(2, K.BIG_BLIND, B, ".50"),
                ev(3, K.RAISE, A, "4", street_total=True),
                ev(4, K.RAISE, B, "5", street_total=True, all_in=True),
                ev(5, K.RAISE, A, "8", street_total=True),
            ],
            ("20", "5"),
        )
    )
    assert not h.decisions[-1].can_raise
    assert "raise_not_reopened" in {d.code for d in h.diagnostics}


def test_dead_button_uses_blinds_for_turn_order_without_guessing_named_position():
    original = history(
        hu_prefix()
        + [
            flop(),
            ev(6, K.CHECK, B),
            ev(7, K.BET, A, "1"),
            ev(8, K.FOLD, B),
            ev(9, K.RETURN, A, "1"),
            ev(10, K.AWARD, A, "1"),
        ]
    )
    h = reconstruct(replace(original, button=None))
    assert h.action_consistent and h.accounting_reconciled
    assert all(result.position is None for result in h.results)
    assert any(d.code == "unknown_button" for d in h.diagnostics)


def test_shared_card_after_runout_divergence_and_multiple_owners_are_invalid():
    events = hu_prefix() + [
        flop(),
        ev(6, K.SHOW, A, cards=(Card("As"),)),
        ev(7, K.SHOW, B, cards=(Card("As"),)),
    ]
    h = reconstruct(history(events))
    assert "duplicate_card" in {d.code for d in h.diagnostics}


def test_partial_reveal_does_not_become_complete_hole_cards():
    h = reconstruct(
        history(
            hu_prefix()
            + [
                flop(),
                ev(6, K.CHECK, B),
                ev(7, K.BET, A, "1"),
                ev(8, K.FOLD, B),
                ev(9, K.RETURN, A, "1"),
                ev(10, K.AWARD, A, "1"),
                ev(11, K.SHOW, B, cards=(Card("Qc"),)),
            ]
        )
    )
    assert h.results[1].observed_cards == (Card("Qc"),)
    assert not h.results[1].complete_hole_cards


def test_missing_uncalled_return_cannot_pass_ledger_validation():
    h = reconstruct(
        history(
            hu_prefix()
            + [
                flop(),
                ev(6, K.CHECK, B),
                ev(7, K.BET, A, "1"),
                ev(8, K.FOLD, B),
                ev(9, K.AWARD, A, "2"),
            ]
        )
    )
    assert not h.accounting_reconciled
    assert "missing_uncalled_return" in {d.code for d in h.diagnostics}


def test_short_opening_all_in_can_be_called_below_minimum_bet():
    h = reconstruct(
        history(
            hu_prefix()
            + [
                flop(),
                ev(6, K.BET, B, ".20", all_in=True),
                ev(7, K.CALL, A, ".20", street_total=True),
                ev(
                    8,
                    K.BOARD,
                    cards=tuple(Card(c) for c in ("As", "Kd", "2c", "3h")),
                    street=Street.TURN,
                    run=1,
                ),
                ev(
                    9,
                    K.BOARD,
                    cards=tuple(Card(c) for c in ("As", "Kd", "2c", "3h", "4s")),
                    street=Street.RIVER,
                    run=1,
                ),
                ev(10, K.AWARD, A, "1.40"),
            ],
            ("50", ".70"),
        )
    )
    assert h.action_consistent


def test_dead_small_blind_does_not_shift_actual_big_blind_position():
    h = history(
        [
            ev(1, K.BIG_BLIND, B, ".50"),
            ev(2, K.FOLD, C),
            ev(3, K.RAISE, A, "1.50", street_total=True),
            ev(4, K.CALL, B, "1.50", street_total=True),
            flop(5),
            ev(6, K.CHECK, B),
            ev(7, K.BET, A, "1"),
            ev(8, K.FOLD, B),
            ev(9, K.RETURN, A, "1"),
            ev(10, K.AWARD, A, "3"),
        ],
        ("50", "50", "50"),
    )
    result = reconstruct(replace(h, dead_small_blind=True))
    assert result.action_consistent
    assert {r.player_id: r.position for r in result.results} == {
        A: "BTN",
        B: "BB",
        C: None,
    }


def test_balanced_awards_do_not_hide_missing_showdown_runouts():
    events = hu_prefix() + [
        flop(),
        ev(6, K.BET, B, "49.50", all_in=True),
        ev(7, K.CALL, A, "49.50", street_total=True, all_in=True),
        ev(8, K.AWARD, A, "100"),
    ]
    h = reconstruct(history(events))
    assert not h.action_consistent
    assert "incomplete_showdown_board" in {d.code for d in h.diagnostics}
    assert h.status == "partial"


def test_run_twice_announcement_requires_a_second_complete_board():
    events = hu_prefix() + [
        flop(),
        ev(6, K.BET, B, "49.50", all_in=True),
        ev(7, K.CALL, A, "49.50", street_total=True, all_in=True),
        ev(8, K.RUN_TWICE),
        ev(
            9,
            K.BOARD,
            cards=tuple(Card(c) for c in ("As", "Kd", "2c", "3h")),
            street=Street.TURN,
            run=1,
        ),
        ev(
            10,
            K.BOARD,
            cards=tuple(Card(c) for c in ("As", "Kd", "2c", "3h", "4s")),
            street=Street.RIVER,
            run=1,
        ),
        ev(11, K.AWARD, A, "100"),
    ]
    h = reconstruct(history(events))
    assert "incomplete_showdown_board" in {d.code for d in h.diagnostics}
    assert h.status == "partial"
