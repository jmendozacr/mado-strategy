# Exploration: HTF Candle Construction — Real Timezone Anchor — SYNTHESIZED

**Triage**: L (as originally classified — see correction below). Council: architect + qa-engineer + business-analyst ran in parallel (anti-anchoring — independent reads, blind to each other), synthesized here.

## Headline: the triaged root cause is disproven

Two independent, blind, adversarial verifications (architect via the MetaQuotes weekly-boundary signature; qa-engineer via four orthogonal signals — weekly open/close, tick-volume peak, D1 Sunday-bar existence) both conclude: **MT5 broker export timestamps are plain UTC+0, no DST.** `core/kill_zone.py` and its REQ-29 docstring are correct as written. The triage's claimed root cause (broker server = UTC+3/EEST) does not hold.

QA additionally demonstrated *why* the original 2-timestamp cross-check couldn't have settled this: both timestamps shared residue class mod 4 (9am/1am → both ≡1 mod4), so the second carried ~zero independent information; both fell in June, inside both EU and US DST, unable to distinguish fixed-+3 from DST-following EEST from any of 6 offsets consistent with "lands on an H4 boundary." Simulating the proposed fix empirically: 166/193 tests still pass; of 27 failures only 3 are timezone-semantic, the other 24 are fixture collateral (accidental coupling to a magic timestamp), not evidence the clock was wrong.

## Corrected record (vs. #452 / #450 / #451)

- #452 (triage) claims avg-R improved "across all 3 instruments" under the HTF re-anchor experiment. #450 (source) says only EURUSDm was tested for that framing. The actual honest A/B (business-analyst, reading `.sdd/evidence/`): **2 of 3 improve, DXYm degrades avg R by 7.4%** (0.502→0.464). Win rate improves 3/3 but by <1.1pp each.
- The "all 3 instruments" claim that IS true is a different metric (the confluence sub-change's own pre→post non-regression gate), conflated with the backtest avg-R claim in #452.
- The motivating scratch experiment (`pairs/H4/*_UTC4aligned.csv`) uses a **fixed** offset across a 2020–2026 span that includes multiple US DST transitions — it is not NY-local under any premise, and (architect) doesn't even land on "NY midnight" as intended — it lands on a third, unintended grid (~NY 03:00) that happens to place one H4 candle inside the kill zone.

## Abstraction Ladder

**A1 — Flow**: the user's actual flow is "run backtest → read W/avg-R → decide if a rule is worth trading." The originally-chased failure mode ("every kill-zone classification since `crt-detector-killzone-filter` is wrong") does not exist. The real A1 risk, if this change proceeded as scoped, is the inverse: re-baselining three shipped changes' fixtures onto a wrong clock, invalidating currently-correct work.

**A2 — System**: `ingestion/loader.py` parses naive datetimes, no clock contract. HTF is never constructed — it's a separate `--htf-csv` MT5 export, paired (not epoch-validated) against LTF by `ingestion/pairing.py`. `core/kill_zone.py` treats the naive stamps as UTC and converts via real `America/New_York` (`zoneinfo`) rules — correctly.

**A3 — Architecture**: no aggregation capability exists anywhere in the codebase today. `ingestion` (leaf) → `core` → `alignment`/`backtest` → `cli`. `in_ny_kill_zone` is the *only* wall-clock-semantic consumer; everything else (`swing`, `fvg`, `crt_range`, `mss`, `model1`, `simulate`) is ordinal/index/duration. `cli.py` is missing from `.importlinter`'s `root_packages` — an existing, unrelated fitness-function gap.

**A4 — Code**: `core/kill_zone.py` (correct, do not touch), `ingestion/loader.py`, `ingestion/pairing.py`, `alignment/htf_ltf.py`, `backtest/simulate.py`, `tests/fixtures/synthetic.py` (highest blast-radius single artefact — one magic timestamp `_KILL_ZONE_BASE` accidentally couples 24 unrelated tests to the kill-zone window).

## What legitimately survives (convergent, architect + qa-engineer)

A **different, smaller-scoped, feature-shaped** question: should H4 aggregation follow an NY-local, DST-aware grid (since ICT/CRT session primitives — Kill Zones, "0100 am Continuation" — are taught NY-local per `docs/charter-1..5.md`), instead of the broker's fixed-UTC grid? This is NOT a bugfix — there is no existing aggregation code to fix. It needs its own triage, its own problem statement, and is blocked on a **product decision no persona can make**: which NY anchor (midnight / 17:00 session-open / kill-zone-aligned)? architect notes the true NY-local grid *shifts* across DST (04/08/12/16/20/00 UTC in EDT vs 05/09/13/17/21/01 UTC in EST) — a moving target the scratch experiment never modeled.

Separately, independent of any timezone-anchor decision, two pieces of real, small, immediately actionable value:
1. **Missing test-safety-net**: no REQ anywhere asserts the ingestion clock contract from the data itself (QA drafted REQ-CLK.1-3 sketches — positive/negative/cross-pairing). This gap is exactly what let a 2-point, information-poor cross-check nearly overturn three archived changes.
2. **Test decoupling**: 24 backtest/e2e tests are accidentally coupled to `_KILL_ZONE_BASE` sitting inside the kill zone. QA recommends decoupling them (`kill_zone_gated=False` where the subject is fill/RR/dedup mechanics) as a standalone, clock-decision-independent cleanup — shrinks any future clock-change blast radius from 27 tests to 3.

## Open Questions (blocking any propose)

1. **Product** — is the NY-local-anchored HTF aggregation actually wanted as new work, and if so which anchor (midnight / session-open 17:00 / kill-zone-aligned)? Do the charters (docs/charter-1..5.md) actually specify NY-anchored H4 candles, or is that an inference from how sessions are discussed? (business-analyst, architect, qa-engineer all flag this — none can resolve it.)
2. **Product** — `crt-detector-key-level-confluence-core` is paused on a defect that (per this exploration) doesn't exist. Its S-000 gate failed for real reasons (W=0.0266, avg R regressing) on a correct clock. Unpause and confront the original failure, or keep paused pending the (separate) HTF-aggregation feature decision?
3. **Product** — business-analyst: build H4 from M15 (loses ~2.5 years nominal history per file start dates) vs. architect's counter that this cost is "nominal, not effective" since LTF already bounds the tradeable population and HTF-before-LTF-start only fed a ~3-day CRT-range warm-up. Unresolved between personas — needs verification against how the backtest CLI actually uses pre-LTF-start history before it can inform a design.
4. **Process** — correct the over-claimed evidence in #452/#450/#451 before anything is built referencing them.

## ready_for_proposal: NO (2 of 3 personas; business-analyst conditional-yes did not independently re-verify the offset premise)

Architect and qa-engineer both recommend: **halt this change as scoped, re-triage.** The change's stated root cause is empirically false; proceeding would "fix" correct code and re-baseline three shipped changes onto a wrong clock.

## Persona reports (full detail)

- Architect: engram obs #455, topic `sdd/crt-detector-htf-timezone-anchor/explore-architect`
- QA Engineer: engram obs #456, topic `sdd/crt-detector-htf-timezone-anchor/explore-qa-lens`
- Business Analyst: engram obs #454, topic `sdd/crt-detector-htf-timezone-anchor/explore-business-analyst`
