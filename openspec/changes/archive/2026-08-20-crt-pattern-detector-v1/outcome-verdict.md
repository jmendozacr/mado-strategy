# Outcome Verdict — crt-pattern-detector-v1 (Reckoning Checkpoint, pre-archive)

**Checkpoint**: reckoning (backward-looking) | **Triage**: L
**Verdict**: `outcome-gap` — PROVISIONAL, `gap_category: scope`, override-cheap
**Gate status**: held open pending the human's answers to the conscience questions below.

---

## 1. Our objective was THIS

**Problem statement** (triage, corrected post-plan-verify):

> Stop manually scanning Forex charts by hand to find CRT/ICT setups — the notes in
> `docs/charter-1..5.md` define the methodology precisely enough to encode most of it
> as detection rules. v1 delivers 5 of the 7 originally-named setup types.

**North Star** (foresight memo, ratified):

> The trader's eye stops being the bottleneck for FINDING CRT/ICT setups and becomes
> the judge of setups already found — the methodology is read onto his own historical
> data mechanically and honestly, tagged with whether the higher timeframe agreed.
> **Success is measured by a chart he can act on, not by detectors that pass their tests.**

---

## 2. Did we deliver it? Where?

Evidence below is from a **live run performed by this checkpoint**, not read from a report:
real MT5 EURUSD M5 (100,000 rows) + H1 (41,320 rows) from `pairs/`, pair mode,
`--from-date 2026-08-11 --to-date 2026-08-19`. Suite re-run independently: **117 passed**.

| Piece of the pain | Delivered? | Where / evidence |
|---|---|---|
| Read his own MT5 exports | YES | Ran on the real 100k-row EURUSD M5 + H1 files, 34.7s wall clock |
| Encode the methodology mechanically | YES | 5 detectors, non-degenerate output on real data; 6 hypothesis no-lookahead properties |
| Detect honestly (no peeking, nothing silently dropped) | YES | Property suite + `insufficient_htf_data` tag instead of silent exclusion |
| Tag whether HTF agreed | YES, but near-vacuous as a filter | 2,470 of 2,796 Model-1 signals (88%) tagged `aligned` — it does not narrow the field |
| **A chart he can act on** | **PARTIAL — see §3** | Legible at ~1 day; unreadable at ~9 days |
| A scannable companion table | YES — this is the workhorse artefact | `detections.csv`, filterable by type/status/aligned |
| Date + type CLI filters | YES, and they filter RESULTS not just the plot | `cli.py::_filter_by_date_range` / `_filter_by_types` |

**Ratified foresight commitments — all honored, no drift:**

1. *Sequencing (detector before backtest)* — honored.
2. *Python over Pine Script, justified by committed phases 2 (backtest) + 3 (live alerts)* —
   **honored substantively**, not just nominally. What shipped is a layered pure-function
   core with pandas confined to ingestion (ADR-01/04, enforced by `lint-imports`), 6
   no-lookahead property tests, and heap-based sweeps that take 100k rows in ~35s. That is
   a genuine backtest/live-alert substrate — the thing the Python choice was bought for.
3. *Partial scope, 5 of 7 patterns* — honored exactly; OB/Breaker registered as followups.
4. *Deferred suspicion — "the AST config linter may be disproportionate ceremony"* —
   resolved benignly: it landed as one well-scoped test (`test_fitness_config.py`), with
   triangulation proving it catches drift. Not ceremony.

---

## 3. Did we drift? — the one criterion that demonstrably misses

**The North Star's own success sentence is "a chart he can act on." REQ-23.1 names the
scale it must hold at: "multi-week series, all 6 types — each visually distinct."**

At a 9-calendar-day window (1,971 M5 candles), the LTF panel — the execution panel, the
one he trades from — renders as a solid ribbon of overlapping markers. Individual
candlesticks are not distinguishable. Confirmed at native pixel resolution via a 3x
NEAREST-upscaled crop, so this is **not** a downscaling artifact.

At a 1-day window (288 candles) the same chart is genuinely legible — candles visible,
all 6 encodings distinguishable. So the tool has a usable zoom; it is just not the zoom
the spec names.

**Density, measured** (9-day window, one pair):

| Type | Rows | Per candle |
|---|---|---|
| model1 | 2,796 (757 confirmed, 191 pending, 1,848 invalidated) | 1.42 |
| crt_range | 1,968 (1,692 true-break, 276 false-break) | 1.00 |
| mss | 863 | 0.44 |
| swing | 848 | 0.43 |
| fvg | 390 | 0.20 |
| **total** | **6,865** | **3.48** |

**~948 live (confirmed + pending) Model-1 signals in ~7 trading days on a single pair —
about 135 per day.** The triage scope's in-scope bullet promised *"conservative tuning
philosophy (few false positives over high recall) for all discretionary detectors."*
That bullet has **no REQ-ID and no acceptance criterion**, so no gate below this one could
ever have caught it — which is exactly why it surfaces here and not in verify.

**Root cause (why `gap_category: scope`, not `problem-fit`):** the boundary between
*"detect mechanically"* and *"detect selectively enough to be actionable"* was never
specified. REQ-23.1's "each visually distinct" was only ever exercised against sparse
synthetic fixtures. Both the legibility miss and the density observation trace to that
single unspecified boundary. That routes to `sdd-spec`, where an actionability/selectivity
acceptance criterion would be written — not to `sdd-propose`, because the work genuinely
does address the stated pain.

**Honest counterweight, stated plainly:** this is NOT outputs-without-outcome. The tool
runs on his real data in 35 seconds, is honest by construction, and hands him a filterable
table plus a legible day-zoom chart. That is a real change in his reality. The gap is
partial and has a working path around it (window tighter, filter the CSV). Whether that
path is acceptable is his call, not mine — §4.

---

## 4. Conscience questions — ESCALATED, human-only (not answered here)

Significance is **not** re-asked: it was ratified at foresight pre-sunk-cost, and delivery
did not drift from that ratified commitment (see §2, items 2–3). These are usability only.

1. **The actual workflow.** As shipped, the working loop is: window to ~1 trading day for a
   readable chart, and filter `detections.csv` yourself for status/alignment. Is that the
   workflow you will actually use — or did you expect to open a multi-week overlay and see
   setups at a glance? (The North Star sentence says the latter; the tool delivers the former.)
2. **The density.** ~135 live Model-1 signals per trading day on one pair, with 88% of them
   tagged HTF-aligned. Is that a field you can judge as "setups already found" — or does v1
   need a selectivity or ranking pass before the eye genuinely stops being the bottleneck?
3. **The cheapest close.** Would `--status` / `--aligned` CLI filters (with status filtering
   also feeding the chart) close this for you — or is the issue the detection thresholds
   themselves, which would mean re-spec rather than a filter?

**If the answers are "this workflow is fine":** override the gap, archive proceeds, and the
items in §5 register as followups. That is a one-step close.
**If the answers are "I expected a glanceable multi-week chart":** route to `sdd-spec` to
write the missing actionability criterion, then re-design the density/rendering path.

---

## 5. Followups to register either way (non-blocking)

1. **CLI `--status` / `--aligned` filters** — today `--types` filters kind only; narrowing to
   live, HTF-aligned signals requires the trader to open the CSV himself.
2. **Chart declutter at multi-week zoom** — or a warning when marker count per plotted candle
   exceeds a legibility threshold, so the tool tells him to window in rather than silently
   emitting an unreadable PNG.
3. **Indistinguishable duplicate CSV rows** — 764 duplicate row-groups in the 9-day run, some
   repeated 5x. These are almost certainly distinct signals sharing an anchor candle, but the
   CSV carries no disambiguating column (no anchor index / signal id), so the trader cannot
   tell a genuine repeat from a bug. Add an identifying column or dedupe.
4. **Opaque legend occludes plotted data** — the white legend box hides roughly the first
   ~12% of the LTF candles at day zoom. Minor.
5. **`slices.md` S-006 manual-acceptance checkbox still unticked** — the work was performed
   three times with documented real-data evidence. Housekeeping only.

---

## Verdict

`outcome-gap` — **provisional**, `gap_category: scope`, blocking-with-override.

I am **not** asserting the tool is unusable — that is the human's judgement and it is
escalated in §4. I am asserting one fact he must see before archive rather than after:
**the North Star's own success criterion ("a chart he can act on") demonstrably fails at the
multi-week scale REQ-23.1 names, and the "conservative tuning" promise was never given a
criterion any gate could check.** Everything else promised at foresight was delivered, and
the phase-2/3 justification that bought the Python choice is genuinely honored by what shipped.
