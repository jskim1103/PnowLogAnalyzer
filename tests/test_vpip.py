from dataclasses import replace
from decimal import Decimal

import pytest
from app.domain.players import PlayerId
from app.domain.preflop import (
    GameVariant,
    PreflopAction,
    PreflopHand,
    StartingPlayer,
)
from app.domain.preflop import (
    PreflopActionKind as Kind,
)
from app.stats.vpip import calculate_vpip

A, B, C = PlayerId("a"), PlayerId("b"), PlayerId("c")
NLHE = GameVariant.NLHE
PLO5 = GameVariant.PLO5


def action(player, kind, order, amount=None, all_in=False):
    return PreflopAction(
        player,
        kind,
        order,
        Decimal(str(amount)) if amount is not None else None,
        all_in,
    )


def hand(*decisions, variant=NLHE, hand_id="h"):
    return PreflopHand(
        "s",
        hand_id,
        variant,
        (StartingPlayer(A, 1, Decimal("10")), StartingPlayer(B, 2, Decimal("10"))),
        (action(A, Kind.SMALL_BLIND, 1, ".25"), action(B, Kind.BIG_BLIND, 2, ".50"))
        + decisions,
    )


def by_id(report):
    return {row.player_id: row for row in report.results}


def test_blinds_and_checks_do_not_count_but_small_blind_completion_does():
    report = calculate_vpip(
        (hand(action(A, Kind.CALL, 3, ".50"), action(B, Kind.CHECK, 4)),)
    )
    rows = by_id(report)
    assert (rows[A].numerator, rows[A].denominator, rows[A].percentage) == (1, 1, 100)
    assert (rows[B].numerator, rows[B].denominator, rows[B].percentage) == (0, 1, 0)
    assert rows[A].sample_size == 1
    assert not report.excluded_hands


def test_folded_blind_and_big_blind_walk_are_both_zero():
    rows = by_id(calculate_vpip((hand(action(A, Kind.FOLD, 3)),)))
    assert all(row.numerator == 0 and row.denominator == 1 for row in rows.values())


def test_multiple_raises_count_one_hand_and_fold_after_call_still_counts():
    h = hand(
        action(A, Kind.CALL, 3, ".50"),
        action(B, Kind.RAISE, 4, "2"),
        action(A, Kind.RAISE, 5, "4"),
        action(B, Kind.RAISE, 6, "8"),
        action(A, Kind.FOLD, 7),
    )
    assert all(row.numerator == 1 for row in calculate_vpip((h,)).results)


def test_game_variants_are_never_combined():
    report = calculate_vpip(
        (
            hand(action(A, Kind.FOLD, 3)),
            hand(
                action(A, Kind.CALL, 3, ".50"),
                action(B, Kind.CHECK, 4),
                variant=PLO5,
                hand_id="other",
            ),
        )
    )
    assert len(report.results) == 4
    assert {(r.variant, r.numerator) for r in report.results if r.player_id == A} == {
        (NLHE, 0),
        (PLO5, 1),
    }


def test_zero_eligible_denominator_returns_none_and_exclusions():
    report = calculate_vpip((hand(),))
    assert all(
        r.denominator == 0 and r.percentage is None and r.excluded == 1
        for r in report.results
    )
    assert "incomplete_preflop" in report.excluded_hands[0].reasons


def test_short_all_in_call_counts_voluntary_investment():
    h = hand(action(A, Kind.CALL, 3, ".40", True), action(B, Kind.CHECK, 4))
    h = replace(
        h,
        players=(replace(h.players[0], stack=Decimal(".40")), h.players[1]),
        actions=h.actions[:-1],
    )  # BB has no decision versus an all-in caller.
    report = calculate_vpip((h,))
    assert not report.excluded_hands
    assert by_id(report)[A].numerator == 1


def test_forced_blind_all_in_without_decision_does_not_count():
    h = hand(action(A, Kind.CALL, 3, ".50"))
    h = replace(h, players=(h.players[0], replace(h.players[1], stack=Decimal(".50"))))
    report = calculate_vpip((h,))
    assert not report.excluded_hands
    assert by_id(report)[B].numerator == 0


@pytest.mark.parametrize(
    "decisions,reason",
    [
        ((action(A, Kind.CHECK, 3), action(B, Kind.CHECK, 4)), "check_facing_bet"),
        ((action(C, Kind.CALL, 3, ".50"),), "unknown_actor"),
        (
            (action(A, Kind.CALL, 3, ".25"), action(B, Kind.CHECK, 4)),
            "nonpositive_investment",
        ),
        ((action(A, Kind.RAISE, 3, "20"),), "stack_exceeded"),
        (
            (action(A, Kind.FOLD, 3), action(A, Kind.CALL, 4, ".50")),
            "action_after_fold",
        ),
    ],
)
def test_ineligible_hands_are_excluded_instead_of_counted_as_zero(decisions, reason):
    report = calculate_vpip((hand(*decisions),))
    assert reason in report.excluded_hands[0].reasons
    assert all(row.denominator == 0 for row in report.results)


def test_input_issues_missing_blinds_and_duplicate_hands_are_excluded():
    h = hand(action(A, Kind.FOLD, 3))
    report = calculate_vpip((replace(h, input_issues=("unknown_preflop_record",)),))
    assert report.excluded_hands[0].reasons == ("unknown_preflop_record",)
    assert (
        "missing_blinds"
        in calculate_vpip((replace(h, actions=h.actions[2:]),))
        .excluded_hands[0]
        .reasons
    )
    with pytest.raises(ValueError, match="Duplicate hand"):
        calculate_vpip((h, h))


def test_dead_small_blind_and_unknown_variants():
    h = hand(action(A, Kind.FOLD, 3))
    h = replace(h, dead_small_blind=True, actions=h.actions[1:])
    assert not calculate_vpip((h,)).excluded_hands
    unknown = replace(h, variant=GameVariant.UNKNOWN)
    assert calculate_vpip((unknown,)).excluded_hands[0].reasons == (
        "unsupported_variant",
    )


def test_excluded_hand_does_not_dilute_eligible_rate():
    good = hand(action(A, Kind.CALL, 3, ".50"), action(B, Kind.CHECK, 4))
    bad = replace(hand(), hand_id="incomplete")
    row = by_id(calculate_vpip((good, bad)))[A]
    assert (row.numerator, row.denominator, row.excluded, row.percentage) == (
        1,
        1,
        1,
        100,
    )


def test_same_player_with_different_ids_is_not_merged_and_sessions_are_distinct():
    first = hand(action(A, Kind.FOLD, 3))
    second = replace(
        hand(action(A, Kind.CALL, 3, ".50"), action(B, Kind.CHECK, 4)),
        session_id="other-session",
    )
    row = by_id(calculate_vpip((first, second)))[A]
    assert (row.numerator, row.denominator, row.percentage) == (1, 2, 50)


def test_empty_input_has_no_fabricated_players():
    report = calculate_vpip(())
    assert not report.results and not report.excluded_hands
