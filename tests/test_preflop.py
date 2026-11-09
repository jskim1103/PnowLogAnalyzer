from app.ingestion.importer import import_session
from app.ingestion.preflop import extract_preflop_hands
from app.stats.vpip import calculate_vpip
from test_importer import END, STACKS, START, export


def report_for(tmp_path, entries):
    return import_session(
        [export(tmp_path, list(enumerate(entries, 1)))], session_id="s"
    )


def basic_hand():
    return [
        START,
        STACKS,
        '"Alpha 🐣 @ synthetic_a" posts a small blind of 0.25',
        '"Beta @ synthetic_b" posts a big blind of 0.50',
        '"Alpha 🐣 @ synthetic_a" calls 0.50',
        '"Beta @ synthetic_b" checks',
    ]


def test_csv_to_vpip_keeps_ids_roster_and_call_totals(tmp_path):
    entries = basic_hand() + [
        "Flop:  [A♣, K♣, Q♣]",
        '"Beta @ synthetic_b" bets 1.00',
        '"Alpha 🐣 @ synthetic_a" folds',
        END,
    ]
    report = report_for(tmp_path, entries)
    normalized = extract_preflop_hands(report)
    assert len(normalized[0].actions) == 4
    assert normalized[0].actions[2].amount == normalized[0].actions[1].amount
    stats = calculate_vpip(normalized)
    assert not stats.excluded_hands
    assert [(r.player_id.value, r.numerator, r.denominator) for r in stats.results] == [
        ("synthetic_a", 1, 1),
        ("synthetic_b", 0, 1),
    ]


def test_session_joins_and_unattributed_cards_do_not_add_dealt_players(tmp_path):
    entries = basic_hand()
    entries.insert(
        2, 'The player "Observer @ synthetic_c" joined the game with a stack of 50.00.'
    )
    entries.insert(3, "Your hand is A♣, K♣, Q♣, J♣, 10♣")
    report = report_for(tmp_path, entries + [END])
    assert len(report.players) == 3
    stats = calculate_vpip(extract_preflop_hands(report))
    assert len(stats.results) == 2
    assert not stats.excluded_hands


def test_unknown_preflop_excludes_but_unknown_postflop_does_not(tmp_path):
    preflop = report_for(tmp_path, basic_hand() + ["mystery action", END])
    assert calculate_vpip(extract_preflop_hands(preflop)).excluded_hands[0].reasons == (
        "unknown_preflop_record",
    )
    postflop = report_for(
        tmp_path, basic_hand() + ["Flop:  [A♣, K♣, Q♣]", "mystery action", END]
    )
    assert not calculate_vpip(extract_preflop_hands(postflop)).excluded_hands


def test_truncated_hand_has_no_eligible_denominator(tmp_path):
    report = report_for(tmp_path, basic_hand())
    stats = calculate_vpip(extract_preflop_hands(report))
    assert "invalid_hand_boundaries" in stats.excluded_hands[0].reasons
    assert all(r.percentage is None for r in stats.results)


def test_overlapping_exports_do_not_double_count_vpip(tmp_path):
    path = export(tmp_path, list(enumerate(basic_hand() + [END], 1)))
    imported = import_session([path, path], session_id="s")
    assert all(
        r.denominator == 1
        for r in calculate_vpip(extract_preflop_hands(imported)).results
    )


def test_malformed_snapshot_does_not_invent_denominators(tmp_path):
    report = report_for(tmp_path, [START, "Player stacks: malformed", END])
    stats = calculate_vpip(extract_preflop_hands(report))
    assert not stats.results
    assert "missing_or_multiple_rosters" in stats.excluded_hands[0].reasons
