# Spec: crt-detector-bias

**Version**: V1 | **Status**: signed | **Change**: `crt-detector-bias`
**Derived from**: `sdd/crt-detector-bias/semantic-research` (three closed design passes, 2026-09-08) + `triage.md` (council convergence, S, layer + simplification decisions).

## Domain: bias-evidence-detection

### REQ-BIAS-01: Close-relation partition
`close_relation` MUST be `"above"` iff `current.close > previous.high`; `"below"` iff `current.close < previous.low`; `"inside"` otherwise (both boundaries inclusive).
**Source: MENTORSHIP** (charter-3 `[00:02:03]`, close relative to the previous candle; "Close Inside" explicitly anchors the third branch to the previous **range**) **+ DESIGN DECISION** (Above/Below read against `previous.high`/`previous.low` rather than `previous.close` or `previous.open` — the only reading that keeps the three branches a strict, exhaustive partition; `previous.close`-based readings collide with "inside" — e.g. `previous={O:102,H:110,L:100,C:105}`, `current.close=107` is simultaneously "above previous.close" and "inside the previous range").
- **REQ-BIAS-01.1** (happy): GIVEN `previous={H:110,L:100}`, WHEN `current.close=115`, THEN `close_relation="above"`.
- **REQ-BIAS-01.2** (edge, boundary equality): GIVEN `current.close == previous.high` (or `== previous.low`), WHEN evaluated, THEN `close_relation="inside"` — a closed range includes its own edges; breaking out requires strictly exceeding it. Consistent with this repo's existing boundary convention (`REQ-OF-03.1`: exact equality is not a break).
- **REQ-BIAS-01.3** (edge, flat previous candle): GIVEN `previous.high == previous.low` (a degenerate point range), WHEN evaluated, THEN the same partition applies without modification — `inside` is possible only at `current.close == previous.high == previous.low`.

### REQ-BIAS-02: Close-derived signal
`close_signal` MUST be `"bullish"` when `close_relation="above"`; `"bearish"` when `close_relation="below"`; when `close_relation="inside"`, `"bullish"` if `current.close > current.open`, `"bearish"` if `current.close < current.open`, and `None` if `current.close == current.open` (flat/doji body).
**Source: MENTORSHIP** (Above/Below directional claims; Inside's own body-colour continuation rule — "una vela bajista sugiere continuidad a la baja y una alcista sugiere continuidad al alza") **+ DESIGN DECISION** (doji fallback to `None` — the source names only "bajista"/"alcista" velas, never a flat one; this repo has an existing doji carve-out precedent at `entries/model1.py` REQ-47.4, pinned deterministically in `test_backtest_levels.py` — same category of decision, not a novel one).
- **REQ-BIAS-02.1** (happy): GIVEN `close_relation="above"`, THEN `close_signal="bullish"`.
- **REQ-BIAS-02.2** (happy): GIVEN `close_relation="inside"` AND `current.close > current.open`, THEN `close_signal="bullish"`.
- **REQ-BIAS-02.3** (edge, doji): GIVEN `close_relation="inside"` AND `current.close == current.open`, THEN `close_signal=None`.

### REQ-BIAS-03: Wick-derived signal
`wick_signal` MUST be `"bearish"` when only an upper wick is present; `"bullish"` when only a lower wick is present; `"conflict"` when both are present; `None` when neither is present. Wick presence: `upper_wick_present = current.high > max(current.open, current.close)`; `lower_wick_present = current.low < min(current.open, current.close)` — categorical existence, no magnitude parameter. `upper_wick_present`/`lower_wick_present` are NOT exposed as separate fields on `BiasEvidence` — they are a bijection of `wick_signal` (4 boolean-pair states ↔ 4 signal values, both directions recoverable) and add no information beyond it (triage.md, Simplification finding).
**Source: MENTORSHIP** (the two directional claims: "una mecha superior indica precios más bajos; una mecha inferior sugiere precios más altos") **+ DESIGN DECISION**, explicitly corrected from an earlier pass: the categorical (no-threshold) existence test is a minimal operationalization chosen because the source supplies no magnitude parameter — it is NOT itself a mentorship-taught zero-threshold rule. The `"conflict"`/`None` labels for the both-present/neither-present cases are DESIGN DECISION — the source states the two claims independently and never addresses simultaneity or absence.
- **REQ-BIAS-03.1** (happy): GIVEN only an upper wick, THEN `wick_signal="bearish"`.
- **REQ-BIAS-03.2** (happy): GIVEN only a lower wick, THEN `wick_signal="bullish"`.
- **REQ-BIAS-03.3** (edge, both wicks — NOT resolved to a direction): GIVEN both an upper and a lower wick, THEN `wick_signal="conflict"`.
- **REQ-BIAS-03.4** (edge, no wicks / flat candle): GIVEN `current.high == max(open,close)` AND `current.low == min(open,close)`, THEN `wick_signal=None`.
- **REQ-BIAS-03.5** (edge, minimal non-zero wick): GIVEN a wick of any strictly-positive size, however small, THEN it counts identically to a large wick — no magnitude threshold exists to distinguish them (source gives no comparative language to do so).

### REQ-BIAS-04: No cross-signal arbitration
`BiasEvidence` MUST expose `close_signal` and `wick_signal` as independent fields; no field combines them into a single final direction, confidence, or weight.
**Source: DESIGN DECISION** — charter-3 `[00:02:03]`'s own closing line ("esto es solo una confluencia... no una regla absoluta") states the two claims are inputs, not a resolved verdict, and supplies no combination policy (no "close wins", no majority, no weighting). Inventing one would add semantics the mentorship does not give.
- **REQ-BIAS-04.1** (edge, disagreement preserved): GIVEN `close_signal="bullish"` AND `wick_signal="bearish"` (or the mirror), THEN both are recorded as-is on the same `BiasEvidence` — no field resolves the disagreement.

### REQ-BIAS-05: No semantic horizon
`BiasEvidence` carries `observation_index` only — no `target_index`, and no field or docstring asserts which future candle (if any) the evidence applies to.
**Source: DESIGN DECISION**, forced by source ambiguity. Re-audited against charter-3's immediate context: the passage's intro ("vela actual", "la vela que estamos operando... leyendo la estructura OHLC/OLHC") points to the candle under evaluation itself; the Above/Below bullets explicitly and repeatedly say "en la siguiente vela" (next candle); the Inside and Wick bullets do not repeat that phrase; the two worked examples (`[00:10:32]`, `[00:14:47]`) both use present-tense "vela actual" framing. Genuinely ambiguous within the same passage — not resolved by assumption.

### REQ-BIAS-06: No-lookahead / timeframe-agnostic
`detect_bias_evidence(series.up_to(n))` MUST match the full-series output for every `BiasEvidence` whose `observation_index` is `< n`. `detect_bias_evidence` accepts a generic `OHLCSeries` and never branches on `.timeframe`.
**Source: REPO CONVENTION** (mirrors `REQ-OF-05`/`REQ-OF-06`). Settling constant `k=0` — evidence at index `i` depends only on candles `i-1` and `i`, the strictest variant in `tests/property/test_no_lookahead.py`'s existing family (current minimum `k=1`).

### REQ-BIAS-07: Input/output cardinality
For a series of `N` candles: `N < 2` → `[]` (no previous candle exists to compare against — in particular, index `0` never produces a `BiasEvidence`); `N >= 2` → exactly one `BiasEvidence` per index `1..N-1`.
**Source: DESIGN DECISION** — direct consequence of REQ-BIAS-01 requiring a previous candle; Bias is a per-candle evidence read (not a rare-event detector), so no candle in range is skipped.
- **REQ-BIAS-07.1** (edge): GIVEN `N=0` or `N=1`, THEN `detect_bias_evidence` returns `[]`.
- **REQ-BIAS-07.2** (edge): GIVEN `N=2`, THEN exactly one `BiasEvidence` is returned, at `observation_index=1`.

## Out of scope (explicit, per triage)

`direction`/`confidence`/`score`/`weight`/`target_index`/`expiry`/state fields; Bias's own horizon interpretation (left ambiguous, REQ-BIAS-05); Turtle Soup, Breaker, OTE, Kiss of Death, Model-1, TSQ phases ("TSQ/OHLC Path Model" — separate concept, `DEFERRED — SOURCE RECONCILIATION REQUIRED`); `DirectionContext`; Draw on Liquidity; `BiasConfig` (no discretionary parameter exists to hold — triage.md Config decision); any outcome/statistics work (WR, MeanR, PF, backtest, ablation, OOS) — this spec is not evaluated by predictive performance.

## Proposed type (not yet implemented)

```python
@dataclass(frozen=True)
class BiasEvidence:
    observation_index: int
    close_relation: Literal["above", "below", "inside"]
    close_signal: Literal["bullish", "bearish"] | None
    wick_signal: Literal["bullish", "bearish", "conflict"] | None


def detect_bias_evidence(series: OHLCSeries) -> list[BiasEvidence]: ...
```

Location: `detector/primitives/bias.py` (triage.md Layer decision — imports only `core.candle`, matching the `primitives` layer contract).

## Revision History

- 2026-09-08 (draft V1): derived from the closed 3-pass semantic-research thread and council triage (S, architect+pm convergent). Pending human sign-off before TDD implementation.
- 2026-09-08 (sign-off): V1 signed as-is, no changes requested. Proceeding to TDD implementation.
