# Poker metric definitions (draft)

All reported metrics must include **numerator**, **eligible denominator**, **sample size**, and **game type**. The implementation must document how partial/incomplete hands, unknown identities, ante/straddle, and missing actions affect eligibility.

| Metric | Numerator | Denominator | Caveats |
|---|---|---|---|
| VPIP | Dealt hands where player voluntarily invests preflop | Eligible dealt hands | Forced blinds/antes alone don't count; voluntary completion/raise does. |
| PFR | Dealt hands where player raises at least once preflop | Eligible dealt hands | Count hands, not number of raises. |
| 3-bet | Eligible opportunities when player reraises the opening raise preflop | Times player could legally 3-bet preflop | Determine whether a raise was the first open versus a prior 3-bet, and account for all-in restrictions. |
| RFI | Unopened preflop opportunities where player opens with a raise | Eligible opportunities to open when action reaches player unopened | Exclude situations where a prior player opened. |
| Fold to 3-bet | Player folds after facing a preflop 3-bet following their own open | Times original raiser faces an eligible 3-bet decision | Define handling for multiple callers, cold 4-bets, all-ins. |
| Flop c-bet | Preflop aggressor bets the flop when action affords a continuation-bet opportunity | Eligible flop c-bet opportunities | Multiway and positional cases require a precise convention. |
| bb/100 | Net chips converted to big-blind units / hands * 100 | Eligible hands | Different stakes require hand-specific BB conversion; avoid mixing tournament and cash-game interpretations. |

## Probability conventions

For a heads-up call that closes betting, with no rake, no tie possibility, and no future investment:

- Let `P` be the pot **after the opponent's bet but before our call**.
- Let `C` be the additional call amount.
- Break-even equity: `C / (P + C)`.
- Net EV of a call: `p_win * P - (1 - p_win) * C`.

If ties are possible, equity is not simply win probability: use expected share of the final pot, and account for split outcomes explicitly. For multiple players, side pots, rake or future betting, use the relevant model rather than this toy formula.

## GTO versus descriptive stats

- Empirical action frequencies and win rates are *observations*.
- Equity versus an assumed range is a *model estimate*.
- A GTO label/solver comparison is conditional on an explicit game tree, legal actions, ranges, stack sizes, positions, bet sizes, rake, player count, and solver assumptions.
- A losing call can be +EV; a winning call can be -EV. Realized outcome does not validate the original decision.

As parser samples become available, add exact eligibility rules, edge cases, fixtures, and formulas here.
