import pytest
from app.domain.players import PlayerId
from app.ingestion.players import PlayerReferenceError, parse_player_reference


@pytest.mark.parametrize(
    "name",
    [
        "Chick 🐣",
        "Last, First",
        'A "quoted" name',
        "a (b) [c]",
        "a @ b",
        "  name  ",
        "",
    ],
)
def test_names_are_preserved(name: str) -> None:
    reference = parse_player_reference(f'"{name} @ synthetic_1"')
    assert reference.player_id == PlayerId("synthetic_1")
    assert reference.display_name == name


def test_renames_keep_identity_and_duplicate_names_do_not_merge() -> None:
    original = parse_player_reference('"Alpha @ synthetic_1"')
    renamed = parse_player_reference('"Beta 🐣 @ synthetic_1"')
    unrelated = parse_player_reference('"Alpha @ synthetic_2"')
    assert original.player_id == renamed.player_id
    assert original.display_name != renamed.display_name
    assert original.player_id != unrelated.player_id
    assert len({original.player_id, renamed.player_id, unrelated.player_id}) == 2
    assert PlayerId("ABC") != PlayerId("abc")


@pytest.mark.parametrize(
    "text",
    [
        "Alpha @ id",
        '"Alpha"',
        '"Alpha @ "',
        '"Alpha @ a b"',
        '"Alpha @ a\\nb"'.replace("\\n", "\n"),
        '"Alpha @ a"b"',
        '"Alpha\nBeta @ id"',
        '"Alpha @ id" folds',
    ],
)
def test_malformed_reference_is_rejected(text: str) -> None:
    with pytest.raises(PlayerReferenceError):
        parse_player_reference(text)


@pytest.mark.parametrize("value", ["", " ", "\t"])
def test_identity_cannot_be_empty(value: str) -> None:
    with pytest.raises(ValueError):
        PlayerId(value)
