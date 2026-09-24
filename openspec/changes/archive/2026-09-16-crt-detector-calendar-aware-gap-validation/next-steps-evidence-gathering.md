# Next Steps: Historical Session Evidence Gathering

**Change**: `crt-detector-calendar-aware-gap-validation`
**Written**: 2026-09-16
**Purpose**: Continuity note. If this session ends, a fresh session should read this file first to resume exactly where the evidence-gathering effort left off — without re-deriving the admissibility constraint below from scratch.

---

## 1. Current SDD state (as of this writing)

| Field | Value |
|---|---|
| Triage | L |
| Phase | `design` |
| Spec status | signed (V1) |
| Plan verify | none yet |
| State files | `.sdd/state/crt-detector-calendar-aware-gap-validation.json`, `sdd/crt-detector-calendar-aware-gap-validation/state` (engram) |

Key artifacts already in this change folder:
- `triage.md`, `proposal.md`, `explore.md` — planning history
- `design.md` — **signed**, defines the dormant contract (see Section 2 below, this is the load-bearing file)
- `evidence-report.md` — research report dated 2026-09-16, the fullest account of what's known/unknown about broker session history
- `specs/{controlled-calendar-activation,exclusive-gap-authority,trusted-closure-classification}/spec.md` — the three new capabilities this change defines

## 2. The constraint that governs everything below

`design.md`'s **External Assumptions** table and **ADR-01** already set the evidence bar for any future calendar activation. Read `design.md` in full before doing new research — it is short (~135 lines) and everything below depends on it.

**Explicitly REJECTED as admissible evidence** (design.md External Assumptions table):
- "Current screenshots or timestamp patterns establish historical schedules" → `rejected` — *"Never admissible evidence"*
- Market-convention research (industry-standard FX session hours, DST documentation from non-broker sources), even cross-referenced against the dataset's own gap patterns, falls in this rejected category. It is useful **narrative corroboration** for the evidence-report, but it cannot by itself justify activating a calendar.

**What IS required** (ADR-01 + Data Model section):
> "Historical broker closures can eventually be supported by retained original records with verifiable provenance" — status: `assumed`, gate: *"Blocks activation until externally evidenced"*

A future evidence claim must carry: broker, server/account identity, instrument, granularity, closure interval, inclusive policy window, **source-byte hash**, canonical-claim hash, **provenance**, **independent attestation**, activation identity.

**Practical translation**: we need an artifact that (a) Exness itself produced or published, (b) is dated to (or demonstrably reflects) the historical period in question, and (c) can be retained/hashed as a fixed byte sequence. A live "current specs" screenshot fails (a) — it's current, not historical. A blog post from a third-party aggregator fails (a) — Exness didn't produce it.

## 3. Ruled out — do not re-research these

Per the decision made this session (2026-09-16), these are **not** pursued as primary evidence paths, because they cannot satisfy Section 2's bar on their own:

- ❌ General FX market convention (babypips, forex.com, tmgm, myfxbook — all confirm Sun 22:00 UTC open / Fri 22:00 UTC close, 21:00 UTC shift during DST). Already gathered, already cited in the evidence-report's Section 2/3 partial findings. **Do not spend more effort here** — it's corroboration, not admissible evidence.
- ❌ Third-party Exness holiday aggregators (extrading-en.org, tradersunion.com, xmcom.org). Same reason — not Exness-originated, no provenance chain.

## 4. The two paths actually worth pursuing

### Path A — Direct request to Exness support/compliance

**Ask for**: written confirmation of the session schedule (open/close times, weekday pattern), holiday closure dates, and DST-handling policy that was **in effect** for `Exness-MT5Trial11` (or whatever the general demo-server policy was) across 2022-08-08 through 2026-08-19 — this is the authorized coverage window per `evidence-report.md` Section 4.3, **not** the older "2020-2026" phrasing that appears in some of the B4/B5 blocker text (that phrasing predates the coverage-window authorization; trust the 2022-08-08→2026-08-19 window).

**Why it might work**: a support response, especially in writing/email, is closer to "provenance-bearing" than anything gathered so far — it's Exness stating something directly, attributably, with a timestamp of its own (the reply date).

**Why it might not**: demo/trial accounts may get a lower support priority, and Exness may simply repeat the current published schedule without confirming historical stability.

**Status**: not yet attempted as of this writing.

### Path B (was "D") — Wayback Machine snapshots of Exness's own pages

**Target URLs** (already identified in `evidence-report.md` Section 1.3):
- `https://get.exness.help/hc/en-us/articles/4405235684498-Instrument-trading-hours`
- `https://get.exness.help/hc/en-us/articles/17923046759836-Holiday-trading-hours`

**What to do**: manually check `web.archive.org` for archived snapshots of both URLs across 2022–2026. If Exness updates these pages year over year (likely, given "Holiday trading hours" is inherently a yearly-refreshed article), old snapshots would show what was published **at that time** — which is a retained, dated, Exness-originated record. That satisfies (a) and (b) from Section 2; whether it satisfies (c) (hashable, retainable as a fixed byte sequence) is straightforward — save the snapshot HTML.

**Why this session couldn't do it**: the WebFetch tool used in this session is blocked from fetching `web.archive.org` directly (returned "Claude Code is unable to fetch from web.archive.org"). This needs to be done **manually in a browser**, or from a session/tool without that restriction.

**Status**: not yet attempted — blocked on tooling in this session, not on the idea itself.

**Concrete manual steps** (no account needed):

1. Calendar view for each target URL — paste directly into the browser address bar:
   ```
   https://web.archive.org/web/*/https://get.exness.help/hc/en-us/articles/4405235684498-Instrument-trading-hours
   https://web.archive.org/web/*/https://get.exness.help/hc/en-us/articles/17923046759836-Holiday-trading-hours
   ```
2. If the calendar looks sparse or empty, use the CDX API for a plain-text list of every captured timestamp before clicking through anything:
   ```
   http://web.archive.org/cdx/search/cdx?url=get.exness.help/hc/en-us/articles/4405235684498*&output=text&fl=timestamp,original&collapse=timestamp:8
   ```
   (swap the article ID for the holiday-hours URL too). Each line is a `YYYYMMDD` timestamp — tells you which years are actually covered before investing time.
3. For each year 2022→2026, open the oldest available snapshot of that year (click the calendar dot, or jump directly: `https://web.archive.org/web/20230101000000*/<url>`).
4. In each snapshot, check specifically for: weekday open/close times, any DST/seasonal-shift wording, exact holiday closure dates listed, and whether the text matches the current live version or differs.
5. For anything worth keeping: record the **exact snapshot URL with its timestamp** (e.g. `web.archive.org/web/20230315.../...`) — that URL itself is the provenance chain the signed design requires — plus a saved screenshot or HTML copy.
6. If no snapshot exists before a given year (the help-center article may be newer than the dataset window), widen the net to the main Exness domain in case an older static page existed before migrating to the help center:
   ```
   https://web.archive.org/web/*/exness.com/*trading-hours*
   ```
7. Feed anything found back into `evidence-report.md` (Sections 1.3 / 2.1), citing the exact snapshot URL — that's what moves an item from `unavailable` to `repository-verified, externally sourced`.

## 5. Concrete checklist for the next session

- [ ] Path A: draft and send the support request to Exness (see "Ask for" above); record the response verbatim, with date, in a new file or appended to `evidence-report.md`.
- [ ] Path B: manually check Wayback Machine for both URLs above across 2022–2026; save any snapshots found (as local files, with retrieval date, and ideally a hash) and note what schedule each one shows.
- [ ] Once evidence exists from either path: update `evidence-report.md`'s classification tables (items currently marked `unavailable` for B3/B4/B5/B6) and bring the finding back to `design.md` for design ratification — the current `design.md` stays valid as the dormant contract; a real calendar activation is explicitly **a separate, new SDD change** per ADR-01's consequence: *"A later activation needs a separate change and approval."*
- [ ] If neither path yields anything usable within a reasonable effort: the fallback is what's already recorded as the conservative decision (evidence-report.md Section 9) — leave the calendar dormant indefinitely, keep the existing allowlist, and treat this as accepted scope rather than a blocker to revisit repeatedly.

## 6. Open side-question — not yet decided

Whether to drop `DXYm` from the 3-instrument set (`EURUSDm`, `GBPUSDm`, `DXYm`) used by the direction-policy statistical runner was discussed this session but **left undecided**. Dropping it would remove one item from the "Remaining Human Decisions" list in `evidence-report.md` (the DXY-CFD-vs-FX-hours question, item #7 — not one of the lettered B1–B9 blockers) and simplify the dataset surface, but would **not** resolve B3–B6 (those apply to EURUSDm/GBPUSDm regardless), and would require reopening the frozen statistical protocol (SHA-256 `192780eb...`) since `instrument_order` is a preregistered field. If a future session picks this up, it's a separate scope decision from the evidence-gathering above — don't conflate the two.

## 7. Quick orientation map for a fresh session

- Backtest engine (candle-by-candle trade simulator): **already built, archived, validated on real data.** Not blocked by anything in this document. See `openspec/changes/archive/2026-08-29-crt-detector-backtest-engine/`.
- Direction-policy statistical runner (Layer 1–3, bootstrap validation of Order Flow/Bias/DoL): implementation **closed**, but real-data execution **unauthorized** — blocked specifically on the evidence this document tracks. See `openspec/changes/crt-detector-direction-policy-statistical-runner-layer3/closeout.md`.
- This calendar-gap-validation change: **dormant by design**, signed spec, no code touched. See `design.md` in this same folder for the authoritative constraint.
