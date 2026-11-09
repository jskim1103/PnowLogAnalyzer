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

## Implemented VPIP (version 1)

Run `uv run pnow-import --session-id my-session /path/to/export.csv --vpip`.
Results remain separate for NLHE and PLO5 and are grouped by opaque player ID,
regardless of observed name changes.

- Numerator: eligible dealt hands in which the player adds a positive amount by
  calling or raising preflop. Count each hand once, even with multiple raises or
  a later fold. A returned uncalled raise still counts as a voluntary investment.
- Denominator/sample size: eligible hands listing that player in the starting
  stack snapshot. Session joins, sit-backs, and anonymous private-card observations
  do not add participants. A big-blind walk or forced-blind all-in still counts as
  a dealt hand, with no voluntary investment unless a call/raise is observed.
- Percentage: `100 * numerator / denominator`. A zero denominator returns `null`
  in JSON and `N/A` in text. Excluded hands never dilute the denominator.
- Amounts: calls and raises are resulting street commitments in the inspected
  export. Use Decimal, subtract previous commitments to identify positive added
  chips, and exclude zero/negative investment or contributions exceeding stacks.
- Exclusions: invalid/incomplete hand boundaries, missing/multiple/late stack
  snapshots, invalid participants, unknown preflop entries, unsupported variants,
  unsupported forced bets (including unimplemented antes/straddles), missing or
  inconsistent blinds, action-order/actor/fold/all-in inconsistencies, and
  incomplete preflop betting evidence. Dead-small-blind markers are supported.
  Each excluded hand records reasons and its session/hand key.
- Player exclusion counts apply only to identified snapshot participants. If a
  malformed/missing snapshot prevents identifying participants, report the hand
  globally; do not fabricate per-player exclusions or denominators.

The normalizer stops at the first observed flop. Later betting, payouts, side pots,
split pots, and second boards do not add preflop opportunities. Unknown postflop
entries do not invalidate established preflop evidence, though the overall hand
must have matching boundaries in this initial implementation. Forced posts alone
never count as VPIP. Preflop `bet` syntax is conservatively unsupported until a
representative example establishes its meaning.

Eligibility checks track pending decisions and commitments to reject detectable
preflop gaps. They assume no undetectably omitted records within otherwise coherent
exports. They do not validate minimum raises, action reopening, seat-based turn
order, PLO pot-limit sizing, hand ranks, or full pot/stack settlement. A VPIP-eligible
hand is not a fully validated poker hand. Run-it-twice announcements and card shows
are observations, not voluntary betting actions. Duplicate hand keys are rejected
by the statistics API; the importer first merges overlapping source records.

The implementation is split between `ingestion/preflop.py` (source translation),
`domain/preflop.py` (provisional typed contract), and `stats/vpip.py` (eligibility
and aggregation). Tests use synthetic hands with hand-calculated numerators and
denominators, including blind completion, checks, walks, all-ins, repeated raises,
folds after calls, malformed/incomplete input, and per-variant separation.
