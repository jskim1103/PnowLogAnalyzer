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

## Registry analytics (version 1)

`stats.registry` exposes 116 executable definitions, not planned placeholders. The
[generated catalog](metric-catalog.md) includes numerator and denominator for each.
`stats.analytics` consumes source-independent reconstructed Hand objects; it never
reads PokerNow text. The API/UI can query players, sessions, variants, UTC dates,
known positions, starting stacks in BB, and observed NLHE classes.

Unlike the legacy preflop-only VPIP interface above, registry metrics conservatively
require a consistent reconstructed hand. This intentionally excludes otherwise
usable preflop data when later hand evidence is invalid. Reconciled accounting is
additionally required for financial fields; known complete NLHE cards are required
for starting-card fields. Excluded hands never enter a frequency denominator. A
filter on a known starting class includes observed matching cards only, not inferred
hidden holdings. Unknown-class coverage is reported in the starting-hand explorer.

### Frequency conventions

- Hand-based participation counts once per dealt hand, not once per action.
- RFI requires an unopened, unlimped pot and legal raising capacity. Open-raise
  sizing/success instead uses the first raise, including an isolation raise.
- 3/4/5-bet opportunities require respectively one/two/three prior observed raises,
  facing a wager, raising rights and chips beyond a call. Short raises still
  increase the observed raise count; they do not automatically reopen raise rights.
- Squeeze opportunities additionally require a caller of the opening raise.
- Call-open is a first-investment decision facing one open; cold-call additionally
  excludes blind posters. Limp responses use the limper's first decision facing
  the initial open. Fold/call to 3-bet refer to the original opener; fold/call to
  4-bet refer to the original 3-bettor. Later cold reraises are separate contexts.
- ATS uses unopened CO/BTN/BTN-SB/SB opportunities with raising rights.
  ATS and fold-to-steal conservatively exclude hands with incomplete named positions. BB fold to
  steal uses that recorded opener context. BB/SB defense denominators are decisions
  facing the first open, never automatically all dealt hands.
- Immediate raise success means all opponents fold preflop, no board is dealt,
  and that raise is the final aggression. Winning later does not count.
- Street action frequencies use voluntary decisions on that street. AFq excludes
  checks: `(bets + raises)/(bets + raises + calls + folds)`. AF uses calls as its
  denominator; zero calls yields null rather than infinity. Overall AF/AFq are
  postflop only. Check-response opportunities use the first facing-bet decision
  after a check; raising responses additionally require raise capacity.
- Flop c-bet opportunities belong to the preflop aggressor at their first unbet
  decision with an opponent able to respond. A prior donk removes the opportunity.
  Turn/river c-bets require the same qualifying aggressor to have bet each previous
  postflop street and retained final street aggression. They are double/triple
  barrels, not delayed c-bets. Responses stop being c-bet responses after a reraise.
- WTSD uses flop viewers; showdown requires multiple nonfolded participants and a
  complete river board. W$SD counts receiving any positive award, including split
  awards, not net profitability. WWSF uses positive awards among flop viewers.
  Voluntary post-fold card reveals do not turn a folded hand into a showdown.
- Bet/pot means the opening bet divided by the pot before that action. Overbet means
  that opening bet exceeds that pot. Raise sizes preserve resulting commitments.
  Voluntary all-in frequencies require positive chips added and stack exhaustion.

### Financial and reliability conventions

Net chips = awards − contributions + returns. bb/100 is the sum of each eligible
hand's net/BB divided by eligible dealt hands, multiplied by 100. Unknown stakes or
chip-to-currency conversion never become inferred dollar results. Performance charts
include supported reconciled results only and show exclusions. Observed peak-to-trough
chip drawdown is descriptive, not a future-risk prediction.

Values use Decimal fractions internally; the UI formats frequencies as percentages.
Binomial frequencies report 95% Wilson intervals. Repeated decisions and sessions
can be correlated, so these are descriptive binomial approximations, not independent
proof of skill. Means, monetary totals and aggression-factor ratios do not receive
fake binomial intervals. Monte Carlo equity instead uses per-player 95% Hoeffding
bounds on bounded pot shares, including ties; exact enumeration has no sampling
uncertainty. Weighted range priors are explicit assumptions conditioned jointly on
card compatibility, not opponent observations or estimates derived from folds.

Probability/EV models and remaining unsupported families are documented in
`implementation-status.md`. Planned probes/floats/delayed bets, all-in EV, solver
recommendations and bluff/value classifications are not advertised as executable.
