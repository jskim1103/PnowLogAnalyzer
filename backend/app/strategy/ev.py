"""Explicit one-pot toy models, not solver recommendations."""

from decimal import Decimal


def call_ev(
    pot_before_call: Decimal,
    call: Decimal,
    equity: Decimal,
    *,
    rake: Decimal = Decimal(0),
    closes_betting: bool = True,
) -> dict[str, Decimal]:
    if (
        pot_before_call < 0
        or call <= 0
        or not 0 <= equity <= 1
        or rake < 0
        or rake >= pot_before_call + call
    ):
        raise ValueError("Invalid pot, call, equity or rake")
    if not closes_betting:
        raise ValueError("Future betting is not modeled; the call must close betting")
    final = pot_before_call + call - rake
    return {
        "required_equity": call / final,
        "call_ev": equity * final - call,
        "fold_ev": Decimal(0),
    }


def bluff_model(
    pot: Decimal,
    bet: Decimal,
    fold_probability: Decimal,
    equity_when_called: Decimal = Decimal(0),
) -> dict[str, Decimal]:
    if (
        pot <= 0
        or bet <= 0
        or not 0 <= fold_probability <= 1
        or not 0 <= equity_when_called <= 1
    ):
        raise ValueError("Invalid pot, bet or probability")
    return {
        "break_even_fold_frequency": bet / (pot + bet),
        "toy_mdf": pot / (pot + bet),
        "ev": fold_probability * pot
        + (1 - fold_probability) * (equity_when_called * (pot + 2 * bet) - bet),
    }
