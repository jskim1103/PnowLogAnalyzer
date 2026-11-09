"""Source-independent player identity and observed display labels."""

from dataclasses import dataclass


@dataclass(frozen=True)
class PlayerId:
    """Opaque identity; case-sensitive and independent of any display name."""

    value: str

    def __post_init__(self) -> None:
        if not self.value or self.value.isspace():
            raise ValueError("Player ID must not be empty")


@dataclass(frozen=True)
class PlayerReference:
    """An identity and its display name at one observation."""

    player_id: PlayerId
    display_name: str
