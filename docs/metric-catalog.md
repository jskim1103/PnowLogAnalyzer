# Metric catalog and input dependencies

This file distinguishes planned coverage from executable implementations. The registry is the source of truth for 116 executable metrics, formulas,
assumptions and supported variants. The dependency table below includes planned
families as well as implemented ones; the generated table lists only executable
definitions.

| Input tier | Metric families | Required evidence and acceptance tests |
|---|---|---|
| Dealt roster + complete preflop | hands, VPIP, PFR, limps, calls, folds, open-limp, overlimp, RFI, cold-call, check-option, walks, preflop all-in | stable IDs, real dealt players, forced/voluntary delta; walks and short all-ins |
| Preflop decision context | 3/4/5-bets, squeeze, isolation, steal/defense, raise/call/fold responses, sizing and success | eligible legal raise rights, previous aggression/callers, live seats and positions; short raises do not automatically reopen |
| Complete street decisions | bet/raise/call/check/fold frequencies, AF/AFq, check-raise/call/fold, folds facing bets, donks/probes, floats | street boundaries, opportunities, active/all-in states, pot before decision; all-in runouts have no betting opportunities |
| Cross-street aggression | flop c-bet and response, delayed c-bet, double/triple barrel and success | previous-street aggressor, heads-up/multiway, first-bet opportunity, early donks, folds and all-ins |
| Terminal states / awards | WTSD, W$SD, WWSF, showdown/non-showdown results, splits, all-in showdown | distinguish multiple active players at showdown from voluntary post-fold reveals; wins versus net profits separately |
| Reconciled exact accounting | net chips, bb/100, session/cumulative results, pots won/lost, drawdown/streaks, variance, positional/stack/stake breakdowns | contributions minus returns, awards, explicit rake and per-hand BB; do not convert arbitrary chips to dollars |
| Known positions / stacks | all relevant metrics by seat role, table size, effective stack, SPR, bet size, opponent | actual button and active seats; heads-up exception; dead-button uncertainty; reliable starting stacks |
| Observed cards | 169/1326 Hold'em combinations, PLO5 features, hand strength, board/draw features, card-conditioned metrics | exactly observed cards and owner; no folded-card inference; no Hold'em matrix for PLO5 |
| Explicit mathematical models | equity, draws, combinatorics, pot odds, call/bluff EV, MDF, Wilson/Bayesian intervals, all-in pot shares | ties, blocker removal, exact game variant, ranges, rake/future betting/folds/closing action; reproducible seeds |
| Actual solver models | CFR, strategy lookup, action EV loss, range/nut advantage | specified tree/ranges/stacks/sizing/rake; unavailable until real solver output exists |

All frequency results require a metric-specific opportunity denominator and must
return null for zero denominator. Every variant is aggregated independently. Each
family needs independent synthetic reference examples before being marked complete.
Per-opponent chip attribution, river value/bluff labels, and all-in adjusted EV are
unavailable when source observations do not identify the requisite facts.

<!-- BEGIN EXECUTABLE METRICS -->

## Executable catalog (116 metrics)

Generated from `app.stats.registry`; do not edit these rows manually.

| ID | Name | Unit | Numerator | Eligible denominator |
|---|---|---|---|---|
| hands.dealt | Hands dealt | count | dealt hands | supported dealt hands |
| preflop.vpip | VPIP | frequency | At least one positive voluntary preflop call or raise | supported dealt hands |
| preflop.pfr | PFR | frequency | Raised preflop at least once | supported dealt hands |
| preflop.call | Called preflop | frequency | Called preflop at least once | supported dealt hands |
| preflop.fold | Folded preflop | frequency | Folded before the first flop | supported dealt hands |
| preflop.limp | Limp frequency | frequency | Called the initial blind wager before any raise | supported dealt hands |
| preflop.open_limp | Open-limp frequency | frequency | First voluntary investor limps | supported dealt hands |
| preflop.overlimp | Overlimp frequency | frequency | Limped after a prior limper | supported dealt hands |
| preflop.all_in | Preflop all-in | frequency | Made a voluntary preflop investment exhausting the stack | supported dealt hands |
| preflop.rfi | Raise first in | frequency | Raise first in actions | decisions in an unopened pot before any call/raise |
| preflop.three_bet | 3-bet | frequency | 3-bet actions | decisions facing one raise with raising rights and chips beyond a call |
| preflop.four_bet | 4-bet | frequency | 4-bet actions | decisions facing two raises with raising rights and chips beyond a call |
| preflop.five_bet | 5-bet | frequency | 5-bet actions | decisions facing three raises with raising rights and chips beyond a call |
| preflop.squeeze | Squeeze | frequency | Squeeze actions | 3-bet opportunities after at least one caller of the open |
| preflop.cold_call | Cold call | frequency | Cold call actions | nonblind first-investment decisions facing one raise |
| preflop.call_open | Call open | frequency | Call open actions | first voluntary decisions facing one open raise |
| preflop.fold_to_three_bet | Fold to 3-bet | frequency | Fold to 3-bet actions | original opener decisions facing exactly the first reraise |
| preflop.call_three_bet | Call 3-bet | frequency | Call 3-bet actions | original opener decisions facing exactly the first reraise |
| preflop.limp_fold | Limp-fold | frequency | Limp-fold actions | limper first decisions facing an opening raise |
| preflop.limp_call | Limp-call | frequency | Limp-call actions | limper first decisions facing an opening raise |
| preflop.limp_raise | Limp-reraise | frequency | Limp-reraise actions | limper first decisions facing an opening raise with raising rights |
| preflop.steal | Attempt to steal | frequency | Attempt to steal actions | unopened CO/BTN/SB decisions with raising rights |
| preflop.check_option | Big blind check option | frequency | Big blind check option actions | big blind decisions with no additional call amount |
| preflop.walk | Big blind walk | frequency | BB wins without a voluntary decision by BB | hands posting a big blind |
| flop.seen | Saw flop | frequency | live at the first flop board | supported dealt hands |
| flop.bet | Flop bet | frequency | bet decisions | flop voluntary decisions |
| flop.raise | Flop raise | frequency | raise decisions | flop voluntary decisions |
| flop.call | Flop call | frequency | call decisions | flop voluntary decisions |
| flop.check | Flop check | frequency | check decisions | flop voluntary decisions |
| flop.fold | Flop fold | frequency | fold decisions | flop voluntary decisions |
| flop.afq | Flop aggression frequency | frequency | bets + raises | bets + raises + calls + folds |
| flop.af | Flop aggression factor | ratio | bets + raises | calls |
| flop.fold_facing_bet | Flop fold facing bet | frequency | fold decisions facing a positive wager | decisions facing a positive wager |
| flop.check_fold | Flop check-fold | frequency | fold after checking | first decision facing a bet after a check |
| flop.call_facing_bet | Flop call facing bet | frequency | call decisions facing a positive wager | decisions facing a positive wager |
| flop.check_call | Flop check-call | frequency | call after checking | first decision facing a bet after a check |
| flop.raise_facing_bet | Flop raise facing bet | frequency | raise decisions facing a positive wager | decisions facing a positive wager with raising rights |
| flop.check_raise | Flop check-raise | frequency | raise after checking | first decision facing a bet after a check with raising rights |
| flop.cbet | Flop continuation bet | frequency | bets at a continuation opportunity | first unbet street decisions by the previous qualifying aggressor with an opponent able to respond |
| flop.fold_to_cbet | Flop fold to c-bet | frequency | fold while facing the unre-raised continuation bet | decisions facing that continuation bet |
| flop.call_to_cbet | Flop call to c-bet | frequency | call while facing the unre-raised continuation bet | decisions facing that continuation bet |
| flop.raise_to_cbet | Flop raise to c-bet | frequency | raise while facing the unre-raised continuation bet | decisions facing that continuation bet with raising rights |
| turn.seen | Saw turn | frequency | live at the first turn board | supported dealt hands |
| turn.bet | Turn bet | frequency | bet decisions | turn voluntary decisions |
| turn.raise | Turn raise | frequency | raise decisions | turn voluntary decisions |
| turn.call | Turn call | frequency | call decisions | turn voluntary decisions |
| turn.check | Turn check | frequency | check decisions | turn voluntary decisions |
| turn.fold | Turn fold | frequency | fold decisions | turn voluntary decisions |
| turn.afq | Turn aggression frequency | frequency | bets + raises | bets + raises + calls + folds |
| turn.af | Turn aggression factor | ratio | bets + raises | calls |
| turn.fold_facing_bet | Turn fold facing bet | frequency | fold decisions facing a positive wager | decisions facing a positive wager |
| turn.check_fold | Turn check-fold | frequency | fold after checking | first decision facing a bet after a check |
| turn.call_facing_bet | Turn call facing bet | frequency | call decisions facing a positive wager | decisions facing a positive wager |
| turn.check_call | Turn check-call | frequency | call after checking | first decision facing a bet after a check |
| turn.raise_facing_bet | Turn raise facing bet | frequency | raise decisions facing a positive wager | decisions facing a positive wager with raising rights |
| turn.check_raise | Turn check-raise | frequency | raise after checking | first decision facing a bet after a check with raising rights |
| turn.cbet | Turn continuation bet | frequency | bets at a continuation opportunity | first unbet street decisions by the previous qualifying aggressor with an opponent able to respond |
| turn.fold_to_cbet | Turn fold to c-bet | frequency | fold while facing the unre-raised continuation bet | decisions facing that continuation bet |
| turn.call_to_cbet | Turn call to c-bet | frequency | call while facing the unre-raised continuation bet | decisions facing that continuation bet |
| turn.raise_to_cbet | Turn raise to c-bet | frequency | raise while facing the unre-raised continuation bet | decisions facing that continuation bet with raising rights |
| river.seen | Saw river | frequency | live at the first river board | supported dealt hands |
| river.bet | River bet | frequency | bet decisions | river voluntary decisions |
| river.raise | River raise | frequency | raise decisions | river voluntary decisions |
| river.call | River call | frequency | call decisions | river voluntary decisions |
| river.check | River check | frequency | check decisions | river voluntary decisions |
| river.fold | River fold | frequency | fold decisions | river voluntary decisions |
| river.afq | River aggression frequency | frequency | bets + raises | bets + raises + calls + folds |
| river.af | River aggression factor | ratio | bets + raises | calls |
| river.fold_facing_bet | River fold facing bet | frequency | fold decisions facing a positive wager | decisions facing a positive wager |
| river.check_fold | River check-fold | frequency | fold after checking | first decision facing a bet after a check |
| river.call_facing_bet | River call facing bet | frequency | call decisions facing a positive wager | decisions facing a positive wager |
| river.check_call | River check-call | frequency | call after checking | first decision facing a bet after a check |
| river.raise_facing_bet | River raise facing bet | frequency | raise decisions facing a positive wager | decisions facing a positive wager with raising rights |
| river.check_raise | River check-raise | frequency | raise after checking | first decision facing a bet after a check with raising rights |
| river.cbet | River continuation bet | frequency | bets at a continuation opportunity | first unbet street decisions by the previous qualifying aggressor with an opponent able to respond |
| river.fold_to_cbet | River fold to c-bet | frequency | fold while facing the unre-raised continuation bet | decisions facing that continuation bet |
| river.call_to_cbet | River call to c-bet | frequency | call while facing the unre-raised continuation bet | decisions facing that continuation bet |
| river.raise_to_cbet | River raise to c-bet | frequency | raise while facing the unre-raised continuation bet | decisions facing that continuation bet with raising rights |
| showdown.wtsd | Went to showdown | frequency | flop viewers still live in a multi-player river settlement | hands seeing a flop |
| showdown.wsd | Won money at showdown | frequency | showdowns receiving any positive award (includes split awards) | observed multi-player river showdowns |
| showdown.wwsf | Won when saw flop | frequency | flop-viewed hands receiving a positive award | hands seeing a flop |
| results.net_chips | Net chips | chips | net chips | reconciled dealt hands |
| results.bb100 | bb/100 | bb100 | sum of hand net / hand big blind | reconciled dealt hands |
| results.bb_hand | bb per hand | mean | sum of hand net / hand big blind | reconciled dealt hands |
| results.mean_net | Mean net chips per hand | mean | net chips | reconciled dealt hands |
| starting.pair | Pocket pair | frequency | Pocket pair observations | NLHE dealt hands with both hole cards observed |
| starting.suited | Suited starting hand | frequency | Suited starting hand observations | NLHE dealt hands with both hole cards observed |
| preflop.isolation | Isolation raise | frequency | Isolation raise actions | unraised decisions after a limper with raising rights |
| preflop.sb_complete | Small blind completion | frequency | Small blind completion actions | SB decisions facing only the original big blind |
| preflop.bb_defend | BB defense versus open | frequency | BB defense versus open actions | BB decisions facing exactly one opening raise |
| preflop.bb_call_open | BB call versus open | frequency | BB call versus open actions | BB decisions facing exactly one opening raise |
| preflop.bb_three_bet_open | BB 3-bet versus open | frequency | BB 3-bet versus open actions | BB opening-raise decisions with raising rights |
| preflop.bb_fold_steal | BB fold to steal | frequency | BB fold to steal actions | BB decisions facing an unopened CO/BTN/SB open |
| preflop.sb_fold_open | SB fold versus open | frequency | SB fold versus open actions | SB decisions facing exactly one opening raise |
| preflop.sb_three_bet_open | SB 3-bet versus open | frequency | SB 3-bet versus open actions | SB opening-raise decisions with raising rights |
| preflop.fold_to_four_bet | Fold to 4-bet | frequency | Fold to 4-bet actions | original 3-bettor decisions facing the first 4-bet |
| preflop.call_four_bet | Call 4-bet | frequency | Call 4-bet actions | original 3-bettor decisions facing the first 4-bet |
| preflop.cold_four_bet | Cold 4-bet | frequency | Cold 4-bet actions | first-investment decisions facing two raises with raising rights |
| preflop.open_size_bb | Open raise size in BB | mean | sum of resulting street commitment / hand BB | Open raise actions |
| preflop.open_success | Open raise immediate success | frequency | Open raise actions ending the hand preflop with all opponents folded and no later aggression | Open raise actions |
| preflop.three_bet_size_bb | 3-bet size in BB | mean | sum of resulting street commitment / hand BB | 3-bet actions |
| preflop.three_bet_success | 3-bet immediate success | frequency | 3-bet actions ending the hand preflop with all opponents folded and no later aggression | 3-bet actions |
| preflop.four_bet_size_bb | 4-bet size in BB | mean | sum of resulting street commitment / hand BB | 4-bet actions |
| preflop.four_bet_success | 4-bet immediate success | frequency | 4-bet actions ending the hand preflop with all opponents folded and no later aggression | 4-bet actions |
| flop.bet_size_pot | Flop bet / pot | mean | sum of opening bet / pot before bet | opening bets with a positive pot |
| flop.overbet | Flop overbet | frequency | opening bets larger than the pot | opening bets with a positive pot |
| flop.all_in | Flop voluntary all-in | frequency | voluntary investments exhausting the available stack | flop voluntary decisions |
| turn.bet_size_pot | Turn bet / pot | mean | sum of opening bet / pot before bet | opening bets with a positive pot |
| turn.overbet | Turn overbet | frequency | opening bets larger than the pot | opening bets with a positive pot |
| turn.all_in | Turn voluntary all-in | frequency | voluntary investments exhausting the available stack | turn voluntary decisions |
| river.bet_size_pot | River bet / pot | mean | sum of opening bet / pot before bet | opening bets with a positive pot |
| river.overbet | River overbet | frequency | opening bets larger than the pot | opening bets with a positive pot |
| river.all_in | River voluntary all-in | frequency | voluntary investments exhausting the available stack | river voluntary decisions |
| postflop.af | Postflop aggression factor | ratio | postflop bets + raises | postflop calls |
| postflop.afq | Postflop aggression frequency | frequency | postflop bets + raises | postflop bets + raises + calls + folds |
| preflop.vpip_minus_pfr | VPIP − PFR | frequency | voluntarily played hands without a raise | supported dealt hands |
<!-- END EXECUTABLE METRICS -->
