# Excluded / Protected Artifacts

## `audit/trader-algorithm-fidelity/`

A separate, paused human-fidelity pilot (30 cases, not yet started) lives at
`audit/trader-algorithm-fidelity/`. This lab must never:

- Modify any file under that path.
- Open or alter its decision journal.
- Alter its 30-case `pilot_manifest.json`.
- Reveal which selection categories it uses.
- Report any specific case's result.
- Use any of those 30 sessions as an example of a pattern this lab finds.

This round, the only interaction with that path was confirming its existence and top-level filenames
(via the mapping explorer), which is enough to know it must be excluded — its contents were not read.

## Exclusion mechanism

This lab's event sources (`audit/2026-11-17-causal-lookahead-audit/`,
`audit/2026-11-17-eurusd-usdcad-audusd/`) are structurally independent datasets from the fidelity
pilot's 30 cases — they come from different directories, different generating scripts, and the
fidelity pilot's `pilot_manifest.json` was never read by this lab's extractor. There is therefore no
observed overlap to exclude yet.

If a future research unit needs to cross-reference timestamps/instruments and risks an accidental
overlap with the pilot's 30 selected cases, the mechanism to use is: a pure set-membership filter keyed
only on `(instrument, timestamp)` pairs supplied by the user or by a function that reads
`pilot_manifest.json` and returns **only** that opaque identity set (no category, no outcome) — never a
filter that this lab's own code derives by reading the manifest's categories or scoring itself. That
function does not exist yet because it has not been needed; documenting the intended shape here so it
is not invented ad hoc under time pressure later.

## General read-only boundary

Also read-only for this lab (per the user's explicit scope): `docs/`, `detector/`, `scanner/`, the
original D3/C2 experiment code/results, and original historical data files. This lab's own code may
*import* `detector`'s leaf modules (e.g. `ingestion.loader`) exactly as other `research/` modules in
this repo already do, but must never write into any of those paths.
