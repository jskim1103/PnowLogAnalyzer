# Hand contract and reconstruction (version 2)

`domain.hands` defines immutable source-independent cards, participants, normalized
events, provenance, decisions, board runouts, side-pot layers and results.
`ingestion.hands` alone knows PokerNow wording. Existing provisional preflop models
and the VPIP API remain compatible.

## Pipeline

1. Strict UTF-8 CSV decoding and session-scoped record merging, retaining all source
   locations. Record conflicts fail rather than replacing existing content.
2. Normalize every hand record to a HandEvent, including metadata/unknown records.
   Calls and raises use observed street totals; bets and blinds add exact Decimal
   amounts. Preserve source amounts alongside reconstructed positive chip deltas.
3. Reconstruct preflop/flop/turn/river in chronological sequence. Record pot before
   each decision, additional amount facing, capped call amount, remaining stacks,
   active participants, previous street aggressor, raise rights and seat position.
4. Track pending decisions, clockwise active-seat action order, folds, all-ins,
   minimum increases, and pot-limit caps. Short all-ins do not automatically reopen
   an actor's raise rights; cumulative increases are considered. The effective
   stack field is min(actor remaining, largest live opponent remaining), not a
   claim that every side pot has that same effective stack.
5. Apply explicit unmatched-chip returns and pot awards separately. Ending stacks
   and net results are available only when the ledger reconciles.

All timestamps normalize to UTC; date filters use UTC calendar dates. Raw timestamps
remain in retained source records. IDs are opaque and display names are observations.

## Side pots and settlement

Layer net contributions by distinct contribution caps. Folded contributions remain
in each layer, but folded players are ineligible. A Decimal max-flow feasibility
check verifies that observed player awards can be funded from pots for which they
are eligible. It does not invent a specific source pot/run allocation. A unique
unmatched highest contribution requires an explicit uncalled return.

Conservation is `sum(contributions - returns) == sum(awards)` under the explicit
current assumption of no recorded rake. Unsupported rake events make reconstruction
unavailable rather than silently adjusting the balance. Complete, supported hands
must also have coherent betting completion before street changes and awards.

## Cards and runouts

Use canonical `2c` through `As` cards. Preserve full and partial reveals; never infer
hidden cards. Anonymous private cards stay anonymous unless the caller explicitly
provides an export owner ID. A fold has no card-inference semantics.

Board observations preserve the complete board prefix and explicit run index.
An explicit unanimous run-it-twice announcement requires two complete boards at
showdown; missing runouts are partial even when awards balance. Second runouts can
share the common flop/turn prefix; repeated cards after divergence
are invalid. `Undealt cards` are not treated as live board cards. Unlabeled awards
have run=null, not an assumed first-run allocation. Known duplicate card identities
are diagnosed; anonymous private cards cannot be silently assigned to a participant.

## Validation grades

- **reconciled**: implemented action-state checks and exact accounting both pass.
- **partial**: missing boundaries, unknown grammar or incomplete roster/variant
  prevents a definitive reconstruction. Original observations remain available.
- **invalid**: supported, sufficiently complete evidence contradicts the implemented state/accounting
  checks. Diagnostics include event order and the original event's source location.

These grades are not solver validation or proof of a winning hand. We do not infer
showdown winners from missing cards. The engine does not implement every house-rule
exception, blind-posting configuration or assignment of unlabeled awards to runs.
Named positions remain unknown with a dead button. With a dead small blind, only
the explicit BTN and BB are labeled; other named roles remain unknown rather than
shifting the BB into a fictitious SB seat. Blind-specific metrics use observed posts,
not guessed position labels. Blind evidence still supports
clockwise action-order checks. Heads-up BTN/SB is distinct from multiway SB.

The action model's normal-raise and pot-limit formulas are independently exercised
by synthetic fixtures. The [Poker TDA rules](https://www.pokertda.com/view-poker-tda-rules/)
provide a reference for full raises and reopening, not evidence that every PokerNow
house rule or export variant has been verified. Unusual short opening wagers and
short blind levels require further real-log coverage before claiming full legality.

## Storage and schema

DuckDB schema version 1 caches serialized typed Hand objects (reconstruction version
2), raw source bytes, import reports, participants and decisions. Monetary fields
serialize as Decimal strings; analytics never infer dollars from chips. Session
imports are transactional. Conflicting source records, inconsistent owner IDs and
reassignment of an identical source to another session fail without overwriting the
previous session. New overlapping exports rebuild that session from retained sources;
ordinary startup reads cached histories without reparsing CSVs. A reconstruction
version mismatch automatically rebuilds only stale sessions. Manual rebuild remains
available through the session action. Unsupported schema versions fail
explicitly; future schema changes need a reviewed migration.
