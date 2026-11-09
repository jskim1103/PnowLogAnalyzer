import pytest
from app.database.store import Store
from app.ingestion.importer import ImportConflictError
from test_importer import END, STACKS, START, export


def test_persistent_overlap_import_restart_and_incremental_completion(tmp_path):
    db = tmp_path / "test.duckdb"
    partial = export(tmp_path, [(1, START), (2, STACKS)])
    first = Store(db).import_paths([partial], session_id="s")
    assert first.new_records == 2 and first.hands == 1
    full = export(tmp_path, [(1, START), (2, STACKS), (3, END)], "complete.csv")
    second = Store(db).import_paths([full], session_id="s")
    assert second.new_records == 1 and second.hands == 1
    repeated = Store(db).import_paths([full], session_id="s")
    assert repeated.new_records == 0 and repeated.new_sources == 0
    assert Store(db).hands()[0].history.boundaries_valid
    assert len(Store(db).reports()[0].records) == 3


def test_conflict_rolls_back_without_overwriting_original(tmp_path):
    db = tmp_path / "test.duckdb"
    source = export(tmp_path, [(1, START), (2, STACKS), (3, END)])
    store = Store(db)
    store.import_paths([source], session_id="s")
    conflicting = export(tmp_path, [(1, "changed entry")], "conflict.csv")
    with pytest.raises(ImportConflictError):
        store.import_paths([conflicting], session_id="s")
    assert len(store.hands()) == 1
    assert store.reports()[0].records[0].entry == START
    assert store.sessions()[0]["sources"] == 1


def test_same_hand_id_can_exist_in_distinct_sessions_and_owner_is_explicit(tmp_path):
    path = export(tmp_path, [(1, START), (2, STACKS), (3, END)])
    other = export(tmp_path, [(4, START), (5, STACKS), (6, END)], "other.csv")
    store = Store(tmp_path / "test.duckdb")
    store.import_paths([path], session_id="s", owner="synthetic_a")
    store.import_paths([other], session_id="other")
    assert len(store.hands()) == 2 and len(store.hands(session_id="s")) == 1
    with pytest.raises(ValueError, match="owner"):
        store.import_paths([path], session_id="s", owner="synthetic_b")


def test_cached_hands_can_be_rebuilt_without_changing_results(tmp_path):
    path = export(tmp_path, [(1, START), (2, STACKS), (3, END)])
    store = Store(tmp_path / "test.duckdb")
    store.import_paths([path], session_id="s")
    before = store.hands()
    store.rebuild("s")
    assert store.hands() == before


def test_reconstruction_version_change_rebuilds_only_stale_cache(tmp_path, monkeypatch):
    import duckdb
    from app.database.store import RECONSTRUCTION_VERSION

    path = export(tmp_path, [(1, START), (2, STACKS), (3, END)])
    db = tmp_path / "test.duckdb"
    Store(db).import_paths([path], session_id="s")
    with duckdb.connect(str(db)) as connection:
        connection.execute("UPDATE sessions SET reconstruction_version='obsolete'")
    assert Store(db).sessions()[0]["reconstruction_version"] == RECONSTRUCTION_VERSION

    def unexpected_parse(*args, **kwargs):
        raise AssertionError("Unchanged startup must use cached reconstructions")

    monkeypatch.setattr("app.database.store.import_session", unexpected_parse)
    assert len(Store(db).hands()) == 1
