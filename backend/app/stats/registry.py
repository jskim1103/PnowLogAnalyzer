"""Executable metric definitions: no planned-only or synthetic dashboard metrics."""

from dataclasses import dataclass


@dataclass(frozen=True)
class MetricDefinition:
    id: str
    name: str
    category: str
    unit: str
    description: str
    numerator: str
    denominator: str
    formula: str
    required_data: tuple[str, ...]
    assumptions: str
    version: str = "1"
    supported_variants: tuple[str, ...] = ("NLHE", "PLO5")
    applicable_filters: tuple[str, ...] = (
        "player",
        "session",
        "variant",
        "date",
        "position",
        "starting_stack_bb",
        "observed_nlhe_class",
    )


REGISTRY: dict[str, MetricDefinition] = {}


def _add(
    identifier: str,
    name: str,
    category: str,
    numerator: str,
    denominator: str,
    *,
    unit: str = "frequency",
    description: str = "",
    required: tuple[str, ...] = ("supported_hand",),
) -> None:
    if identifier in {"preflop.steal", "preflop.bb_fold_steal"}:
        required = ("supported_hand", "known_positions")
    formula = {
        "frequency": "numerator / denominator",
        "ratio": "numerator / denominator",
        "count": "numerator",
        "chips": "numerator",
        "bb100": "100 * numerator / denominator",
        "mean": "numerator / denominator",
    }[unit]
    REGISTRY[identifier] = MetricDefinition(
        identifier,
        name,
        category,
        unit,
        description or name,
        numerator,
        denominator,
        formula,
        required,
        "Observed supported hands only; no currency conversion. Variants separate. "
        "Frequency intervals use a binomial approximation; "
        "observations may be correlated.",
        supported_variants=("NLHE",)
        if category == "starting_hands"
        else ("NLHE", "PLO5"),
    )


_add(
    "hands.dealt",
    "Hands dealt",
    "participation",
    "dealt hands",
    "supported dealt hands",
    unit="count",
)
for identifier, name, description in (
    ("vpip", "VPIP", "At least one positive voluntary preflop call or raise"),
    ("pfr", "PFR", "Raised preflop at least once"),
    ("call", "Called preflop", "Called preflop at least once"),
    ("fold", "Folded preflop", "Folded before the first flop"),
    ("limp", "Limp frequency", "Called the initial blind wager before any raise"),
    ("open_limp", "Open-limp frequency", "First voluntary investor limps"),
    ("overlimp", "Overlimp frequency", "Limped after a prior limper"),
    (
        "all_in",
        "Preflop all-in",
        "Made a voluntary preflop investment exhausting the stack",
    ),
):
    _add(
        "preflop." + identifier,
        name,
        "preflop",
        description,
        "supported dealt hands",
        description=description,
    )
for identifier, name, denominator in (
    ("rfi", "Raise first in", "decisions in an unopened pot before any call/raise"),
    (
        "three_bet",
        "3-bet",
        "decisions facing one raise with raising rights and chips beyond a call",
    ),
    (
        "four_bet",
        "4-bet",
        "decisions facing two raises with raising rights and chips beyond a call",
    ),
    (
        "five_bet",
        "5-bet",
        "decisions facing three raises with raising rights and chips beyond a call",
    ),
    ("squeeze", "Squeeze", "3-bet opportunities after at least one caller of the open"),
    ("cold_call", "Cold call", "nonblind first-investment decisions facing one raise"),
    ("call_open", "Call open", "first voluntary decisions facing one open raise"),
    (
        "fold_to_three_bet",
        "Fold to 3-bet",
        "original opener decisions facing exactly the first reraise",
    ),
    (
        "call_three_bet",
        "Call 3-bet",
        "original opener decisions facing exactly the first reraise",
    ),
    ("limp_fold", "Limp-fold", "limper first decisions facing an opening raise"),
    ("limp_call", "Limp-call", "limper first decisions facing an opening raise"),
    (
        "limp_raise",
        "Limp-reraise",
        "limper first decisions facing an opening raise with raising rights",
    ),
    ("steal", "Attempt to steal", "unopened CO/BTN/SB decisions with raising rights"),
    (
        "check_option",
        "Big blind check option",
        "big blind decisions with no additional call amount",
    ),
):
    _add("preflop." + identifier, name, "preflop", name + " actions", denominator)
_add(
    "preflop.walk",
    "Big blind walk",
    "preflop",
    "BB wins without a voluntary decision by BB",
    "hands posting a big blind",
)
for street in ("flop", "turn", "river"):
    _add(
        street + ".seen",
        "Saw " + street,
        "participation",
        "live at the first " + street + " board",
        "supported dealt hands",
    )
    for action in ("bet", "raise", "call", "check", "fold"):
        _add(
            street + "." + action,
            street.title() + " " + action,
            street,
            action + " decisions",
            street + " voluntary decisions",
        )
    _add(
        street + ".afq",
        street.title() + " aggression frequency",
        street,
        "bets + raises",
        "bets + raises + calls + folds",
    )
    _add(
        street + ".af",
        street.title() + " aggression factor",
        street,
        "bets + raises",
        "calls",
        unit="ratio",
    )
    for response in ("fold", "call", "raise"):
        _add(
            street + "." + response + "_facing_bet",
            street.title() + " " + response + " facing bet",
            street,
            response + " decisions facing a positive wager",
            "decisions facing a positive wager"
            + (" with raising rights" if response == "raise" else ""),
        )
        _add(
            street + ".check_" + response,
            street.title() + " check-" + response,
            street,
            response + " after checking",
            "first decision facing a bet after a check"
            + (" with raising rights" if response == "raise" else ""),
        )
    _add(
        street + ".cbet",
        street.title() + " continuation bet",
        street,
        "bets at a continuation opportunity",
        "first unbet street decisions by the previous qualifying aggressor "
        "with an opponent able to respond",
        description=(
            "Flop: preflop aggressor. Turn/river: same aggressor bet "
            "every prior postflop street; "
            "a donk removes the opportunity."
        ),
    )
    for response in ("fold", "call", "raise"):
        _add(
            street + "." + response + "_to_cbet",
            street.title() + " " + response + " to c-bet",
            street,
            response + " while facing the unre-raised continuation bet",
            "decisions facing that continuation bet"
            + (" with raising rights" if response == "raise" else ""),
        )
_add(
    "showdown.wtsd",
    "Went to showdown",
    "showdown",
    "flop viewers still live in a multi-player river settlement",
    "hands seeing a flop",
)
_add(
    "showdown.wsd",
    "Won money at showdown",
    "showdown",
    "showdowns receiving any positive award (includes split awards)",
    "observed multi-player river showdowns",
)
_add(
    "showdown.wwsf",
    "Won when saw flop",
    "showdown",
    "flop-viewed hands receiving a positive award",
    "hands seeing a flop",
)
for identifier, name, unit in (
    ("net_chips", "Net chips", "chips"),
    ("bb100", "bb/100", "bb100"),
    ("bb_hand", "bb per hand", "mean"),
    ("mean_net", "Mean net chips per hand", "mean"),
):
    _add(
        "results." + identifier,
        name,
        "results",
        "net chips"
        if identifier != "bb100" and identifier != "bb_hand"
        else "sum of hand net / hand big blind",
        "reconciled dealt hands",
        unit=unit,
        required=("reconciled_accounting",),
    )
for identifier, name in (("pair", "Pocket pair"), ("suited", "Suited starting hand")):
    _add(
        "starting." + identifier,
        name,
        "starting_hands",
        name + " observations",
        "NLHE dealt hands with both hole cards observed",
        required=("observed_nlhe_hole_cards",),
    )

for identifier, name, denominator in (
    (
        "isolation",
        "Isolation raise",
        "unraised decisions after a limper with raising rights",
    ),
    (
        "sb_complete",
        "Small blind completion",
        "SB decisions facing only the original big blind",
    ),
    (
        "bb_defend",
        "BB defense versus open",
        "BB decisions facing exactly one opening raise",
    ),
    (
        "bb_call_open",
        "BB call versus open",
        "BB decisions facing exactly one opening raise",
    ),
    (
        "bb_three_bet_open",
        "BB 3-bet versus open",
        "BB opening-raise decisions with raising rights",
    ),
    (
        "bb_fold_steal",
        "BB fold to steal",
        "BB decisions facing an unopened CO/BTN/SB open",
    ),
    (
        "sb_fold_open",
        "SB fold versus open",
        "SB decisions facing exactly one opening raise",
    ),
    (
        "sb_three_bet_open",
        "SB 3-bet versus open",
        "SB opening-raise decisions with raising rights",
    ),
    (
        "fold_to_four_bet",
        "Fold to 4-bet",
        "original 3-bettor decisions facing the first 4-bet",
    ),
    (
        "call_four_bet",
        "Call 4-bet",
        "original 3-bettor decisions facing the first 4-bet",
    ),
    (
        "cold_four_bet",
        "Cold 4-bet",
        "first-investment decisions facing two raises with raising rights",
    ),
):
    _add("preflop." + identifier, name, "preflop", name + " actions", denominator)
for identifier, name in (
    ("open", "Open raise"),
    ("three_bet", "3-bet"),
    ("four_bet", "4-bet"),
):
    _add(
        "preflop." + identifier + "_size_bb",
        name + " size in BB",
        "bet_sizing",
        "sum of resulting street commitment / hand BB",
        name + " actions",
        unit="mean",
    )
    _add(
        "preflop." + identifier + "_success",
        name + " immediate success",
        "preflop",
        name + " actions ending the hand preflop with all opponents folded "
        "and no later aggression",
        name + " actions",
    )
for street in ("flop", "turn", "river"):
    _add(
        street + ".bet_size_pot",
        street.title() + " bet / pot",
        "bet_sizing",
        "sum of opening bet / pot before bet",
        "opening bets with a positive pot",
        unit="mean",
    )
    _add(
        street + ".overbet",
        street.title() + " overbet",
        "bet_sizing",
        "opening bets larger than the pot",
        "opening bets with a positive pot",
    )
    _add(
        street + ".all_in",
        street.title() + " voluntary all-in",
        "all_in",
        "voluntary investments exhausting the available stack",
        street + " voluntary decisions",
    )
_add(
    "postflop.af",
    "Postflop aggression factor",
    "aggression",
    "postflop bets + raises",
    "postflop calls",
    unit="ratio",
)
_add(
    "postflop.afq",
    "Postflop aggression frequency",
    "aggression",
    "postflop bets + raises",
    "postflop bets + raises + calls + folds",
)
_add(
    "preflop.vpip_minus_pfr",
    "VPIP − PFR",
    "preflop",
    "voluntarily played hands without a raise",
    "supported dealt hands",
)
