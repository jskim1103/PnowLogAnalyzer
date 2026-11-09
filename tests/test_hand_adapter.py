from dataclasses import replace

from app.domain.hands import Card, EventKind
from app.domain.players import PlayerId
from app.ingestion.hands import normalize_session
from app.ingestion.importer import import_session
from app.reconstruction.engine import reconstruct
from test_importer import END, STACKS, START, export


def test_normalized_history_preserves_every_record_and_provenance(tmp_path):
    entries = [
        START,
        STACKS,
        "Your hand is A♣, K♣, Q♣, J♣, 10♣",
        '"Alpha 🐣 @ synthetic_a" posts a small blind of 0.25',
        '"Beta @ synthetic_b" posts a big blind of 0.50',
        '"Alpha 🐣 @ synthetic_a" calls 0.50',
        '"Beta @ synthetic_b" checks',
        "Flop:  [2♣, 3♦, 4♥]",
        '"Beta @ synthetic_b" checks',
        '"Alpha 🐣 @ synthetic_a" bets 1.00',
        '"Beta @ synthetic_b" folds',
        'Uncalled bet of 1.00 returned to "Alpha 🐣 @ synthetic_a"',
        '"Alpha 🐣 @ synthetic_a" collected 1.00 from pot',
        END,
    ]
    path = export(tmp_path, list(enumerate(entries, 1)))
    imported = import_session([path], session_id="s")
    h = normalize_session(imported)[0]
    assert len(h.events) == len(entries)
    assert h.events[0].sources[0].record_number == 1
    assert h.events[2].player_id is None
    assert h.events[2].cards[0] == Card("Ac")
    assert reconstruct(h).accounting_reconciled
    owned = normalize_session(imported, owner=PlayerId("synthetic_a"))[0]
    assert owned.events[2].player_id == PlayerId("synthetic_a")
    assert reconstruct(owned).results[0].complete_hole_cards
    assert owned.events[-2].kind == EventKind.AWARD
    assert owned.events[-2].run is None  # Unlabelled awards aren't assigned a run.


def test_bad_timestamp_and_unknown_record_remain_diagnostics(tmp_path):
    path = export(tmp_path, [(1, START), (2, STACKS), (3, "unknown format"), (4, END)])
    imported = import_session([path], session_id="s")
    envelope = imported.hands[0]
    envelope = replace(
        envelope,
        records=(replace(envelope.records[0], at="not-a-time"),) + envelope.records[1:],
    )
    h = normalize_session(replace(imported, hands=(envelope,)))[0]
    assert "invalid_timestamp" in {d.code for d in h.diagnostics}
    assert h.events[2].kind == EventKind.UNKNOWN
    assert h.events[2].raw == "unknown format"
