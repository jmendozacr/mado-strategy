# Evidence Report — Calendar-Aware Dataset Gap Validation

**Change**: `crt-detector-calendar-aware-gap-validation`
**Report date**: 2026-09-16
**Scope**: Read-only research report. No code, spec, protocol, manifest, dataset, baseline, authorization, checkpoint, tests, or commits were modified. Only this file was written.
**Purpose**: Establish what is known, what is externally verifiable, and what requires human decision before the design draft at `openspec/changes/crt-detector-calendar-aware-gap-validation/design.md` can be ratified and implemented.

---

## 1. Broker / Provider Identity

### 1.1 What the Repository Proves

The protocol artifact (`detector/research/direction_policy_discovery_v1_amendment_1.json`) names nine dataset files. All three instruments carry an `m` suffix: **EURUSDm**, **GBPUSDm**, **DXYm**. The dataset identity field in the protocol is `"pairs/_discovery_snapshot"`. No broker name, server name, or account type is stated anywhere in the protocol, the manifest builder (`detector/runner/manifest_builder.py`), or any other committed file.

The design draft (`design.md` Section 5.1.3) contains the following design-time inference: "The `m` suffix on these symbols typically indicates a MetaQuotes demo/micro account." This statement is a design inference about naming convention, not a repository-verified fact. It is not contradicted by any other repository evidence, but it is not proven by any repository file either.

**The checkpoint file** (`.claude-calendar-aware-gap-design-checkpoint.md`, "Verified external reference") records that the `SymbolInfoSessionTrade` reference was consulted and confirmed to have no historical effective-date parameter. That conclusion is confirmed by this report's own fetch of `https://www.mql5.com/en/docs/marketinformation/symbolinfosessiontrade`.

### 1.2 Evidence Classification

| Item | Classification | Source |
|---|---|---|
| Instruments are EURUSDm, GBPUSDm, DXYm | `repository-verified` | `detector/research/direction_policy_discovery_v1_amendment_1.json` field `dataset.files` |
| Dataset identity is `pairs/_discovery_snapshot` | `repository-verified` | Same file, `dataset.identity` |
| `m` suffix = MetaQuotes demo account | `partial` — naming convention inference, not broker documentation | `design.md` Section 5.1.3 (design inference, not external evidence) |
| Actual broker / server identity | `user-supplied` | User identified broker `Exness`, server `Exness-MT5Trial11`, demo account on 2026-09-16; not recorded in a committed repository artifact |
| Demo vs. live server distinction for session schedules | `unavailable` | Requires broker documentation |
| Current session specification on `Exness-MT5Trial11` | `user-supplied current snapshot` | MT5 Specification screenshots for EURUSDm, GBPUSDm, and DXYm, supplied 2026-09-16; identical sessions: Sunday 21:05–24:00, Monday–Thursday 00:00–24:00, Friday 00:00–20:59, Saturday closed |

### 1.3 What Is Needed

The broker name and server name must be established from the MT5 terminal's "Server" field or from the user's brokerage account records. Without broker identity, no broker-specific session schedule, holiday calendar, or DST policy can be sourced from an authoritative external document.

**Broker identity supplied by the user (2026-09-16):** broker `Exness`, server `Exness-MT5Trial11`, demo account. This identifies the provider and server label but does not by itself prove that a currently published Exness schedule was the schedule applied historically to this server.

**Current official Exness evidence:** Exness states that its trading servers use UTC+0 and that most instruments follow seasonal DST schedules. Its published Forex table gives Sunday open/Friday close times of 21:05/20:59 UTC in summer and 22:05/21:59 UTC in winter. These pages support the repository's UTC+0 interpretation and establish that UTC session windows can vary seasonally, but they are current guidance and do not establish the historical 2022–2026 schedule for `Exness-MT5Trial11` or the exact DXYm schedule. Sources: `https://get.exness.help/hc/en-us/articles/4405235684498-Instrument-trading-hours` and `https://get.exness.help/hc/en-us/articles/17923046759836-Holiday-trading-hours` (fetched 2026-09-16).

**Current MT5 specification evidence supplied by the user (2026-09-16):** screenshots in `D:\Josué\Downloads\Especificacion\EURUSDm.png`, `GBPUSDm.png`, and `DXYm.png` show identical current sessions for quotations and operations on all three symbols: Sunday `21:05–24:00`, Monday–Thursday `00:00–24:00`, Friday `00:00–20:59`, Saturday closed. The screenshots identify the current server configuration visible in MT5, but they do not establish historical effective periods or prove that the same schedule applied throughout the authorized 2022–2026 window.

---

## 2. Historical Session Schedules

### 2.1 Dataset Coverage Windows (Repository-Verified)

From the protocol's `dataset.files` array — these are the observed file endpoints, not independently frozen expected coverage:

| Instrument | Granularity | Raw start timestamp (protocol field `start_utc`) | Raw end timestamp (protocol field `end_utc`) |
|---|---|---|---|
| DXYm | D1 | 2021-10-27T00:00:00 | 2026-08-19T00:00:00 |
| EURUSDm | D1 | 2020-01-02T00:00:00 | 2026-08-19T00:00:00 |
| GBPUSDm | D1 | 2020-01-02T00:00:00 | 2026-08-19T00:00:00 |
| DXYm | H4 | 2021-10-27T16:00:00 | 2026-08-19T20:00:00 |
| EURUSDm | H4 | 2020-01-02T00:00:00 | 2026-08-19T20:00:00 |
| GBPUSDm | H4 | 2020-01-02T00:00:00 | 2026-08-19T20:00:00 |
| DXYm | M15 | 2022-08-03T00:00:00 | 2026-08-19T20:30:00 |
| EURUSDm | M15 | 2022-07-26T00:00:00 | 2026-08-19T20:30:00 |
| GBPUSDm | M15 | 2022-07-27T00:00:00 | 2026-08-19T20:30:00 |

**Column labeling note**: `start_utc` and `end_utc` are the field names in the protocol's data model for dataset file endpoints; the suffix alone does not verify timezone. The prior repository analysis in Section 3.2 independently concluded that these MT5 export timestamps are UTC+0 with no server-clock DST. Accordingly, this report interprets the raw endpoints as UTC at the `repository-verified (prior SDD analysis)` level, while noting that the conclusion is not backed by authoritative broker documentation. Read these as raw timestamps with a repository-supported UTC interpretation, not as externally verified broker schedule times.

**Distinction from experiment measurement cutoffs**: `candidate_cutoff_end_utc` and `outcome_followup_end_utc` are different — they are independent protocol-defined measurement boundaries with explicit Z-suffix values (`2026-08-19T00:00:00Z`, `2026-08-19T20:30:00Z`), not derived from CSV export timestamps. They define when the experiment's measurement window ends and are treated as UTC by the protocol's own definition. That distinction is preserved throughout this report.

**Important**: These are `DatasetFileRecord.start_utc` / `end_utc` values derived from actual file contents. As the design draft states (Section 1.4), these values MUST NOT be used as `SessionCalendarRef.expected_start/end` because doing so makes boundary truncation detection trivially pass.

The protocol also declares `candidate_cutoff_end_utc: 2026-08-19T00:00:00Z` and `outcome_followup_end_utc: 2026-08-19T20:30:00Z`.

### 2.2 Gap Inventory Evidence (Repository-Verified, Timestamp-Only)

The `.claude-layer3-gap-inventory.md` records a timestamp-only scan of all nine files at HEAD `90320b2`. Total gaps above fixed-cadence: **2,575** (D1: 943, H4: 956, M15: 676).

**D1 pattern** (EURUSDm/GBPUSDm): 342–346 two-day gaps and 2–4 three-day gaps. All two-day gaps fall on Friday-to-Sunday boundaries, consistent with a Mon–Fri trading week. The three-day gaps fall on dates that correspond to Dec 22–25 and Dec 29–Jan 1 in 2022/2023/2024 (Fri-to-Mon including a holiday). DXYm/D1 shows the same Friday pattern (249 two-day + 2 three-day gaps) but starts only from 2021-10-27.

**H4 pattern** (EURUSDm/GBPUSDm): Weekly gaps at the end of each trading week. Under the prior UTC+0 repository finding (Section 3.2), the last H4 bar before a gap closes at raw timestamp 20:00 UTC on Friday and the first bar after reopens at raw timestamp 00:00 or 20:00 UTC on Sunday/Monday. Two anomalous gaps at Dec 24 and Dec 31 (both years 2021) end at raw timestamp 16:00 UTC instead of 20:00, yielding 2-day-4-hour deltas — pattern-consistent with early-close days, but not confirmed against broker schedules. One anomalous 16-hour gap at the dataset start (2021-10-27 16:00 → 2021-10-28 08:00 raw timestamps) may reflect a partial opening bar at dataset inception.

**M15 pattern** (DXYm): The dominant weekly gap is `2 days, 0:15:00` (177 occurrences), not `2 days, 0:00:00` — meaning the last Friday bar ends at XX:45 and the first Monday bar begins at (XX+2days):00 + 15 minutes. A second mode `2 days, 1:15:00` (23 occurrences) alternates with the dominant mode across two identifiable periods. The shift between these two modes occurs at calendar dates consistent with US DST boundaries (e.g., 2022-11-04 → 2022-11-06 is the first `1:15:00` gap; 2023-03-10 → 2023-03-12 transitions back). The U.S. DST calendar rule — second Sunday in March through first Sunday in November — is established by U.S. Department of Transportation rule (source: https://www.transportation.gov/briefing-room/news-digest-dot-28-16); this citation establishes the U.S. calendar rule only and does not establish the broker's session schedule or the causal mechanism. Under the prior UTC+0/no-server-DST repository finding, a server-clock adjustment is ruled out; a seasonal UTC session-window shift or another mechanism remains unproven. Short intra-week gaps appear: `0:30:00` (16 occurrences), `0:45:00` (2), `1:00:00` (2), `1:30:00` (1), `2:15:00` (1), `3:15:00` (1).

**M15 pattern** (EURUSDm/GBPUSDm): Similar alternating `2 days, 0:15:00` / `2 days, 1:15:00` modes. EURUSDm shows 202 two-day-0:15 + 4 two-day-1:15. Short gaps: `0:30:00` (2), `1:00:00` (1).

**Classification constraint**: The design draft is explicit (Section 9, Decision 6) that these patterns are timestamp-only evidence. The shift between the two dominant weekly modes is consistent with DST transitions, but consistency is not proof. The short intra-week gaps (0:30, 0:45, 1:00, 1:30, 2:15, 3:15 for DXYm; 0:30, 1:00 for EURUSDm) cannot be classified from timestamp patterns alone as legitimate partial closures, data feed interruptions, or MT5 server maintenance without broker documentation.

### 2.3 Evidence Classification for Session Schedules

| Item | Classification | Notes |
|---|---|---|
| Mon–Fri trading week for all three instruments | `partial` | Gap pattern is strongly consistent; not proven by broker documentation |
| Session close time Friday (M15 last-bar raw timestamp) | `partial` — pattern-inferred | Raw timestamp ~20:45 (summer-pattern period) / ~21:45 (winter-pattern period); interpreted as UTC under the prior repository finding, but not confirmed as the broker's session close |
| Session open time Monday (M15 first-bar raw timestamp) | `partial` — pattern-inferred | Raw timestamp ~21:00 (summer-pattern period) / ~22:00 (winter-pattern period); interpreted as UTC under the prior repository finding, but not confirmed as the broker's session open |
| Early close on Dec 24 and Dec 31 (H4 evidence) | `partial` | Two H4 gaps end at raw timestamp 16:00 UTC instead of 20:00 under the prior repository finding; pattern-consistent with early-close days; sample size = 2; not confirmed against broker schedules |
| Three-day D1 gaps around Dec 24–25 and Dec 31–Jan 1 | `partial` | Pattern-consistent with holiday closures; requires broker confirmation |
| Whether broker changed session hours during 2020–2026 | `unavailable` | Cannot be determined from timestamp patterns |
| Whether demo-server sessions match live-server sessions | `unavailable` | Requires broker documentation |
| Seasonal 1-hour gap-mode shift — transition dates coincide with US DST calendar | `partial` — date coincidence only; cause unexplained | M15 dominant gap mode shifts by 1 hour at calendar dates coinciding with US DST boundaries (second Sunday in March / first Sunday in November per U.S. DOT rule: https://www.transportation.gov/briefing-room/news-digest-dot-28-16; U.S. calendar rule only); prior repository finding (UTC+0, no server DST) rules out server-clock adjustment as the cause; UTC session-window shift or other mechanism remain possible but are not established; clock basis resolved to UTC+0 by prior finding; causal interpretation unavailable |
| DXY CFD session hours vs. FX pair session hours | `partial` | M15 raw-timestamp gap patterns appear similar to EURUSDm/GBPUSDm; not confirmed by broker DXY schedule documentation |

---

## 3. MT5 Bar Timestamp Behavior

### 3.1 What Official MQL5 Documentation Establishes

The following findings derive from fetching official MQL5 documentation pages during this research session. Each finding is cited to the specific URL consulted.

#### 3.1.1 Bar Timestamp = Period Start Time (Open Time)

Source: `https://www.mql5.com/en/docs/constants/structures/mqlrates` (fetched 2026-09-15)

The `MqlRates` structure's `time` field is documented as **"Period start time"**. Within the MT5 runtime, bar timestamps therefore represent the bar's open time, not its close time.

**Limitation — this definition does not establish export timezone.** MQL5's internal `MqlRates.time` convention defines what the timestamp means within the platform; the documentation consulted does not say whether standard history export preserves server timestamps or converts them to UTC. That documentation gap does not erase the separate prior repository analysis (Section 3.2), which concluded from two independent analyses that these exports are UTC+0 with no DST. The dataset filenames are consistent with the open-time convention (e.g., `EURUSDm_Daily_202001020000_202608190000.csv`) but are not themselves timezone evidence. The UTC+0 conclusion remains repository-internal rather than externally confirmed by broker documentation.

#### 3.1.2 Server Time vs. UTC — Two Distinct Functions

Source: `https://www.mql5.com/en/docs/dateandtime/timecurrent` and `https://www.mql5.com/en/docs/dateandtime/timegmt` (both fetched 2026-09-15)

MQL5 exposes two separate time functions:
- `TimeCurrent()` — returns **server time**, formed on the trade server, independent of the local computer clock. The documentation does not state the server's timezone explicitly.
- `TimeGMT()` — returns **GMT (UTC)**, "calculated taking into account the DST switch by the local time on the computer where the client terminal is running."

The existence of two separate functions establishes that MQL5 models server time and UTC as conceptually distinct. It does **not**, by itself, prove that they differ in value for a particular server. Separately, the archived repository analysis concluded that the exports in this repository use UTC+0 with no DST (Section 3.2). The named broker/server and its configuration are still unavailable, and the repository finding is not authoritative broker documentation.

#### 3.1.3 SymbolInfoSessionTrade — No Date/Period Parameter

Source: `https://www.mql5.com/en/docs/marketinformation/symbolinfosessiontrade` and `https://www.mql5.com/en/docs/marketinformation/symbolinfosessionquote` (both fetched 2026-09-15)

Both session query functions share this signature:
```
bool SymbolInfoSessionTrade(string name, ENUM_DAY_OF_WEEK day_of_week, uint session_index, datetime& from, datetime& to)
```

Key facts established by the documentation:
1. Session times are returned as "seconds from 00 hours 00 minutes, in the returned value date should be ignored" — meaning time-of-day only, no date context.
2. The function signature accepts no date or effective-period argument. From this, the bounded inference is that calling this function can only retrieve whatever session schedule is currently configured on the server — there is no mechanism in the documented API to query what schedule was in effect on a past date. The documentation does not explicitly describe the function as "current-only"; the absence of a date parameter is what grounds this inference.
3. The documentation does not specify whether the returned times are in UTC or server local time. This remains unresolved.
4. Consequently, a `SymbolInfoSessionTrade` call cannot establish what session hours were in effect during earlier periods of the 2020–2026 dataset window.

#### 3.1.4 D1 Bar Timestamp Convention — Not Established by Documentation

The MQL5 documentation consulted does not explicitly state what time-of-day a D1 (daily) bar receives as its open timestamp. The documentation only confirms that `MqlRates.time` is the period start time.

The gap inventory shows all D1 bar timestamps ending in `T00:00:00` for all three instruments. MQL5 documentation consulted does not define the D1 bar's time-of-day anchor. Under the prior repository finding that these exports are UTC+0 with no DST (Section 3.2), the raw `T00:00:00` timestamps are interpreted as midnight UTC. This repository-level interpretation does not establish the broker's documented session rollover or explain bar-grid alignment.

The H4 gap inventory shows the last H4 bar before the weekend gap carries raw timestamp 20:00 in the summer-pattern period and 21:00 in the winter-pattern period; the DXYm/H4 file begins at raw timestamp 16:00. The prior repository finding (Section 3.2) concluded the exports are UTC+0; under that finding, these values are UTC times — a 20:00–21:00 UTC session close on a UTC+0 server. This is fully consistent with UTC+0 and does not require an EET server.

**The EET inference is contradicted by the prior repository finding.** A pattern-based EET inference would require (1) raw timestamps equal UTC and (2) a non-zero UTC offset (to place server midnight at 22:00 or 21:00 UTC). The prior finding (UTC+0, no DST) eliminates step (2): there is no UTC offset to explain. Under UTC+0, D1 `T00:00:00` raw timestamps mean midnight UTC — consistent with all observed values and requiring no EET hypothesis. The EET interpretation is therefore not merely unconfirmed; the prior repository finding directly contradicts it. External broker documentation remains the authoritative final source, but the EET inference has no current support from any evidence in this repository.

#### 3.1.5 Partial Bars at Session Boundaries — Not Established

The design draft (Section 2.2, Step 3 "Partial bars at session open") identifies whether MT5 aligns bar open timestamps to a fixed UTC grid or anchors them to session open as an unresolved external question. The MQL5 documentation consulted does not address bar grid alignment or partial bar behavior at session open. This remains `unavailable` from official documentation.

#### 3.1.6 Summary of MT5 Documentation Findings

| Item | Classification | Source URL / Date |
|---|---|---|
| `MqlRates.time` = period start time (open time) | `externally-verified` | `mql5.com/en/docs/constants/structures/mqlrates`, fetched 2026-09-15 |
| `TimeCurrent()` = server time (not UTC) | `externally-verified` | `mql5.com/en/docs/dateandtime/timecurrent`, fetched 2026-09-15 |
| `TimeGMT()` = UTC (GMT) | `externally-verified` | `mql5.com/en/docs/dateandtime/timegmt`, fetched 2026-09-15 |
| MQL5 models server time and UTC as distinct (two separate functions exist) | `externally-verified` | MQL5 docs fetched 2026-09-15; establishes the API distinction, NOT that this broker's server offset is non-zero |
| Actual UTC offset of this broker's MT5 server (from MQL5 docs alone) | `unavailable` | Two-function existence does not prove offset is non-zero; see Section 3.2 for repository-internal finding |
| CSV exports are UTC+0, no DST (prior repository finding) | `repository-verified (prior SDD analysis)` | `openspec/changes/archive/crt-detector-htf-timezone-anchor/explore.md`; two independent blind analyses; not external broker documentation |
| `SymbolInfoSessionTrade` has no date/period parameter (bounded inference: cannot query historical schedules) | `externally-verified (bounded inference)` | `mql5.com/en/docs/marketinformation/symbolinfosessiontrade`, fetched 2026-09-15; absence of date arg grounds the inference |
| Session time return value timezone (UTC or server local) | `unavailable` | Documentation does not specify; fetched 2026-09-15 |
| Clock basis of exported CSV timestamps | `repository-verified (prior SDD analysis)` — UTC+0; not confirmed by external broker documentation | Prior finding: UTC+0, no DST; MQL5 export format timezone not addressed in documentation consulted independently |
| D1 bar open timestamp convention | `repository-verified (prior SDD analysis)` — midnight UTC per UTC+0 finding | Under UTC+0 export clock, `T00:00:00` = midnight UTC; not confirmed from broker documentation |
| Bar grid alignment at session boundaries (fixed UTC grid vs. session-anchored) | `unavailable` | Not addressed in documentation consulted or prior repository finding |
| MT5 server timezone for MetaQuotes demo servers specifically (external documentation) | `unavailable` | Not addressed in documentation consulted |

### 3.2 Prior Repository Finding: CSV Export Clock Basis

**Source**: `openspec/changes/archive/crt-detector-htf-timezone-anchor/explore.md` and `triage.md` (committed archive; change closed 2026-08-31).

The `crt-detector-htf-timezone-anchor` change was opened on the hypothesis that these MT5 exports use UTC+3 (EEST, described in the triage as the "MetaQuotes/MT5 historical default"). Its `sdd-explore` phase ran two independent, blind, adversarial analyses before the change was closed without any code modification:

- **Architect**: applied the MetaQuotes weekly-boundary signature — the well-known MT5 weekly open/close gap pattern — against the real dataset.
- **QA Engineer**: applied four orthogonal signals — weekly open/close alignment, tick-volume peak, D1 Sunday-bar existence, and a simulation of the proposed UTC+3 fix against the existing test suite.

**Archived conclusion** (`explore.md`, synthesized): both analysts independently concluded that **these MT5 exports for EURUSDm, GBPUSDm, and DXYm are plain UTC+0, with no DST adjustment**. The UTC+3/EEST hypothesis was rejected. `core/kill_zone.py` (which treats the naive timestamps as UTC) was confirmed correct. The triage closure note records: "The broker is UTC+0, no DST. `core/kill_zone.py`/REQ-29 is CORRECT as written. The 'UTC+3/EEST' claim does not hold."

**Distinction from external broker evidence**: this finding is a repository-internal analysis based on data signals from the real dataset. It establishes consistency with UTC+0 across multiple orthogonal signals applied to the actual files in this repository. It is not an authoritative statement from the broker, not MetaQuotes documentation, and not any external source that names this specific broker's configuration. It does not substitute for broker documentation on session hours, holidays, or DXY CFD schedules.

**TradingView distinction**: the original UTC+3 hypothesis originated from a two-timestamp cross-check between these CSVs and TradingView's display (FOREXCOM, fixed UTC-4). The exploration found that TradingView's display used a **fixed** UTC-4 offset — not actual NY-local time (which would shift between UTC-4 in EDT and UTC-5 in EST across DST transitions). Both cross-check timestamps fell in June (inside both EU and US DST) and shared the same residue class mod 4, providing near-zero independent discriminating information across the six offset candidates consistent with "lands on an H4 boundary." The UTC+3 inference did not survive adversarial scrutiny. TradingView's fixed UTC-4 display is a presentation choice of that platform and does not establish the broker's clock.

**Implication for Section 3.1.4 EET inference**: the pattern-based EET inference in Section 3.1.4 assumed (1) raw timestamps equal UTC and (2) a non-zero UTC offset implies EET. The prior repository finding eliminates the second precondition: if the exports are UTC+0, there is no UTC offset to explain. The observed H4 raw timestamps (20:00 / 21:00 at weekend close) are fully consistent with a 20:00–21:00 UTC session close on a UTC+0 server; they do not require an EET server. The EET inference is not merely unconfirmed — the prior finding contradicts it at step (2).

**Implication for M15 alternating gap modes**: the prior finding (UTC+0, no DST on the server clock) does not explain the 1-hour alternating shift in the M15 dominant weekly gap distribution. If the exports are UTC+0 with no DST adjustment, the server clock does not change seasonally — yet the gap-mode shift occurs at calendar dates coincident with U.S. DST boundaries. This coincidence remains a raw date coincidence; the prior finding provides no causal mechanism. The cause of the 1-hour M15 gap-mode shift is unexplained by the prior finding and is not evidence of broker DST.

#### 3.2.1 Summary of Prior Repository Finding

| Item | Classification | Source |
|---|---|---|
| CSV exports (EURUSDm, GBPUSDm, DXYm) are UTC+0, no DST | `repository-verified (prior SDD analysis)` | `openspec/changes/archive/crt-detector-htf-timezone-anchor/explore.md`; two independent blind adversarial analyses; change closed 2026-08-31; not external broker documentation |
| UTC+3/EEST hypothesis rejected | `repository-verified (prior SDD analysis)` | Same source; original two-timestamp cross-check found to be information-poor and non-discriminating |
| TradingView FOREXCOM UTC-4 display is a fixed presentation offset, not the broker's clock | `repository-verified (prior SDD analysis)` | Same source; fixed UTC-4 is not DST-following NY-local time |
| Broker identity (who configured the server as UTC+0) | `unavailable` | Prior finding establishes clock behavior from data signals, not broker identity |
| Cause of M15 1-hour gap-mode shift given UTC+0 exports | `unavailable` | Prior finding leaves this unexplained; coincidence of dates with U.S. DST calendar is not a causal explanation |
| Historical broker session schedule, holidays, DXY CFD hours | `unavailable` | Prior finding does not address these; external broker documentation still required |

---

## 4. Coverage Window vs. Instrument Availability

### 4.1 Concept Taxonomy (from design.md Section 1.3)

The design draft defines four concepts that must not be conflated. This report uses the same taxonomy:

1. **Calendar evidence validity** (`SessionCalendar.validity_start/end`): the date range for which the declared session schedule has been externally confirmed accurate.
2. **Experiment expected coverage** (`SessionCalendarRef.expected_start/end`): the pre-outcome frozen coverage window the experiment declares each dataset must contain. A human decision, not derivable from broker availability or observed file endpoints.
3. **Broker instrument availability**: when the broker began/stopped offering the instrument. External evidence.
4. **Schedule-period applicability**: which session definition applies on a given date when session hours vary over time.

### 4.2 What the Repository Proves

The protocol defines two independent measurement boundaries with explicit UTC Z-values: `candidate_cutoff_end_utc: 2026-08-19T00:00:00Z` and `outcome_followup_end_utc: 2026-08-19T20:30:00Z`. These are protocol-defined constants, not derived from CSV export timestamps, and are treated as UTC by the protocol's own definition. They are not the expected dataset coverage window.

The protocol's `dataset.files` array records `start_utc` and `end_utc` per file — these field names carry the `_utc` suffix as a data-model convention, but the values are raw timestamps derived from CSV file contents. The prior repository analysis (Section 3.2) interprets these timestamps as UTC+0; that interpretation is repository-verified, not independently confirmed by broker documentation. These are observed file endpoints, not independently frozen coverage contracts.

The DXYm start date difference (2021-10-27 vs. 2020-01-02 for Forex pairs) is a fact established by the dataset files. The design draft's inference that this reflects a shorter dataset rather than different calendar behavior is a design inference. It is not confirmed by broker documentation.

### 4.3 The Boundary Completeness Problem

The design draft (Section 1.4) establishes that `SessionCalendarRef.expected_start/end` MUST NOT be set to observed `DatasetFileRecord.start_utc/end_utc` because doing so makes boundary truncation detection trivially pass. An independently frozen coverage contract is required.

**Authorized contract (2026-09-16):** one common expected window applies to all nine instrument/granularity combinations: `expected_start = 2022-08-08` and `expected_end = 2026-08-19`, inclusive. This was selected as a pre-outcome human decision for comparability and is not derived from observed file endpoints. The protocol's `outcome_followup_end_utc = 2026-08-19T20:30:00Z` remains a separate measurement cutoff.

### 4.4 Evidence Classification

| Item | Classification | Source |
|---|---|---|
| Protocol `start_utc`/`end_utc` field values per file (raw CSV-derived; interpreted as UTC by prior repository finding) | `repository-verified` | Protocol JSON `dataset.files` records the values; prior archived analysis supports UTC+0/no DST; `_utc` suffix alone is not timezone proof |
| DXYm dataset starts later (protocol `start_utc` 2021-10-27) than Forex pairs (2020-01-02) | `repository-verified` | Protocol JSON `dataset.files`; endpoints are interpreted as UTC under the prior repository finding |
| Experiment measurement cutoffs `candidate_cutoff_end_utc: 2026-08-19T00:00:00Z`, `outcome_followup_end_utc: 2026-08-19T20:30:00Z` | `repository-verified` | Protocol JSON; these are independent protocol-defined measurement boundaries with explicit Z values, not derived from CSV export timestamps; treated as UTC by the protocol's own definition |
| Independently frozen expected dataset coverage per instrument/granularity | `repository-verified` — human-authorized contract | Common inclusive window `2022-08-08` through `2026-08-19` for all nine combinations; authorized 2026-09-16; not derived from observed endpoints |
| DXYm broker availability start date (whether 2021-10-27 is broker availability or data gap) | `unavailable` | Requires broker documentation |

---

## 5. Evidence Classification Matrix

### 5.1 Required Evidence Items (a) through (g)

**(a) UTC / local timezone for broker and MT5 server**

| Aspect | Classification | Evidence |
|---|---|---|
| MQL5 distinguishes server time (`TimeCurrent`) from UTC (`TimeGMT`) as separate API concepts | `externally-verified` | MQL5 docs fetched 2026-09-15; establishes the API distinction only — does not prove this broker's server offset is non-zero |
| CSV exports are UTC+0, no DST (prior repository finding) | `repository-verified (prior SDD analysis)` | `openspec/changes/archive/crt-detector-htf-timezone-anchor/explore.md`; two independent blind analyses; not external broker documentation |
| UTC+3/EEST hypothesis | `repository-verified as rejected` | Same source; original two-timestamp cross-check non-discriminating; adversarial analysis rejected UTC+3/EEST |
| Whether server runs on EET (UTC+2/UTC+3) | `contradicted by prior repository finding` | Prior finding (UTC+0) eliminates the non-zero-offset precondition; EET requires a UTC offset to explain; see Section 3.2 |
| Clock basis of exported CSV timestamps | `repository-verified (prior SDD analysis)` — UTC+0 | Prior finding: UTC+0, no DST; not confirmed by external broker documentation; does not resolve authoritative broker session schedule |
| Broker identity and server label | `user-supplied` | User identified `Exness` / `Exness-MT5Trial11` / demo on 2026-09-16; this does not establish historical schedule applicability |

Exness-specific current documentation now supplies the missing provider-level context: UTC+0 server time and seasonal session schedules. Historical effective periods, server-specific applicability, holiday closures, and DXYm hours remain unresolved.

**Partial resolution**: the prior repository finding (Section 3.2) establishes UTC+0 as the CSV export clock from internal data analysis. This resolves the clock-basis question at the `repository-verified (prior SDD analysis)` level. It does not substitute for authoritative broker documentation on session hours, holidays, DXY CFD schedules, or the experiment's expected coverage contract, all of which remain `unavailable`.

---

**(b) Historical weekly sessions and effective periods for each instrument**

| Aspect | Classification | Evidence |
|---|---|---|
| Mon–Fri trading week (all instruments) | `partial` — pattern consistent | Gap inventory confirms no regular trading on Sat–Sun; not confirmed by broker session documentation |
| Session open time — Monday first-bar timestamp | `partial` — pattern-inferred; not confirmed by broker documentation | Raw timestamp ~21:00 (summer-pattern period) / ~22:00 (winter-pattern period) in M15; per prior repository finding (UTC+0) these are UTC times, but the session schedule itself is not confirmed from broker documentation |
| Session close time — Friday last-bar timestamp | `partial` — pattern-inferred; not confirmed by broker documentation | Raw timestamp ~20:45 (summer-pattern period) / ~21:45 (winter-pattern period); per prior repository finding (UTC+0) these are UTC times, but the session schedule itself is not confirmed from broker documentation |
| Whether session hours changed between 2020 and 2026 | `unavailable` | Cannot be determined from timestamp patterns |
| EURUSDm/GBPUSDm vs DXYm session hour differences | `partial` — patterns appear similar | Gap inventory shows similar weekly delta distributions; not confirmed by broker documentation |
| Historical schedule for EURUSDm coverage period (protocol `start_utc` 2020-01-02 to `end_utc` 2026-08-19) | `unavailable` | Requires broker historical documentation; endpoint timestamps are interpreted as UTC per the prior repository finding, but are not independently frozen expected-coverage dates |
| Historical schedule for GBPUSDm coverage period (protocol `start_utc` 2020-01-02 to `end_utc` 2026-08-19) | `unavailable` | Requires broker historical documentation; same endpoint/coverage distinction |
| Historical schedule for DXYm coverage period (protocol `start_utc` 2021-10-27 to `end_utc` 2026-08-19) | `unavailable` | Requires broker documentation; DXYm CFD hours need separate confirmation; endpoint/coverage distinction as above |

---

**(c) Holiday schedules (calendar years covered by dataset)**

| Aspect | Classification | Evidence |
|---|---|---|
| Christmas/New Year closures visible in D1 gaps | `partial` | Three-day D1 gaps at Dec 22–25 and Dec 29–Jan 1 in 2022/2023/2024 are consistent with Christmas/New Year market closures; not confirmed as official broker closures |
| Dec 24 and Dec 31 early-close visible in H4 gaps | `partial` | Two H4 gaps end at raw timestamp 16:00 UTC instead of 20:00 under the prior repository finding in late Dec 2021; pattern-consistent with early-close days; sample size = 2; not confirmed against broker schedules |
| Complete holiday schedule for 2020–2026 | `unavailable` | Requires broker's published holiday calendar for each year of the coverage window |
| Good Friday, US Independence Day, Thanksgiving early-close | `unavailable` | Not visible in the D1 gap inventory (only two-day and three-day gaps listed; these would typically add single extra closure days without producing >1-day D1 gaps if session model is Mon–Fri) |

---

**(d) Seasonal / DST policy**

| Aspect | Classification | Evidence |
|---|---|---|
| Seasonal 1-hour shift in M15 weekly timestamp-delta distribution | `partial` — raw delta/date-pattern only | DXYm/M15 dominant weekly gap alternates between `2 days, 0:15:00` and `2 days, 1:15:00`; mode-transition dates coincide with US DST calendar dates (second Sunday of March / first Sunday of November per U.S. DOT rule: https://www.transportation.gov/briefing-room/news-digest-dot-28-16; establishes U.S. calendar rule only — does not establish the broker's clock, timezone, or causal mechanism); this is a raw date coincidence |
| Causal explanation for M15 1-hour gap-mode shift | `unavailable` — unexplained by prior repository finding | The prior UTC+0/no-server-DST finding rules out server-clock adjustment as the cause; a seasonal change in UTC session windows or another mechanism remains unproven |
| Whether server clock adjusts seasonally (broker server DST) | `repository-verified as absent` per prior finding | Prior finding concluded there is no DST adjustment on the export clock; this is not external broker documentation |
| Whether the 1-hour delta shift reflects seasonal changes in UTC session hours (blocking the current schema) | `partial` — consistent but not established; broker DST ruled out by prior finding | The shift is consistent with a seasonal change in UTC session open/close times (as opposed to server-clock DST); this remains the leading unresolved possibility; design draft marks calendars requiring seasonal variation as BLOCKED until confirmed and the temporal applicability contract is designed |
| Non-UTC path DST conversion algorithm | `unavailable` — BLOCKED by design | Design draft Section 2.4 identifies conversion circularity and unresolved policy for ambiguous/nonexistent local times; not resolved |

---

**(e) DXY CFD hours vs. FX session hours**

| Aspect | Classification | Evidence |
|---|---|---|
| DXYm M15 weekly gap mode distribution | `partial` | DXYm/M15 shows same alternating `0:15:00` / `1:15:00` pattern as EURUSDm/GBPUSDm; 16 `0:30:00` intra-week gaps and more varied anomalous gap types than FX pairs |
| DXYm H4 early-close pattern | `partial` | Two Dec 2021 gaps end at raw timestamp 16:00 UTC under the prior repository finding (same raw value as FX pairs), pattern-consistent with the same early-close schedule |
| Whether DXY CFD is traded on a separate session schedule from FX pairs | `unavailable` | Requires broker's published DXY CFD schedule; the US Dollar Index is published by ICE Futures, but broker CFD hours may differ from exchange hours |
| ICE Futures US Dollar Index official exchange hours | `unavailable` — not fetched | No ICE Futures documentation was fetched during this research session |
| Whether DXYm session hours were separately set by the broker | `unavailable` | Requires broker documentation |

---

**(f) MT5 bar alignment / partial bars / D1 rollover**

| Aspect | Classification | Evidence |
|---|---|---|
| Bar timestamp = period open time | `externally-verified` | MQL5 `MqlRates.time` documentation: "Period start time"; source `mql5.com/en/docs/constants/structures/mqlrates`, fetched 2026-09-15 |
| D1 bar raw timestamp is `T00:00:00` | `repository-verified (prior SDD analysis)` — interpreted as midnight UTC | All D1 raw timestamps are `T00:00:00`; under the prior UTC+0 export-clock finding, these are midnight UTC; external broker rollover documentation is absent |
| D1 bar's relationship to broker session rollover | `unavailable` | Timestamp interpretation does not establish the broker's documented D1 rollover or bar-grid alignment |
| Bar grid alignment (fixed UTC grid vs. session-open anchored) | `unavailable` | Not addressed in MQL5 documentation consulted; design draft marks this as a required external contract |
| Partial bars at session open | `unavailable` | Design draft Section 2.2 notes this is a design proposal whose broker confirmation is required before the expected-bar set can be validated against real data |
| MT5 standard export format timezone (server time vs. UTC conversion at export) | `repository-verified (prior SDD analysis)` — UTC+0 for these exports | The archived repository analysis supports UTC+0/no DST for these files; MQL5 documentation does not specify export conversion, and external broker documentation remains unavailable |

---

**(g) Experiment expected coverage contract**

| Aspect | Classification | Evidence |
|---|---|---|
| Experiment measurement cutoffs — `candidate_cutoff_end_utc: 2026-08-19T00:00:00Z` and `outcome_followup_end_utc: 2026-08-19T20:30:00Z` | `repository-verified` | Protocol JSON; independent protocol-defined constants with explicit Z values, not derived from CSV export timestamps; treated as UTC by the protocol's own definition; distinct from dataset file endpoint fields |
| Independently frozen expected dataset start per instrument/granularity | `repository-verified` — human-authorized contract | Common `expected_start = 2022-08-08` for all nine combinations; authorized 2026-09-16; not derived from observed endpoints |
| Independently frozen expected dataset end per instrument/granularity | `repository-verified` — human-authorized contract | Common inclusive `expected_end = 2026-08-19` for all nine combinations; protocol follow-up cutoff remains `2026-08-19T20:30:00Z` |
| Whether observed file endpoints may serve as proxy coverage contract | `repository-verified as prohibited` | Design draft Section 1.4 explicitly prohibits this; setting `expected_start/end` equal to `DatasetFileRecord.start_utc/end_utc` makes boundary truncation detection trivially pass |
| Discovery start dates declared in protocol (per instrument) | `repository-verified` | `dataset.discovery_start_by_instrument`: DXYm `2022-08-03`, EURUSDm `2022-07-26`, GBPUSDm `2022-07-27` |

---

## 6. Consolidated Gap Summary by Instrument

For completeness, the timestamp-only inventory totals (repository-verified, HEAD `90320b2`):

| File | Rows | Gaps above cadence | Dominant gap type |
|---|---|---|---|
| DXYm/D1 | 1,505 | 251 | 2-day gaps: 249; 3-day gaps: 2 |
| EURUSDm/D1 | 2,072 | 346 | 2-day gaps: 342; 3-day gaps: 4 |
| GBPUSDm/D1 | 2,072 | 346 | 2-day gaps: 342; 3-day gaps: 4 |
| DXYm/H4 | 7,746 | 256 | 2-day gaps dominant; 9 anomalous (varied delta sizes; cause unclassified) |
| EURUSDm/H4 | 10,680 | 350 | 2-day gaps dominant |
| GBPUSDm/H4 | 10,680 | 350 | 2-day gaps dominant |
| DXYm/M15 | 100,647 | 238 | 2-day gaps (two dominant delta modes); 0:30:00 intra-week: 16 |
| EURUSDm/M15 | 101,357 | 219 | 2-day gaps (two dominant delta modes); 0:30:00 intra-week: 2 |
| GBPUSDm/M15 | 101,257 | 219 | 2-day gaps (two dominant delta modes) |

Total: 2,575 gaps across all nine files (D1: 943, H4: 956, M15: 676). No OHLC values were inspected; all evidence is timestamp-only.

---

## 7. Findings on Design Readiness

### 7.1 UTC Constant-Schedule Path — Conditional Specification Status

The design draft's UTC-only, constant-schedule path is internally coherent as a design structure. Given a calendar with:
- `timezone = "UTC"`
- No DST rules (constant UTC session windows)
- No cross-midnight sessions (`close_day_offset = 0` only)

The `generate_expected_timestamps` algorithm is specified as deterministic **only conditional on** all of the following contracts being established: (1) the repository-supported UTC+0 interpretation of CSV timestamps is accepted for this dataset, with broker documentation still needed for authoritative confirmation; (2) bar-grid alignment at session boundaries is confirmed (fixed UTC grid vs. session-open anchored); (3) partial-bar semantics at session open/close are resolved; (4) the repository-supported D1 midnight-UTC timestamp interpretation is accepted, while its relationship to broker session rollover is clarified; and (5) a concrete verified calendar artifact exists with confirmed session hours and holiday schedule. Until the remaining contracts are resolved, `generate_expected_timestamps` produces a deterministic output *for a given calendar input*, but the calendar input itself is blocked (see Section 7.2), and the output cannot be validated as correct against real data. The fail-closed validator, calendar hash binding, and calendar artifact schema are coherent design structures. Tests in Sections 7.1, 7.2, 7.4–7.10 are implementable in isolation once a concrete calendar artifact exists, but acceptance against real data requires the calendar, alignment, and bar-boundary contracts above to be resolved first.

### 7.2 What Is BLOCKED in the Design

1. **Non-UTC calendar path** (Section 2.4): the prior repository finding supports UTC+0 exports with no server-clock DST, so a non-UTC conversion path is not supported for these dataset timestamps. The remaining external question concerns the broker's session schedule and whether its UTC session windows vary seasonally. If the design retains a general non-UTC path for other inputs, its conversion policy remains unresolved independently of this dataset finding.

2. **Seasonal session-timing variation** (Section 2.4): the M15 gap inventory shows a 1-hour dominant delta-mode shift at dates consistent with DST boundaries. The prior repository finding rules out server-clock adjustment as the cause; a UTC session-window shift or another mechanism remains unproven. The current `WeeklySession` schema has no temporal applicability fields. Until the cause and schedule-period applicability contract are established (Section 9, Decision 7), calendars that may require seasonal variation cannot be constructed.

3. **Cross-midnight sessions** (Section 2.4): whether any session crosses UTC midnight is unconfirmed (Assumption 1). The four sub-contracts required by Decision 8 have not been designed.

4. **DST Section 7.3 tests**: blocked pending non-UTC path resolution.

5. **Cross-midnight Section 7.11 tests**: blocked pending Decision 8 resolution.

6. **Experiment expected coverage contract** (Section 1.4): resolved by human authorization on 2026-09-16 as the common inclusive window `2022-08-08` through `2026-08-19` for all nine combinations. It remains separate from observed file endpoints and the protocol's hourly follow-up cutoff.

7. **Calendar artifact construction**: no calendar artifact can be created until broker identity, session timezone, session hours, holiday schedule, and DST policy are established from authoritative broker documentation.

---

## 8. Remaining Human Decisions Required

The following items require a human decision or human-verified external evidence before the design can proceed toward spec ratification:

1. **Broker identity and server name**: the actual broker whose MT5 server produced the EURUSDm, GBPUSDm, and DXYm datasets must be identified from the MT5 terminal's "Server" field or account records.

2. **Experiment expected coverage contract** (Design draft Decision 1b): resolved by human authorization on 2026-09-16 as `expected_start = 2022-08-08` and inclusive `expected_end = 2026-08-19` for every instrument/granularity pair. These dates are a pre-outcome data-selection decision and are not derived from observed file endpoints.

3. **Session timezone** (Design draft Decision 1a, Assumption 1): the prior repository finding (Section 3.2) concludes these CSV exports are UTC+0 with no DST, supporting the UTC-only path at the `repository-verified (prior SDD analysis)` level. External broker documentation confirming the session schedule's time basis is still absent. The EET/UTC+3 hypothesis is contradicted by the prior finding. The remaining question is whether session open/close times are constant in UTC year-round or shift seasonally (see item 5 below); broker documentation is needed for authoritative confirmation.

4. **Historical session hours** (Design draft Assumption 1): what were the exact open/close times (weekday + time + timezone) for each instrument during the coverage window? Requires broker documentation or MT5 server logs.

5. **Seasonal session-timing change mechanism** (Design draft Decision 7, Assumption 3): the M15 gap pattern shows a 1-hour mode shift at dates coinciding with US DST boundaries. The prior repository finding (UTC+0, no server-clock DST) rules out server-clock adjustment as the cause. The remaining candidate is a seasonal change in the broker's UTC session open/close times. If the UTC session windows shift seasonally, a temporal applicability contract must be designed before any calendar can be constructed; if they are constant, the current constant-UTC schema applies. Broker documentation confirming which applies is required.

6. **Holiday schedule** (Design draft Assumption 2): which specific dates in 2020–2026 did the broker declare full closures or early closes for each instrument? Requires the broker's published holiday calendar archives for each year.

7. **DXY CFD session schedule** (Design draft Assumption 4): does the broker's DXY CFD schedule differ from its FX pair schedule? Requires broker's published DXY CFD session times.

8. **D1 bar/session-rollover relationship** (Design draft Decision 5): the prior repository finding supports interpreting the raw D1 `T00:00:00` timestamps as midnight UTC. Broker documentation is still needed to confirm how that timestamp relates to the broker's daily session rollover; bar-grid alignment also remains unresolved.

9. **M15 anomalous gap classification** (Design draft Decision 6): what are the `0:30:00`, `0:45:00`, `1:00:00`, `1:30:00`, `2:15:00`, `3:15:00` intra-week gaps in DXYm/M15, and `0:30:00`, `1:00:00` in EURUSDm/M15? Requires broker session logs, MT5 server event records, or published broker notifications. Timestamp pattern inference is insufficient.

10. **Calendar vs. allowlist transition** (Design draft Decision 2): Option A (calendar fully replaces allowlist) vs. Option B (calendar supplements allowlist). Depends on evidence completeness, which cannot be assessed until items 4, 5, 6, 7, 8, 9 above are resolved.

11. **Protocol vs. manifest binding** (Design draft Decision 4): whether calendar references are added to the frozen protocol (requiring a new protocol amendment) or kept manifest-only. Human decision; the protocol is currently frozen at SHA-256 `192780eb571afc4fc690301b5ca7c68ec5e186426f55f443d8f226e6fa471f4f`.

12. **Cross-midnight session contract** (Design draft Decision 8): if Assumption 1 confirms any session crosses UTC midnight, the four sub-contracts in Section 2.4 must be designed before implementation.

---

## 9. Blockers Before Design Ratification

The design draft cannot be ratified (signed spec, implementation, real-data execution) until:

**Conservative decision authorized 2026-09-16:** because a complete auditable historical Exness schedule is not publicly available for `Exness-MT5Trial11` across the authorized window, no historical `SessionCalendar` artifact will be constructed or used for real-data validation at this stage. The calendar schema and synthetic-test design remain research artifacts only. The existing gap allowlist remains operative; replacing or supplementing it requires a separate authorized decision.

**Hard blockers** (no workaround within the current design):

- **B1**: Broker identity established (prerequisite for all session evidence gathering).
- **B2**: **Resolved** — independently frozen common coverage contract declared for all nine combinations: `2022-08-08` through `2026-08-19`, inclusive; cannot be derived from observed endpoints.
- **B3**: Broker documentation must establish the session schedule's time basis and whether it remains constant. The prior repository finding (Section 3.2) supports UTC+0 exports with no server DST; EET/UTC+3 is contradicted at the repository-evidence level, though not independently settled by broker documentation. If UTC sessions are constant, the current schema applies; if UTC session windows vary seasonally, a temporal applicability contract must be designed (Decision 7).
- **B4**: Historical session hours (open/close times, weekday schedule) verified for the full coverage window from broker documentation.
- **B5**: Holiday schedule verified from broker documentation for calendar years 2020–2026.
- **B6**: Seasonal session-timing mechanism confirmed. Prior repository finding rules out server-clock DST as the cause. Remaining question is whether the UTC session open/close windows shift seasonally (requiring a temporal applicability contract) or are constant in UTC (current schema sufficient). Requires broker documentation.

**Conditional blockers** (only if their trigger condition holds):

- **B7** (conditional on authoritative evidence requiring a non-UTC calendar): non-UTC conversion algorithm must be fully specified before `generate_expected_timestamps` can handle such calendars; the current repository finding does not support that path for these exports.
- **B8** (conditional on B6 confirming that UTC session windows shift seasonally): temporal applicability contract for `WeeklySession` must be designed before seasonally-varying calendars can be represented.
- **B9** (conditional on Assumption 1 — if any session crosses UTC midnight): cross-midnight session contract (Decision 8) must be designed.

**Pending design decisions** (not blocking calendar construction, but blocking spec signing):

- **D1**: Calendar vs. allowlist transition (Decision 2).
- **D2**: `gap_end` validation on existing allowlist path (Decision 3).
- **D3**: Protocol vs. manifest binding for calendar references (Decision 4).

---

## 10. Files Touched

Only this file was written:

- `openspec/changes/crt-detector-calendar-aware-gap-validation/evidence-report.md` (revised)

Files read (read-only, no modification):

- `openspec/changes/archive/crt-detector-htf-timezone-anchor/explore.md` — sourced the UTC+0/no-DST conclusion, methodology, and TradingView distinction
- `openspec/changes/archive/crt-detector-htf-timezone-anchor/triage.md` — sourced the closure record and the rejected UTC+3/EEST hypothesis origin

No other files were modified, executed, or committed. The signed statistical spec, protocol artifact, manifests, detector code, dataset files, baseline artifacts, authorization artifacts, checkpoint files, and tests are unchanged.
