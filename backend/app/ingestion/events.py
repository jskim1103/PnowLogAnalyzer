"""Observed PokerNow event grammar; no poker-state or metric calculations."""

import re
from dataclasses import dataclass

from app.domain.players import PlayerReference
from app.ingestion.players import PlayerReferenceError, parse_player_reference

REFERENCE = r'"[^\r\n]* @ [^"\s]+"'
AMOUNT = r"\d+\.\d{2}"
CARD = r"(?:10|[2-9JQKA])[♠♥♦♣]"
CARDS = rf"{CARD}(?:, {CARD})*"
START = re.compile(
    rf"-- starting hand #(\d+) \(id: ([^\s)]+)\)  (.+?) "
    rf"\((?:dealer: (?P<dealer>{REFERENCE})|dead button)\) --"
)
END = re.compile(r"-- ending hand #(\d+) --")
STACK = re.compile(
    rf'#(?P<seat>\d+) (?P<player>"[^\r\n]*? @ [^"\s]+") '
    rf"\((?P<amount>{AMOUNT})\)(?= \| |$)"
)
PLAYER_PATTERNS = [
    rf"(?P<player>{REFERENCE}) (?:folds|checks)",
    rf"(?P<player>{REFERENCE}) (?:calls|bets|raises to) {AMOUNT}(?: and go all in)?",
    rf"(?P<player>{REFERENCE}) posts a (?:small|big) blind of {AMOUNT}",
    rf"(?P<player>{REFERENCE}) shows a {CARDS}\.",
    rf"(?P<player>{REFERENCE}) collected {AMOUNT} from pot(?: with .+)?",
    rf"Uncalled bet of {AMOUNT} returned to (?P<player>{REFERENCE})",
    rf"The player (?P<player>{REFERENCE}) (?:joined the game with a stack of|"
    rf"quits the game with a stack of|stand up with the stack of|"
    rf"sit back with the stack of) {AMOUNT}\.",
    rf"The player (?P<player>{REFERENCE}) requested a seat\.",
    rf"The admin approved the player (?P<player>{REFERENCE}) "
    rf"participation with a stack of {AMOUNT}\.",
    rf"The admin updated the player (?P<player>{REFERENCE}) stack "
    rf"from {AMOUNT} to {AMOUNT}\.",
    rf"WARNING: the admin queued the stack change for the player "
    rf"(?P<player>{REFERENCE}) adding {AMOUNT} chips in the next hand\.",
    rf"(?P<player>{REFERENCE}) chooses to (?: run it twice|not run it twice)\.",
]
OWNERSHIP = re.compile(
    rf"The player (?P<player>{REFERENCE}) passed the room ownership "
    rf"to (?P<recipient>{REFERENCE})\."
)
PATTERNS = tuple(re.compile(pattern) for pattern in PLAYER_PATTERNS)
BOARD = re.compile(
    rf"(?:Flop|Turn|River|Undealt cards)(?: \(second run\))?: "
    rf"(?:{CARDS})? \[{CARDS}\]"
)


@dataclass(frozen=True)
class ClassifiedEvent:
    kind: str
    players: tuple[PlayerReference, ...] = ()


def classify_event(entry: str) -> ClassifiedEvent:
    """Recognize syntax only; original entries remain in the import report."""
    start = START.fullmatch(entry)
    if start:
        dealer = start["dealer"]
        return ClassifiedEvent(
            "hand_start", (parse_player_reference(dealer),) if dealer else ()
        )
    if END.fullmatch(entry):
        return ClassifiedEvent("hand_end")
    if entry.startswith("Player stacks: "):
        body = entry.removeprefix("Player stacks: ")
        position = 0
        players: list[PlayerReference] = []
        seats: set[int] = set()
        while position < len(body):
            match = STACK.match(body, position)
            if match is None:
                raise PlayerReferenceError("Malformed player stack snapshot")
            player = parse_player_reference(match["player"])
            seat = int(match["seat"])
            if (
                seat <= 0
                or seat in seats
                or any(previous.player_id == player.player_id for previous in players)
            ):
                raise PlayerReferenceError(
                    "Duplicate player or invalid seat in snapshot"
                )
            seats.add(seat)
            players.append(player)
            position = match.end()
            if position < len(body):
                position += len(" | ")
                if position == len(body):
                    raise PlayerReferenceError("Trailing stack separator")
        if not players:
            raise PlayerReferenceError("Empty player stack snapshot")
        return ClassifiedEvent("stacks", tuple(players))
    for pattern in PATTERNS:
        match = pattern.fullmatch(entry)
        if match:
            return ClassifiedEvent(
                "player_event", (parse_player_reference(match["player"]),)
            )
    ownership = OWNERSHIP.fullmatch(entry)
    if ownership:
        return ClassifiedEvent(
            "ownership",
            tuple(
                parse_player_reference(ownership[key])
                for key in ("player", "recipient")
            ),
        )
    if BOARD.fullmatch(entry):
        return ClassifiedEvent("board_observation")
    if re.fullmatch(rf"Your hand is {CARDS}", entry):
        return ClassifiedEvent("unattributed_cards")
    if entry in {
        "Dead Small Blind",
        "Remaining players decide whether to run it twice.",
        "All players in hand choose to run it twice.",
        "Some players choose to not run it twice.",
    }:
        return ClassifiedEvent("table_event")
    if re.fullmatch(
        r"Game Config Changes\n\* Poker Variant: "
        r"(?:No Limit Texas Hold'em|Pot Limit Omaha 5 Hi) » "
        r"(?:No Limit Texas Hold'em|Pot Limit Omaha 5 Hi)",
        entry,
    ):
        return ClassifiedEvent("configuration")
    return ClassifiedEvent("unknown")
