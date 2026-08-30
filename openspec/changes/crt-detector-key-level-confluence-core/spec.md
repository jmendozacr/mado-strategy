# Specs: crt-detector-key-level-confluence-core

**Spec version**: V3 | **Status**: signed (2026-08-30, human sign-off — V2 was signed, re-opened for plan-verify iteration 2 findings, V3 re-signed) | **Change**: `crt-detector-key-level-confluence-core` | **Triage**: L
**Program**: `crt-detector-key-level-confluence` (sub-change #1, walking skeleton) | **Spec source**: internal
**Engram mirror**: `sdd/crt-detector-key-level-confluence-core/spec` (identical content)

Charter-1 [00:12:02] makes reaction at an HTF Key Level a precondition of a valid Model-1 setup. The detector never implemented that check, so every Model-1 signal is reported as tradeable. This spec makes confluence a hard validity gate using the one Key Level source already in code (FVG).

> **Mechanism note (plan-verify iteration 2, informational — not a behaviour change)**: while confluence is defined as a geometric predicate (REQ-55), its real-data discrimination is driven substantially by Key Level EXPIRY state (REQ-53) — most zones eventually get touched by some later purge; whether a zone is still open (unmitigated) at purge time is what actually separates credited from non-credited signals in practice. REQ-60.2's evidence requirement exists precisely to keep this measured, not assumed.

Two domains: NEW `key-level-confluence` (REQ-53..REQ-60) and a DELTA against `openspec/specs/detector/spec.md` V5 modifying REQ-30, REQ-40, REQ-45, REQ-46.

**REQ-ID allocation**: highest existing main-spec ID is REQ-52. V1 took REQ-53..REQ-57; V2 added REQ-58..REQ-60. V3 adds no new REQ-ID — every fix is a scenario or prose correction inside an already-admitted requirement (REQ-53, REQ-55, REQ-59, REQ-60, REQ-40).

> **V3 basis**: applies the resolved findings of `sdd/crt-detector-key-level-confluence-core/verify-plan-2` — both-sides tiebreak rewritten (finding #1, user decision), granularity/framing wording corrected (findings #2/#3), REQ-55.11/REQ-53 expiry-boundary collision fixed (finding #4), consumer-coupling and ≥50-trades floor given explicit scenarios (finding #5), REQ-40.2 decoupled from `detections.csv` row counts (finding #9), REQ-59.2 scoped to signals confluence actually evaluates (finding #10), REQ-60.2's denominator made explicit (finding #7), and a new REQ-60.4 halt-on-performance-regression criterion (user decision, finding #13). Finding #6 (REQ-46 coverage) and finding #8/#11 (fixture design, baseline capture) are design/slice-layer fixes, not spec changes — routed to `sdd-design` V3 / `sdd-slice` V3.

---

## Domain: key-level-confluence (NEW — REQ-53 through REQ-60)

### REQ-53: Normalised Key Level shape, FVG source adapter, and expiry on mitigation
The system MUST expose a single normalised `KeyLevel` shape carrying at minimum: `kind` (source tag), the price zone as `top`/`bottom`, `origin_index` (REQ-54), and an **expiry index** — the index from which the level ceases to be a valid Key Level, absent when it never expires. The system MUST expose an adapter presenting a detected FVG as a `KeyLevel` whose `top`/`bottom` are that FVG's own `top`/`bottom`. Confluence consumers MUST depend only on this normalised shape, never on a source detector's own type.

A Key Level sourced from an FVG MUST expire when that FVG is mitigated (filled). The adapter MUST derive the expiry index from the FVG's fill outcome: set to the fill index when filled, absent when open. An expired Key Level MUST NOT be credited to a purge STRICTLY AFTER its expiry index, and MUST still be credited to a purge AT OR BEFORE it — expiry is a point in time, not a retroactive deletion, and the expiry index itself remains creditable: the candle that fills a level can be the very candle that reacts at it.

> **Reversal of a signed V1 decision (verify-plan-1 finding #1)**: V1 required the opposite ("MUST NOT expire on mitigation"; adapter forbidden from reading fill state). A blind judge ran V1's rule against real `pairs/` H4/M15 data and measured the gate withholding only **2.8%** of signals: unexpiring filled zones accumulated to ~**9×** the instrument's price range, so almost every purge wick landed inside some zone. The user reversed the decision on that evidence. Most consequential change in V2.

> **Boundary correction (V3, verify-plan-2 finding #4)**: V2 excluded a purge "at or after" the expiry index — inclusive of the expiry index itself, mirroring REQ-54.4's origin-side boundary. A blind judge found this denies credit to the single strongest-confluence case: a purge candle that BOTH reacts at AND fills the same FVG in one motion (~0.2% of signals) — the very candle doing the filling is excluded from crediting the reaction it just caused. V3 corrects the boundary to exclude only purges strictly after expiry; the fill candle itself stays creditable. This is deliberately asymmetric with the origin boundary (REQ-54.4 unchanged) — origin and expiry answer different questions (was this level knowable yet? vs. is this level still open?) and there is no requirement they share the same edge treatment.

*Rationale — reading fill state is not lookahead*: the credit predicate uses the fill index only as `purge_index > expiry_index`, exactly equivalent to "had this level been filled strictly before this purge?" — a question about the past, answerable at the purge candle. REQ-54.5 pins this.

- **REQ-53.1** (happy): GIVEN a bullish FVG `top=1.1050`, `bottom=1.1030`, WHEN presented as a `KeyLevel`, THEN its zone is exactly `[1.1030, 1.1050]` and `kind` identifies FVG as the source.
- **REQ-53.2** (alternate — mitigation sets an expiry): GIVEN two FVGs identical except one `open` and one `filled` with fill index `120`, WHEN both are presented as `KeyLevel`s, THEN the filled one's expiry index is `120` and the open one's is absent; otherwise equal in every field including `origin_index`.
- **REQ-53.3** (edge): GIVEN an HTF series with no FVG detected, WHEN Key Levels are collected, THEN an empty collection is returned — not an error, not a null.
- **REQ-53.4** (structural, NEW — consumer-coupling, verify-plan-2 finding #5): GIVEN `alignment/htf_ltf.py`'s own import statements, WHEN inspected, THEN it imports only `core.key_level`, never `primitives.fvg` or any other detector module directly — confluence consumers see the normalised shape only, never a source detector's own type.

### REQ-54: A Key Level is knowable only from the candle that completes it
The system MUST set `origin_index` to the index at which the level first becomes provably knowable from the series alone — for FVG, the third candle of the formation (`end_index` = `start_index + 2`), NEVER the geometric start index. A Key Level MUST NOT be credited to any signal whose triggering event precedes `origin_index`. Neither formation nor expiry (REQ-53) may depend on data unavailable at the crediting purge candle.
*Rationale*: an FVG's geometry reads `candles[i]` and `candles[i+2]`; at index `i` the gap does not yet exist.
- **REQ-54.1** (happy): GIVEN an FVG from candles 40, 41, 42, WHEN its `KeyLevel` is produced, THEN `origin_index` is 42.
- **REQ-54.2** (boundary — present at knowability): GIVEN a `KeyLevel` with `origin_index = n`, WHEN re-derived from the series truncated to its first `n + 1` candles, THEN that same `KeyLevel` is present.
- **REQ-54.3** (boundary — absent before): GIVEN the same `KeyLevel`, WHEN re-derived from the first `n` candles, THEN it is absent.
- **REQ-54.4** (error — no credit from the future): GIVEN a signal whose HTF purge candle sits at index `p`, and a Key Level with `origin_index >= p`, WHEN confluence is determined, THEN that Key Level MUST NOT be credited. Both indices on the HTF series.
- **REQ-54.5** (boundary, NEW — expiry is lookahead-safe): GIVEN a purge at HTF index `p` and the Key Level credited to it from the full series, WHEN Key Levels are re-derived from the first `p + 1` candles and that purge is re-evaluated, THEN the SAME Key Level is credited; and a level not credited at `p` on the full series is not credited on the truncation either.

### REQ-55: Confluence — the HTF purge must react at a Key Level
The system MUST determine, for every Model-1 signal tagged `aligned` (REQ-05), whether its HTF purge candle reacted at a Key Level, and MUST record the crediting `KeyLevel` (or its absence).

> **Granularity note (V3, verify-plan-2 finding #3 — wording correction, no behavioural change)**: confluence is determined once per HTF purge candle, not once per Model-1 signal. Every LTF Model-1 signal `aligned` to the same HTF purge candle inherits that candle's confluence outcome — REQ-05's alignment tagging can map one HTF purge candle to several LTF signals, and REQ-59 makes the single per-candle determination binding on every consumer. V2's wording implied per-signal precision; this was never the mechanism, only the phrasing.

**Which wick extreme(s) are credited.** The credited extreme(s) are the extreme(s) on the side(s) of the HTF CRT range the purge candle actually breached — the breach(es) that made it the purge candle. WHERE the purge candle's `high` exceeds the CRT range's `high`, the `high` is a credited extreme; WHERE the purge candle's `low` falls below the CRT range's `low`, the `low` is a credited extreme. A purge candle breaching only one side has exactly one credited extreme; a purge candle breaching both sides has two. Determined from the HTF purge candle and its HTF CRT range alone; MUST NOT be derived from the Model-1 signal's own `direction` field.

> **Correction of V1 (finding #3, found independently by both blind judges)**: V1 said "`high` for a bullish purge, `low` for a bearish purge" — **inverted**. A Model-1 `direction` is the direction of the trade the purge sets up, the OPPOSITE of the breached side: a high-side breach produces a `bearish` signal. A rule reading `direction` credits the wrong wick on every signal. REQ-55.7 exists to fail such an implementation.

**Both sides breached in one candle.** WHERE the purge candle breaches BOTH sides, BOTH the `high` and the `low` are evaluated as credited extremes independently; confluence holds if EITHER extreme falls inside a valid Key Level's zone. Not rare (measured: **14.1%** of real H4 purges).

> **Correction of V2 (V3, verify-plan-2 finding #1, user decision)**: V2 resolved a both-sides breach by always crediting the `high` alone, discarding the `low` extreme's own Key Level eligibility entirely. A blind judge found this arbitrary — it flips **5.4%** of signal verdicts relative to evaluating both sides on their own merits. V3 evaluates both extremes independently; confluence holds if either qualifies. REQ-55.6 rewritten; REQ-55.13 added to demonstrate the corrected case (low-side-only match, which V2's rule wrongly failed).

**When confluence holds.** ANY credited extreme falls inside a Key Level's `[bottom, top]` zone, inclusive of both edges, AND the level is neither un-knowable (REQ-54.4) nor expired (REQ-53) at the purge index. NO tolerance, proximity or near-miss allowance. WHERE more than one level qualifies — whether from the same extreme or across both extremes of a both-sides breach — the LOWEST `origin_index` MUST be credited.

**When not determinable.** For `unaligned` or `insufficient_htf_data` there is no HTF purge candle; the system MUST record absence rather than a negative determination.

- **REQ-55.1** (happy, high-side breach): GIVEN an `aligned` signal whose HTF purge candle breached its CRT range's `high` and has `high = 1.1040`, and an unexpired Key Level `[1.1030, 1.1050]` with an earlier `origin_index`, WHEN confluence is determined, THEN that Key Level is recorded — notwithstanding the signal's `direction` being `bearish`.
- **REQ-55.2** (happy, low-side breach): GIVEN an `aligned` signal whose purge breached the CRT `low` with `low = 1.0965`, and an unexpired Key Level `[1.0960, 1.0975]` with an earlier `origin_index`, THEN that Key Level is recorded — notwithstanding `direction` being `bullish`.
- **REQ-55.3** (alternate — no tolerance): GIVEN a credited extreme of `1.1029` and a Key Level `[1.1030, 1.1050]`, THEN NO Key Level is recorded.
- **REQ-55.4** (edge — boundary counts): GIVEN a credited extreme equal to the level's `bottom` exactly, THEN that Key Level IS recorded.
- **REQ-55.5** (error — undeterminable, not negative): GIVEN `unaligned` or `insufficient_htf_data`, THEN no Key Level is recorded AND the signal is NOT treated as having failed confluence (see REQ-40.5, REQ-56.3).
- **REQ-55.6** (edge, REWRITTEN V3 — both sides breached, each evaluated independently): GIVEN a purge candle whose `high` exceeds its CRT `high` AND whose `low` falls below its CRT `low`, and two unexpired Key Levels — one containing the `high`, the other the `low`, neither both — THEN BOTH levels are eligible and confluence holds; the level with the LOWER `origin_index` is recorded (REQ-55.12's earliest-wins rule applies across both extremes, not just one).
- **REQ-55.7** (error, NEW — `direction` is not the rule): GIVEN an `aligned` signal whose purge breached the CRT `high` only, and whose `direction` is therefore `bearish`, and a single unexpired Key Level containing that candle's `low` but NOT its `high`, THEN NO Key Level is recorded — the `low` was never breached, so it is not a credited extreme; an implementation selecting the wick by `direction` would wrongly credit it. This scenario MUST fail such an implementation.
- **REQ-55.8** (happy, NEW — unfilled level counts): GIVEN an HTF purge at index 80 and an FVG-sourced Key Level `origin_index = 42`, no expiry, whose zone contains the credited extreme, THEN that Key Level is recorded.
- **REQ-55.9** (error, NEW — expired level does not count): same, but expiry index `60`, THEN NO Key Level is recorded.
- **REQ-55.10** (alternate, NEW — valid until it expires): same, but expiry index `90`, THEN that Key Level IS recorded.
- **REQ-55.11** (boundary, CORRECTED V3 — the expiry index itself): same, but expiry index exactly `80` (the purge candle IS the fill candle), THEN the Key Level IS recorded — expiry excludes only purge indices strictly after its own index (REQ-53's V3 boundary correction); the candle that fills a level is still credited for reacting at it.
- **REQ-55.12** (alternate, NEW — earliest qualifying level wins): GIVEN two unexpired levels both containing the credited extreme, `origin_index` 42 and 55, both earlier than the purge, THEN the one with `origin_index = 42` is recorded.
- **REQ-55.13** (alternate, NEW V3 — both sides breached, only the low-side extreme qualifies): GIVEN a purge candle breaching both sides, an unexpired Key Level containing the `low` but no unexpired Key Level containing the `high`, THEN confluence holds and the low-side level is recorded. (Demonstrates the case V2's high-always rule wrongly failed — see REQ-55.6.)

### REQ-56: Confluence is a validity gate on reported detections
The system MUST withhold from `detections.csv` and `overlay.png` every Model-1 detection for which confluence was DETERMINABLE and came back negative. A detection is withheld **if and only if**: it is tagged `aligned`; its confirmation type is NOT `fvg_fill`; and no Key Level was recorded. Equivalently, KEPT when not `aligned`, OR confirmation type is `fvg_fill`, OR a Key Level is recorded.

**Why `fvg_fill` signals are outside this gate (finding #18, user-resolved).** An `fvg_fill`-confirmed signal has no CRT range, therefore no HTF purge candle and no confluence determination to make; `--backtest` already reports it under `excluded_no_crt_range` (REQ-30.4). Withholding it here too would merge two distinct rejection reasons into one silent removal, leaving a reader unable to tell WHY a row disappeared. Each signal keeps its own single exclusion reason.

The gate MUST be surgical. Detections tagged `unaligned`/`insufficient_htf_data`, every `fvg_fill`-confirmed detection, and every non-Model-1 row MUST appear exactly as they would with the gate absent. Applies to every run, with or without `--backtest`. Column contract unchanged: no column added, removed or reordered; the crediting level's source is NOT surfaced as a column in this change.

- **REQ-56.1** (happy): GIVEN an `aligned` signal with a Key Level recorded, WHEN `detections.csv` is written, THEN its row is present.
- **REQ-56.2** (happy — the gate bites): GIVEN an `aligned`, non-`fvg_fill` signal with no Key Level recorded, THEN no row and no marker appears in either artefact.
- **REQ-56.3** (alternate — surgical, differential anchor): GIVEN two runs of the CURRENT code over a minimal input pair identical EXCEPT whether the HTF Key Level zone contains the purge candle's credited wick extreme, WHEN both `detections.csv` files are compared, THEN every `unaligned` row, every `insufficient_htf_data` row, every `fvg_fill`-confirmed row and every non-Model-1 row is byte-for-byte identical — the files differ ONLY in the presence of the `aligned` Model-1 rows the gate withholds.
  > (Previously anchored ABSOLUTELY, to "same count and same bytes as a run of the same input before this change" — permanently unreproducible once this ships, the exact trap ADR-016 removed from REQ-45. Re-anchored differentially. Finding #17.)
- **REQ-56.4** (alternate — non-Model-1 untouched): GIVEN Swing, FVG, CRT range and MSS rows, THEN none is withheld.
- **REQ-56.5** (edge — header contract): GIVEN a run WITHOUT `--backtest`, THEN `detections.csv`'s header is byte-identical to the 7-column header of REQ-24/REQ-41.3.
- **REQ-56.6** (edge — single-series): GIVEN no HTF pair supplied, THEN no detection is withheld — no signal is tagged `aligned`, so confluence is never determinable.
- **REQ-56.7** (alternate, NEW — `fvg_fill` untouched by the gate): GIVEN an `aligned` detection whose confirmation type is `fvg_fill`, with no Key Level ever recorded (no CRT range, no purge candle), THEN its row and marker both appear — the gate does not withhold it, and its exclusion from the tradeable population stays attributed to `excluded_no_crt_range` alone.

### REQ-57: HTF Key Level sources are computed, not rendered
The system MUST compute Key Level sources on the HTF series whenever an HTF pair is supplied, so REQ-55 has levels to evaluate. This MUST NOT change any rendered or reported artefact: HTF-sourced FVGs MUST NOT be drawn on `overlay.png`, MUST NOT appear as rows in `detections.csv`, and MUST NOT change the meaning of `--types fvg` (LTF FVG detections only).
- **REQ-57.1** (happy): GIVEN an HTF pair supplied, THEN Key Levels are available from the HTF series for REQ-55.
- **REQ-57.2** (alternate): GIVEN an HTF series containing FVGs, THEN no HTF FVG is drawn on `overlay.png`.
- **REQ-57.3** (edge): GIVEN `--types fvg`, THEN `detections.csv` contains exactly the LTF FVG rows an equivalent run produced before this change.

### REQ-58: HTF Key Levels are never held on the run's detections record (NEW)
The system MUST keep HTF-derived Key Levels out of the run's detections record — the structure `--from-date`, `--to-date`, `--session` and `--types` narrow. Key Levels MUST be computed, consumed by REQ-55, and discarded; they MUST NOT be a field of that record.
*Rationale*: every field of that record is swept by the results-narrowing filters. Were Key Levels a field, `--from-date` or `--session` would narrow the pool available to REQ-55 and thereby change which signals are **valid** — a display filter inverting into a validity filter. REQ-57 asserts the observable consequences; this REQ asserts the structural constraint that makes them hold **by construction** rather than by exclusions a future edit could forget. (Finding #5; design ADR-014.)
- **REQ-58.1** (structural): GIVEN the detections record of a paired run, WHEN its fields are enumerated, THEN none holds Key Levels or HTF-derived FVGs.
- **REQ-58.2** (happy — validity independent of `--from-date`): GIVEN a paired run and the same run with `--from-date` set later than the earliest Key Level's `origin_index` timestamp, THEN every Model-1 detection present in both windows has the SAME confluence outcome.
- **REQ-58.3** (happy — validity independent of `--session`): GIVEN a paired run and the same run with `--session ny-killzone`, THEN every Model-1 detection surviving the session filter has the same confluence outcome as unfiltered.

### REQ-59: Confluence is determined once and read, never recomputed (NEW)
The system MUST determine each signal's confluence outcome exactly once and record it on that signal. Every consumer — the reported-detections gate (REQ-56) and the `excluded_no_key_level` population cut (REQ-30.7, REQ-40) — MUST read that single recorded outcome. No consumer MAY recompute confluence independently.
*Rationale*: two independent computations of the same predicate can drift apart with no test noticing — the exact failure class this project already shipped and fixed once, in the `--types` population-snapshot defect of the prior archived change. Also makes REQ-42.1's trades↔detections join hold by construction. (Finding #5; design §1 and ADR-014.)
- **REQ-59.1** (happy — consumers agree by construction): GIVEN any `--backtest` run, WHEN `trades.csv` and `detections.csv` are compared, THEN every traded `signal_id` appears as a Model-1 row in `detections.csv`.
- **REQ-59.2** (error — divergence impossible, not merely unlikely, SCOPED V3 to signals confluence actually evaluates): GIVEN two otherwise-identical runs differing ONLY in whether one signal's recorded confluence outcome is present, AND that signal is `aligned`, non-`fvg_fill`, and otherwise eligible to reach the confluence check (i.e., not excluded by an earlier cut), THEN that signal's presence in `detections.csv` and its membership in `excluded_no_key_level` change TOGETHER — never one without the other. Signals excluded by an earlier cut (`excluded_unaligned`, `excluded_never_confirmed`, `excluded_no_crt_range`) never reach the confluence check at all (REQ-30's precedence, REQ-40.5); their `detections.csv` presence and bucket membership are governed by that earlier requirement instead and are unaffected by confluence outcome.
  > (Scoped, V3, verify-plan-2 finding #10: V2's wording made a universal claim that is false for signals an earlier cut already disposed of — changing their confluence outcome changes nothing about them, since they never reach REQ-56/REQ-30.7 at all. Narrowed to the signals the claim actually holds for.)

### REQ-60: H4/M15 is the reference pairing for real-data validation (NEW)
The confluence gate's real-data behaviour MUST be validated on an H4 (HTF) / M15 (LTF) instrument pair, and that run's evidence MUST record: the number of `aligned` Model-1 signals, how many were credited a Key Level, how many were not, the resulting `excluded_no_key_level` count, the resulting `trades_opened` count, and the Model-1 row count in `detections.csv` before and after the gate. H4/M15 is the pairing this change is specified against; other pairings are informative but do not discharge this requirement. (Finding #5 — in scope from the start, previously carrying only an implicit slice acceptance line.)
- **REQ-60.1** (happy): GIVEN a real H4/M15 pair, WHEN the detector runs with `--backtest`, THEN the recorded evidence contains all six counts above.
- **REQ-60.2** (error — the gate must discriminate, denominator made explicit V3): GIVEN that evidence, WHEN the proportion of ALL `aligned`, non-`fvg_fill` signals withheld for lack of a Key Level is computed — using as denominator every `aligned`, non-`fvg_fill` signal admitted to `signals_considered` (REQ-40), REGARDLESS of whether it would also be excluded by a later cut such as `excluded_never_confirmed` — THEN that proportion MUST be materially greater than zero and materially less than 100%. V1's rule measured 2.8% on this denominator, which forced the REQ-53 reversal; a gate withholding everything leaves nothing to trade. The concrete numeric bound is set as an acceptance criterion at design time (finding #2, routed to `sdd-design`).
  > (Clarified, V3, verify-plan-2 finding #7 — CRITICAL: the denominator was previously inferable only from the design layer, which left room to read it as the SUBSET remaining after the `excluded_never_confirmed` cut. Under that reading, the numeric band set at design time was mathematically UNREACHABLE — a walking skeleton whose own halt-gate criterion cannot be satisfied cannot execute. This spec now fixes the denominator explicitly as the full `aligned`, non-`fvg_fill` population, matching the empirical methodology already used to justify the REQ-53 reversal.)
- **REQ-60.3** (error, NEW V3 — minimum sample floor, verify-plan-2 finding #5): GIVEN that evidence, WHEN `trades_opened` is inspected, THEN it MUST be at least 50 — the floor below which the steward's reckoning treats the surviving sample as statistically inconclusive (CQ2, `sdd/crt-detector-key-level-confluence-core/north-star`), a hard outcome-gap rather than a soft note.
- **REQ-60.4** (error, NEW V3 — halt on performance regression, user decision): GIVEN the H4/M15 evidence run's post-gate backtest performance (net R, `metrics_summary`), WHEN compared against the pre-gate baseline captured before this change existed (`sdd/crt-detector-key-level-confluence-core/pre-gate-baseline`), IF post-gate performance is WORSE than the pre-gate baseline, THEN the walking skeleton (S-000) MUST HALT and require explicit human confirmation before any further slice (S-001 onward) proceeds — even when REQ-60.2's discrimination band and REQ-60.3's trade-count floor are both satisfied. A gate that discriminates enough and still leaves the strategy worse off is not, by itself, evidence the gate is correctly built.

---

## Domain: detector (DELTA against `openspec/specs/detector/spec.md` V5)

### ADDED Requirements
None. REQ-53..REQ-60 constitute the new `key-level-confluence` domain, ADDED to the main spec as that domain at archive time.

### MODIFIED Requirements

> **MODIFIED-block completeness note (for `sdd-archive` §4)**: each block reproduces the FULL current text — description and every scenario — then applies the change. Scenario counts vs V5: REQ-30 6→7, REQ-40 4→6, REQ-45 3→3, REQ-46 2→2. No scenario dropped.

#### REQ-30: Tradeable candidate population selection
The system MUST select as a trade CANDIDATE (subject to fill simulation, REQ-50) every `AlignedSignal` whose `aligned == "aligned"` AND which has a Key Level recorded (REQ-55) AND whose `ltf_signal` is eligible to be entered: `status == CONFIRMED`, `status == INVALIDATED` with `retest_index` not `None`, OR `status == PENDING` with `retest_index` not `None`. The system MUST NOT select any signal whose `retest_index is None` — regardless of status — nor `fvg_fill`-confirmed signals (no CRT range at all), nor `unaligned`/`insufficient_htf_data` signals, nor signals for which confluence was determinable and negative, as candidates. All three eligible candidate types share the same fill-timing mechanism (REQ-50): the fill-window search is `[retest_index, retest_index + max_fill_wait]` for all of them.

The exclusion cuts are evaluated in the fixed precedence order of REQ-40, earliest match winning, so a signal excluded for an earlier reason is never attributed to a later one. In particular, an `fvg_fill`-confirmed signal is attributed to "no CRT range" and never reaches the confluence cut — which keeps this requirement consistent with REQ-56.7's decision to leave `fvg_fill` signals outside the reported-detections gate.

(Previously: candidate selection required only `aligned == "aligned"` plus entry eligibility; a confluence conjunct is added and REQ-30.7 covers its exclusion. REQ-30.3's cross-reference to REQ-40 is re-anchored from a positional ordinal to the bucket's name — see the ordinal note under REQ-40. V2 adds the precedence paragraph making the `fvg_fill` ↔ confluence interaction explicit; no behavioural change — the ordering it states is the one REQ-40 already fixes.)
- **REQ-30.1** (happy): GIVEN an `aligned` CONFIRMED signal, WHEN the candidate population is built, THEN it becomes a trade candidate, subject to REQ-50's unified fill-window search starting at `retest_index`.
- **REQ-30.2** (edge): GIVEN an `aligned` INVALIDATED signal with `retest_index` set, WHEN the candidate population is built, THEN it becomes a trade candidate subject to REQ-50's SAME unified fill-window search starting at `retest_index`. Some INVALIDATED+retest candidates correctly fail to fill within the window and land in `excluded_never_filled` instead of being forced into a loss (see REQ-50.4).
- **REQ-30.3** (edge): GIVEN a signal with `retest_index is None`, regardless of status, WHEN the candidate population is built, THEN no candidate is created; counted under `excluded_never_confirmed` (REQ-40).
- **REQ-30.4** (edge): GIVEN a CONFIRMED `fvg_fill` signal, WHEN the candidate population is built, THEN no candidate is created; counted under `excluded_no_crt_range` (REQ-40) — never under `excluded_no_key_level`, whatever its confluence outcome, because the earlier cut wins.
- **REQ-30.5** (edge): GIVEN a CONFIRMED signal tagged `unaligned` or `insufficient_htf_data`, WHEN the candidate population is built, THEN no candidate is created; counted under "unaligned" (REQ-40).
- **REQ-30.6** (edge): GIVEN an `aligned` PENDING signal with `retest_index` set (entry touched, confirmation never resolved within `max_retest_lookback`), WHEN the candidate population is built, THEN it becomes a trade candidate subject to REQ-50's same unified fill-window search starting at `retest_index` — mirroring REQ-30.2. Closes a survivorship-bias gap: excluding these entirely would silently drop exactly the setups most likely to resolve as losses or opens.
- **REQ-30.7** (edge, NEW): GIVEN an `aligned` CONFIRMED signal with `retest_index` set but no Key Level recorded, WHEN the candidate population is built, THEN no candidate is created; counted under `excluded_no_key_level` (REQ-40). The methodology does not recognise it as a setup, so it MUST NOT contribute to any reported metric.

#### REQ-40: Population-reconciliation report
The system MUST report, for every `--backtest` run, a `ReconciliationReport` whose `signals_considered` count is measured over the population that survives the CLI's results-narrowing filters — `--from-date`, `--to-date`, `--session`, and `--types` where it excludes Model-1/alignment from the run entirely — and BEFORE the confluence validity gate of REQ-56 has narrowed the reported artefacts. The confluence gate MUST NOT reduce `signals_considered`: a signal it withholds from `detections.csv` MUST still be admitted to `signals_considered` and land in `excluded_no_key_level`, so that bucket is a live, countable disclosure rather than a structurally-zero one. `signals_considered` MUST NOT be derived by counting Model-1 rows in `detections.csv` — REQ-56's validity gate can make that count smaller than `signals_considered` (REQ-40.6), so the two are measured independently and are never asserted equal to each other.

Every signal admitted to `signals_considered` MUST land in EXACTLY ONE of `trades_opened` or eight exclusion buckets — `excluded_no_crt_range`, `excluded_unaligned`, `excluded_never_confirmed`, `excluded_no_key_level`, `excluded_duplicate`, `excluded_kill_zone`, `excluded_rr_floor`, `excluded_never_filled` — evaluated in that fixed precedence order, earliest match winning. `excluded_no_key_level` is the population-cuts stage evaluated immediately after `excluded_never_confirmed` and immediately before `excluded_duplicate`. `metrics_summary` MUST disclose every bucket, including `excluded_no_key_level`, as its own line.

(Previously: seven exclusion buckets, and `signals_considered` described as "measured strictly AFTER the full CLI filter chain has already run". Two changes. First, `excluded_no_key_level` is added between `excluded_never_confirmed` and `excluded_duplicate`; REQ-40.1's sum invariant now closes over eight, and REQ-40.5 covers the unaligned-and-non-confluent precedence case. Second, the "strictly after the full CLI filter chain" clause contradicted the confluence gate's actual placement — the gate is part of the CLI's chain but deliberately runs AFTER the population is counted, precisely so the new bucket is not always zero. The clause is restated to name which filters precede the count and to make the gate's exclusion from it a stated requirement rather than an accident; REQ-40.6 pins it. Finding #4. V3 adds the explicit decoupling sentence to REQ-40's description and REQ-40.2 — verify-plan-2 finding #9: a shipped test asserted `signals_considered == {count of Model-1 rows in detections.csv}`, true only when the gate withholds nothing; the assertion must re-derive `signals_considered` from the results-filtered raw population directly, never from `detections.csv`.)

> **Ordinal note (deliberate, load-bearing)**: this requirement and its dependants identify exclusion buckets by NAME, never by a positional "stage N" ordinal. Inserting a bucket mid-chain silently invalidates every ordinal downstream — REQ-46's `excluded_duplicate` was "stage 4" under V5 and would become "stage 5" here. Naming removes the failure class rather than renumbering it once. `excluded_no_key_level` MUST NOT be labelled "stage 4"; that ordinal already denoted `excluded_duplicate` in V5.

- **REQ-40.1** (edge, invariant): GIVEN any `--backtest` run, WHEN the reconciliation report is generated, THEN `trades_opened + sum(all 8 exclusion buckets) == signals_considered`, exactly.
- **REQ-40.2** (grounded, e2e — decoupled from `detections.csv` row counts, CORRECTED V3): GIVEN a session filter narrows the population, WHEN `--backtest` runs, THEN `signals_considered` reflects the post-results-filter count, not the raw detected count, and MUST NOT be derived by counting Model-1 rows in `detections.csv` — measured independently, never asserted equal against a `detections.csv` row count.
- **REQ-40.3** (edge, precedence): GIVEN a signal that is BOTH unaligned AND anchored outside the kill zone, WHEN reconciled, THEN it lands in `excluded_unaligned`, never `excluded_kill_zone`.
- **REQ-40.4** (edge): GIVEN a `PENDING` signal whose `retest_index` is set, WHEN the candidate population is built, THEN it is admitted as a REQ-30.6 candidate — never silently dropped — and resolves through the `excluded_no_key_level`, `excluded_duplicate`, `excluded_kill_zone`, `excluded_rr_floor` and `excluded_never_filled` cuts, landing in `trades_opened` or one of those five buckets.
- **REQ-40.5** (edge, precedence, NEW): GIVEN a signal that is BOTH `unaligned` AND has no Key Level recorded, WHEN reconciled, THEN it lands in `excluded_unaligned`, never `excluded_no_key_level` — the earlier bucket wins, mirroring REQ-40.3. Confluence was never determinable for it (REQ-55.5), so attributing it to the confluence bucket would misreport why it was rejected.
- **REQ-40.6** (edge, NEW — the gate does not shrink the count): GIVEN a `--backtest` run in which at least one `aligned`, non-`fvg_fill` Model-1 signal has no Key Level recorded, WHEN the reconciliation report is generated, THEN every such signal is counted once in `signals_considered` and once in `excluded_no_key_level` — the confluence gate having withheld its row from `detections.csv` MUST NOT remove it from either count, and `excluded_no_key_level` MUST be non-zero for that run.

#### REQ-45: `--backtest` flag and trades.csv contract
The system MUST accept a `--backtest` boolean flag, composable with the existing `--from-date`/`--to-date`/`--session`/`--types` filter chain. WHEN `--backtest` is supplied, the system MUST write `trades.csv` with exactly these 13 columns in this order: `signal_id, anchor_timestamp, entry_timestamp, direction, entry_price, stop_loss, take_profit, exit_timestamp, exit_price, outcome, r_multiple, ambiguous_bar, gap_filled`. WHEN `--backtest` is supplied, `detections.csv` gains a trailing `signal_id` column (REQ-41) and no other change; `overlay.png` is unaffected. WHEN `--backtest` is NOT supplied, the system MUST produce `detections.csv` and `overlay.png` byte-for-byte identical to those of the equivalent run differing ONLY by the `--backtest` flag, except for the trailing `signal_id` column that `--backtest` adds to `detections.csv` — no other carve-out applies.

(Previously: the non-backtest guarantee was anchored ABSOLUTELY, to "today's exact byte-for-byte output". REQ-56's validity gate runs on every run, backtest or not, so the pre-feature absolute baseline is permanently unreproducible and the guarantee as written would be unverifiable forever. The anchor is re-based DIFFERENTIALLY — against the equivalent run differing only by `--backtest` — the promise that actually still holds and stays testable for the life of the project. This STRENGTHENS the requirement: it remains verifiable after any future change to the detection population, whereas the absolute anchor decays on every such change.)
- **REQ-45.1** (happy, regression): GIVEN `--session ny-killzone --backtest`, WHEN the run completes, THEN trades are filtered accordingly AND `overlay.png` is byte-identical to an equivalent non-backtest run.
- **REQ-45.2** (edge, contract): GIVEN any `--backtest` run producing at least one trade, WHEN `trades.csv` is inspected, THEN its header is exactly the 13 columns above in that order, and `entry_timestamp` is the timestamp of the candle at `fill_index` (REQ-50).
- **REQ-45.3** (edge, differential byte-for-byte): GIVEN a detector run WITHOUT `--backtest` and an otherwise-identical run WITH `--backtest` over the same input and filters, WHEN both runs' `detections.csv` and `overlay.png` are compared, THEN `overlay.png` is byte-for-byte identical between them, and `detections.csv` is byte-for-byte identical apart from the trailing `signal_id` column present only in the `--backtest` run — the non-backtest run having no `signal_id` column and matching the 7-column header exactly.

#### REQ-46: Signal deduplication
Before simulation, the system MUST collapse candidates sharing an identical `(anchor_index, direction, entry_price, entry_type)` tuple into ONE trade candidate — the one with the LOWEST `origin_index` survives; the rest are counted under `excluded_duplicate` (REQ-40). Deduplication MUST run BEFORE the kill-zone and R:R-floor cuts.

(Previously: cited the `excluded_duplicate` bucket by the positional ordinal "REQ-40, stage 4". Inserting `excluded_no_key_level` ahead of it makes that ordinal false. Corrected to name the bucket — no behavioural change whatsoever. This block exists ONLY to keep a cross-reference truthful.)
- **REQ-46.1** (happy): GIVEN 3 candidates sharing an identical identity tuple, WHEN deduplicated, THEN exactly 1 trade candidate survives (lowest `origin_index`) and 2 are counted under `excluded_duplicate`.
- **REQ-46.2** (edge): GIVEN two candidates sharing the same `anchor_index`/`entry_price` but with DIFFERENT `entry_type`, WHEN deduplicated, THEN both survive as distinct candidates.

### REMOVED Requirements
None.

---

## Explicitly Out of Scope (deferred — no REQ-ID created)

| Deferred item | Reason |
|---|---|
| Swing as a Key Level source | User deferred explicitly to a later sub-change. |
| ICTOrderBlock as a Key Level source | Program sub-change #2, plugs into REQ-53's normalised shape. |
| Breaker Block as a Key Level source | Program sub-change #3, same seam. |
| Rejection Block | No definitional source in the charters; stays at `project/pending-changes`. |
| Key Level source-attribution column in `detections.csv` | Deferred to sub-change #2. 7-column header stays signed; REQ-24/REQ-41.3 NOT touched. |
| Any confluence tolerance / proximity parameter | Rejected on the merits — see REQ-55.3. |
| Rendering HTF Key Levels, or any `--types` semantic change | Explicitly excluded by REQ-57/REQ-58. |
| A confluent/non-confluent reporting partition or parallel metrics split | Rejected: confluence is a validity gate, not a report dimension. |
| Configurable expiry policy (time-decay, partial mitigation, re-test of a filled zone) | NEW in V2. Full mitigation is the only expiry rule specified. YAGNI until real-data evidence asks for more. |
| Applying the confluence gate to `fvg_fill`-confirmed signals | NEW in V2. Rejected on the merits (REQ-56.7): each signal keeps its own single exclusion reason. |
| `--types model1` disclosure note when the gate silently withholds rows | NEW in V3 — user decision: the gate applies uniformly regardless of flags; no flag-specific note needed. |

## Requirements NOT Modified (verified against V5)

| REQ | Why untouched |
|---|---|
| REQ-24, REQ-41.3 | 7-column header unchanged — source attribution deferred. REQ-56.5 asserts this. |
| REQ-17 | Gate is strictly downstream of Model-1 detection; `entries/model1.py` unchanged. Its `direction` semantics are READ correctly by REQ-55, not changed. |
| REQ-42 / REQ-42.1 | Join still holds by construction under gating — now asserted as REQ-59.1. |
| REQ-05 | Alignment tagging unchanged; confluence is determined downstream. |

## Sensitive Areas Coverage
None. Main spec's own coverage is "None"; this change reads MT5 CSV exports and writes regenerable artefacts only.

## Upstream Ingest / Upstream Sync
Not applicable — `spec_source: internal`. No `ingest_spec`, no drift check, no `sync_signed_spec`.

## V3 Change Log (against signed V2)

| # | Finding | Change |
|---|---|---|
| 1 | verify-plan-2 #1 (Judge A, user decision) | **REQ-55 both-sides tiebreak reversed**: both credited extremes now evaluated independently; confluence holds if EITHER matches. REQ-55.6 rewritten, REQ-55.13 added. |
| 2 | verify-plan-2 #2/#3 (Judge A, informational + wording) | **Framing corrected**: mechanism note added (expiry drives real-data discrimination, not geometric overlap alone); REQ-55 preamble clarifies confluence is per-HTF-candle, not per-signal. |
| 3 | verify-plan-2 #4 (Judge A, CRITICAL) | **Expiry boundary corrected**: REQ-53 and REQ-55.11 now exclude only purges strictly AFTER expiry, not at-or-after — the candle that both purges and fills the same FVG is creditable again. |
| 4 | verify-plan-2 #5 (Judge A) | **Two new scenarios**: REQ-53.4 (consumer-coupling, structural), REQ-60.3 (≥50-trades floor). No new REQ-IDs — both are scenarios under already-admitted requirements. |
| 5 | verify-plan-2 #7 (Judge B, CRITICAL) | **REQ-60.2's denominator made explicit**: the full `aligned` non-`fvg_fill` population, not the post-`never_confirmed`-cut subset — resolves the mathematical unreachability Judge B proved under the other reading. |
| 6 | verify-plan-2 #9 (Judge B) | **REQ-40.2 decoupled** from `detections.csv` row counts — `signals_considered` measured independently, never asserted equal to a `detections.csv` count. |
| 7 | verify-plan-2 #10 (Judge B) | **REQ-59.2 scoped** to signals that actually reach the confluence-check stage; the universal claim was false for signals an earlier cut already disposed of. |
| 8 | verify-plan-2 #13 (user decision) | **REQ-60.4 added**: S-000 halts on post-gate performance regression vs. the pre-gate baseline, even when the discrimination band and trade floor both pass. |
| 9 | verify-plan-2 #12 (user decision) | No spec change — `--types model1` needs no disclosure note; recorded in Explicitly Out of Scope for the record. |

Findings #6 (REQ-46 slice coverage), #8 (fixture design), #11 (baseline capture instructions) are NOT spec changes — routed to `sdd-design` V3 / `sdd-slice` V3.

**Verified against the real codebase before writing** (carried forward from V2, unchanged by V3 — no code-level claim in this spec needed re-verification since V3 only corrects boundary/wording/denominator definitions, not detector behaviour claims):
- `entries/model1.py::_purge_signals` — high-side breach → `direction="bearish"`; low-side → `"bullish"`. CONFIRMED.
- `primitives/crt_range.py::first_breach_index` — checks `candle.high > high` BEFORE `candle.low < low`; both-sides identification order unaffected by V3 (V3 changes which extreme(s) are CREDITED for confluence, not which side is identified as the purge). CONFIRMED.
- `backtest/simulate.py::_population_cuts` — `fvg_fill` → `excluded_no_crt_range` is the FIRST `elif` branch; an `fvg_fill` signal never reaches the confluence cut. CONFIRMED.
- `cli.py` lines 117–121 — the `population` snapshot is taken after `_filter_by_date_range` and `_filter_by_session`. CONFIRMED.
- `primitives/fvg.py::_sweep_fill_status` — `fill_index` is the filling candle's index; an FVG becomes fill-eligible only at `start_index + 3` (= `origin_index + 1`). CONFIRMED.

**Size budget**: exceeded (as V1/V2 did, same reason) — the full-text MODIFIED reproduction mandate for four main-spec requirements takes priority over the 800-word guideline. Precedent accepted at V1 sign-off.

**SIGNED 2026-08-30 by human confirmation.** Next: `sdd-design` V3 (findings #6, #8, #11 — REQ-46 slice mapping, fixture design, baseline-capture reconciliation).
