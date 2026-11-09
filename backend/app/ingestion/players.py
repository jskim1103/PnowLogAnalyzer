"""Decode complete PokerNow player references at known event positions."""

from app.domain.players import PlayerId, PlayerReference


class PlayerReferenceError(ValueError):
    """A complete player reference does not match the supported grammar."""


def parse_player_reference(text: str) -> PlayerReference:
    """Parse '"display name @ opaque-id"', preserving the name exactly.

    Callers must first locate the reference using the enclosing event grammar.
    The final separator allows names containing ' @ ' or embedded quotes.
    """
    if len(text) < 2 or not (text.startswith('"') and text.endswith('"')):
        raise PlayerReferenceError("Expected a complete quoted player reference")
    name, separator, identifier = text[1:-1].rpartition(" @ ")
    if not separator or not identifier:
        raise PlayerReferenceError("Expected a display name and player ID separator")
    if any(character.isspace() or character == '"' for character in identifier):
        raise PlayerReferenceError("Player ID contains whitespace or quotation marks")
    if "\n" in name or "\r" in name:
        raise PlayerReferenceError("Player display name contains a line break")
    return PlayerReference(PlayerId(identifier), name)
