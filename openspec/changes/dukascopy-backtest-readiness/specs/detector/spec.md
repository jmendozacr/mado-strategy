# Delta for Detector

**Spec version**: V2
**Status**: signed
**Change**: `dukascopy-backtest-readiness`

## ADDED Requirements

None.

## MODIFIED Requirements

### REQ-30: Tradeable candidate population selection

The system MUST admit each aligned signal with a retest when its status is confirmed, invalidated, or pending, subject to REQ-50 fill simulation. It MUST reject signals without a retest, FVG-fill confirmations, and unaligned or insufficient-data signals. All admitted types share REQ-50's fill window from `retest_index`.

(Previously: every signal without a retest used one never-confirmed label.)

- **REQ-30.1**: GIVEN an aligned confirmed signal with a retest, WHEN candidates are built, THEN it is admitted under REQ-50.
- **REQ-30.2**: GIVEN an aligned invalidated signal with a retest, WHEN candidates are built, THEN it is admitted and may later be `excluded_never_filled`.
- **REQ-30.3**: GIVEN `retest_index` is absent, WHEN candidates are built, THEN none is created; a confirmed signal is `confirmed_no_retest`, while a signal that never confirmed is `never_confirmed`.
- **REQ-30.4**: GIVEN a confirmed FVG-fill signal, WHEN candidates are built, THEN none is created and it is `excluded_no_crt_range`.
- **REQ-30.5**: GIVEN a confirmed unaligned or insufficient-data signal, WHEN candidates are built, THEN none is created and it is `excluded_unaligned`.
- **REQ-30.6**: GIVEN an aligned pending signal with a retest, WHEN candidates are built, THEN it is admitted under the same REQ-50 fill window.

### REQ-33: Same-candle SL+TP tie-break

After entry activation, the system MUST resolve a candle reaching both SL and TP as a loss at SL. This includes the entry-fill candle and a simultaneous partial-profit touch, except for REQ-37.5's pre-entry opening. Each SL+TP case MUST be disclosed. After the fill candle, level precedence is decided before REQ-34 gap handling.

(Previously: the SL-wins tie-break applied only after the entry-fill candle.)

- **REQ-33.1**: GIVEN an open trade and a candle reaches both SL and TP, WHEN resolved, THEN it loses at SL and is marked ambiguous.
- **REQ-33.2**: GIVEN four trades resolved through the SL+TP tie-break, WHEN the summary is produced, THEN it reports exactly four same-candle SL+TP resolutions.
- **REQ-33.3**: GIVEN an open trade and a candle opens beyond TP but reaches SL, WHEN resolved, THEN it loses at SL and is not a gap fill.
- **REQ-33.4**: GIVEN the entry-fill candle reaches both SL and TP, WHEN resolved, THEN it is an immediate loss at SL and is disclosed as a same-candle SL+TP resolution.
- **REQ-33.5**: GIVEN the entry-fill candle reaches both SL and a partial-profit level, WHEN resolved, THEN it is an immediate full loss at SL and no partial profit is credited.

### REQ-37: No-lookahead simulation entry point

Entry and exit resolution MUST use only available candle data. Fill search MAY begin at `retest_index` for every admitted candidate. The fill candle MUST evaluate SL exposure only: SL means immediate loss; TP or partial-profit without SL earns nothing. Favourable-exit evaluation MUST start on the following candle. An opening beyond SL before entry MUST NOT create a loss merely because entry is reached later.

(Previously: all SL/TP evaluation began on the candle after fill, so fill-candle SL touches were ignored.)

- **REQ-37.1**: GIVEN confirmation follows `retest_index` by up to six candles, WHEN simulated, THEN fill search begins at `retest_index`, not after confirmation.
- **REQ-37.2**: GIVEN an invalidated-with-retest or pending-with-retest candidate, WHEN simulated, THEN fill starts at `retest_index`, fill-candle evaluation is SL-only, and normal exits start next candle.
- **REQ-37.3**: GIVEN an entry-fill candle whose range reaches SL, WHEN resolved, THEN it closes as an immediate loss on that candle, including when SL equals the candle's extreme.
- **REQ-37.4**: GIVEN an entry-fill candle reaches TP or a partial-profit level but not SL, WHEN evaluated, THEN no favourable exit is credited and favourable-exit evaluation starts on the following candle.
- **REQ-37.5**: GIVEN a prospective entry whose fill candle opens beyond SL before later reaching entry, WHEN the candle is evaluated, THEN the opening excursion is not recorded as a loss and no pre-entry position is inferred, even though the candle's range contains SL.
- **REQ-37.6**: GIVEN a prospective entry whose fill candle opens exactly at SL and reaches entry, WHEN the candle is evaluated, THEN the strict beyond-SL exception does not apply and the trade is an immediate loss at SL.

### REQ-40: Population-reconciliation report

The system MUST reconcile the post-filter `signals_considered` population. Each signal MUST land in EXACTLY ONE of `trades_opened` or, in precedence order: `excluded_no_crt_range`, `excluded_unaligned`, `confirmed_no_retest`, `never_confirmed`, `excluded_no_key_level`, `excluded_duplicate`, `excluded_kill_zone`, `excluded_rr_floor`, `excluded_never_filled`. Confirmed without retest belongs only to `confirmed_no_retest`; neither confirmation nor admissible retest belongs only to `never_confirmed`. `excluded_no_key_level` remains its own independent terminal category, unaffected by this split.

(Previously: signals without a retest were all described as never confirmed.)

- **REQ-40.1**: GIVEN any backtest run, WHEN reconciled, THEN `trades_opened + sum(all 9 exclusion buckets) == signals_considered`, exactly.
- **REQ-40.2**: GIVEN a filter narrows the population, WHEN reconciled, THEN `signals_considered` equals the filtered count, not the raw detected count.
- **REQ-40.3**: GIVEN a signal is both unaligned and outside the kill zone, WHEN reconciled, THEN it lands only in `excluded_unaligned`.
- **REQ-40.4**: GIVEN a pending signal has a retest, WHEN candidates are built, THEN it is admitted and lands in one stage 4-7 terminal result, never silently dropped.
- **REQ-40.5**: GIVEN a signal confirmed but received no retest, WHEN reconciled, THEN it is counted only in `confirmed_no_retest`, never `never_confirmed`.
- **REQ-40.6**: GIVEN a signal neither reached confirmation nor produced an admissible retest, WHEN reconciled, THEN it is counted only in `never_confirmed`, never `confirmed_no_retest`.
- **REQ-40.7**: GIVEN one confirmed-no-retest signal, one never-confirmed signal, and one opened trade, WHEN reconciled, THEN each increments its distinct terminal result once and REQ-40.1 equality holds exactly.

### REQ-68: Two-stage partial exit detection and resolution

For each trade reaching exit resolution, the system MUST compute the midpoint between its entry and TP as the partial-profit level. On the fill candle, SL alone is eligible: an SL touch produces a single-leg loss, while a partial or TP touch without SL is ignored. From the following candle, partial, SL, and TP resolve normally; SL wins a same-candle tie with partial. A partial closing strictly before SL closes the configured fraction, then the remainder keeps the original SL and TP from the next candle. A zero partial fraction MUST preserve single-leg results.

(Previously: partial, SL, and TP searches all began after the fill candle, so fill-candle SL was ignored.)

- **REQ-68.1**: GIVEN partial resolves before SL and the remainder later reaches TP, WHEN resolved, THEN both exits are recorded at their respective candles.
- **REQ-68.2**: GIVEN partial resolves before SL and the remainder later reaches the original SL, WHEN resolved, THEN the unchanged SL closes the remainder.
- **REQ-68.3**: GIVEN the fill candle reaches SL and partial, or a later candle reaches both together, WHEN resolved, THEN SL wins, the trade is a single-leg loss, and no partial is recorded.
- **REQ-68.4**: GIVEN a post-fill partial-resolution candle opens beyond the partial level, WHEN resolved, THEN the partial fills at that opening price under REQ-34.
- **REQ-68.5**: GIVEN the partial fraction is zero, WHEN resolved, THEN the trade is identical to single-leg resolution.
- **REQ-68.6**: GIVEN no eligible post-fill exit level is reached by series end, WHEN resolved, THEN the trade remains open with no partial leg.

## REMOVED Requirements

None.

## Design Inputs

- Migrate both reconciliation labels across metrics and published text.
- On the fill candle, evaluate only adverse SL exposure, not all exits.

## Sensitive Areas Coverage

No sensitive behaviour is changed. This delta affects historical research only and does not place or manage orders.
