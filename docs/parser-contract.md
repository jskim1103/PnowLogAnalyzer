# Parser contract (provisional)

The first increment implements CSV decoding and explicit player references only.
PokerNow grammar stays in `app.ingestion`; `app.domain` contains source-independent
identity values. No public interface is stable yet.

## Identity

A player ID is an opaque, case-sensitive string. It is never derived from a display
name. The user reports that PokerNow IDs persist across sessions; the inspected
single-session sample cannot independently establish that property. Renames do not
change identity, and identical names do not merge different IDs. No alias inference
or automatic ID linking is performed.

An observed name belongs to a reference, not to the canonical identity. Preserve it
exactly, including Unicode, punctuation, and whitespace. Parse a complete quoted
reference by its final ` @ ` separator, allowing that separator inside the name.
Only parse references from positions established by event grammar; do not scan
arbitrary free text for identities. A malformed reference raises an explicit error.
The initial ID grammar excludes whitespace and quotation marks but does not assume
a fixed length or restrict IDs to the characters in one sample.

## Source records

Decode UTF-8 (accepting a BOM) with the standard-library CSV reader. The verified
columns are `entry`, `at`, and `order`; require those exact columns in that order
until another export version is inspected. Preserve each decoded field verbatim,
plus a SHA-256 source-file fingerprint, logical record number (first data row is 1),
and physical line span. Logical records can span multiple lines. CSV syntax and row
shape failures raise errors rather than silently skipping input. Decoding does not
classify events, validate timestamps, reorder records, or validate hands.

## Next increment

Classify player-bearing event positions and collect ordered name observations by
ID. Then add hand boundaries and explicit per-hand variants. The inspected export
contains PLO5 and NLHE, newest-first records, and dead-button headers. Action amount
normalization must distinguish chips added from resulting street commitment.
Unknown events and unattributed `Your hand is` observations must stay explicit.

## CLI import milestone

`app.ingestion.importer` will produce a typed import report, player observations,
and hand envelopes retaining every source record. These envelopes are not yet the
shared reconstructed domain `Hand`. The CLI accepts one or more overlapping
exports from **one explicitly named session**; it does not infer session identity
from filenames or file hashes. Use separate invocations for different sessions.

Merge records by numeric `order` within that session. Identical records retain all
source references; conflicting contents for an order fail the import. Preserve
source file hashes and report schema/parser version. Hand keys are the pair of
explicit session ID and observed PokerNow hand ID. No database or persistent import
state is introduced. Repeated imports produce the same result, and overlapping
files in one invocation do not duplicate hands.

Validate hand boundaries (one start and matching end, unique hand ID and number),
not poker legality. Nested starts, orphan ends, missing ends, and malformed headers
produce explicit issues. Retain records outside hands too. Parse player references
only in anchored, observed event positions and stack snapshots; malformed snapshots
are reported without discarding the original record. Group observed names by ID,
retaining source locations and chronological observations. Joined players are not
assumed to be participants; only hand stack snapshots describe participants.

CLI counts explicitly distinguish hands with valid boundaries from fully validated
poker hands. The latter remains zero until action/state/accounting validation is
implemented. JSON includes raw entries and player labels, so any redirected output
is private data. Unknown entries are retained and counted; they cannot support a
claim of full validation. `--strict` fails on import issues or unknown events.

## First statistics adapter

The user requested VPIP before full chip accounting. Introduce a small provisional
`domain.preflop` contract (starting seats/stacks, ordered typed actions, variant,
hand key, and input issues). `ingestion.preflop` translates observed PokerNow
wording into this contract; `stats.vpip` depends only on domain types. This avoids
making the mathematics engine interpret CSV entries or coupling ingestion to a
statistical formula. It is not a replacement for the future full Hand contract.

Amounts use Decimal; calls and raises preserve observed street totals. The VPIP
module checks preflop investment, roster membership, forced blind evidence,
fold/all-in state, and betting completion sufficient for metric eligibility. It
does not claim full hand legality, side-pot allocation, or payout reconciliation.
Unknown preflop records and unsupported forced posts cause explicit exclusions.
Unknown postflop events do not change a completed preflop observation, but an
invalid hand boundary still excludes the whole hand in this first version.
