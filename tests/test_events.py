import pytest
from app.ingestion.events import classify_event
from app.ingestion.players import PlayerReferenceError


@pytest.mark.parametrize("name", ["Emoji 🐣", "Comma, Name", "A @ B", "A | B", 'A "B"'])
def test_player_reference_in_snapshot_preserves_name(name: str) -> None:
    event = classify_event(
        f'Player stacks: #1 "{name} @ synthetic_a" (50.00) | '
        '#9 "Other @ synthetic_b" (20.00)'
    )
    assert event.kind == "stacks"
    assert [p.player_id.value for p in event.players] == ["synthetic_a", "synthetic_b"]
    assert event.players[0].display_name == name


@pytest.mark.parametrize(
    "suffix",
    [
        "calls 0.50",
        "raises to 2.00",
        "calls 4.57 and go all in",
        "posts a big blind of 0.50",
        "shows a A♣.",
        "shows a A♣, K♦, Q♥, J♠, 10♣.",
        "collected 2.00 from pot",
        "collected 2.00 from pot with Pair, A's (combination: A♣, A♥, 2♠, 3♠, 4♠)",
    ],
)
def test_observed_player_event_forms(suffix: str) -> None:
    event = classify_event(f'"A 🐣 @ synthetic_a" {suffix}')
    assert event.kind == "player_event"
    assert event.players[0].player_id.value == "synthetic_a"


def test_private_cards_stay_unattributed_and_undealt_cards_are_observations() -> None:
    event = classify_event("Your hand is A♣, K♦, Q♥, J♠, 10♣")
    assert event.kind == "unattributed_cards" and not event.players
    assert classify_event("Undealt cards:  [A♣, K♦, Q♥, J♠, 10♣]").players == ()


@pytest.mark.parametrize(
    "body",
    [
        '#1 "A @ a" (2.00) | ',
        '#1 "A @ a" (2.00) | #1 "B @ b" (2.00)',
        '#1 "A @ a" (2.00) | #2 "B @ a" (2.00)',
        '#0 "A @ a" (2.00)',
        '#1 "A @ a" (2.00) ignored',
    ],
)
def test_bad_stack_snapshot_is_reported(body: str) -> None:
    with pytest.raises(PlayerReferenceError):
        classify_event("Player stacks: " + body)


def test_unknown_text_does_not_create_player_identity() -> None:
    event = classify_event('A message mentioning "Not a player @ arbitrary"')
    assert event.kind == "unknown"
    assert not event.players
