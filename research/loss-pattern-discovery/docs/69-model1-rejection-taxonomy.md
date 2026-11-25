# Deliverable B — Model-1 Rejection Taxonomy

Reproduce: `uv run --project detector python research/loss-pattern-discovery/extract/funnel_reconstruction.py`
(writes the taxonomy counts alongside the funnel reconstruction). Full code citations and the
structural proof below are in `docs/67-phase9-design-and-pre-registration.md` section 1 and
`extract/model1_rejection_diagnostics.py`'s own module docstring.

## The 10 questions (Unit B), answered from source

1. **Anchor found when**: `causal_anchor_v2.find_first_valid_anchor` -- candle `j`'s own
   high/low breaks an earlier candle `i`'s own high/low (per direction), with no candle strictly
   between `i+1` and `j-1` having already broken it, within a 20-candle age-bounded lookback.
2. **Anchor NOT found when**: no such `(i, j)` pair exists anywhere the search is allowed to look
   (bounded by the window AND the 20-candle lookback) -- OR the retry chain (below) runs out of
   room before ever engulfing.
3. **Engulf** (`entries/model1.py::_track_anchor`): a candle's close breaks beyond the ANCHOR
   candle's own body (`_closes_beyond`, direction-specific).
4. **Retest**: after engulfing, the first candle whose wick overlaps the anchor's body range marks
   `retest_index`; retest COMPLETES when a later candle's close breaks beyond that retest candle's
   own OPEN.
5. **Confirms when**: engulf AND retest both complete within the window -> `DetectionStatus.CONFIRMED`.
6. **Stays PENDING when**: engulfed (and possibly retest-touched) but the window's own `window_end`
   is reached before retest completes.
7. **Invalidates when**: a candle closes beyond the anchor's PROTECTED extreme (the opposite side
   from the engulf side) before retest completes -- but see finding below: this is NEVER the
   pipeline's own terminal outcome.
8. **At window end**: `_track_anchor`'s own loop simply stops; unconfirmed-and-engulfed ->
   PENDING; never-engulfed -> `None`.
9. **Can a trigger invalidate before ever confirming?** Yes, internally, routinely -- but
   `causal_anchor_v2.confirm_in_ltf_window_v2`'s own retry loop ALWAYS retries from the
   invalidation point as a new anchor, so INVALIDATED is never visible outside that function.
10. **120 vs. 240 minutes**: only the SEARCH BUDGET changes -- same rules, same age-bounded anchor
    lookback (20 candles, independent of window length), same engulf/retest logic. A longer window
    gives more candles (up to ~16 M15 bars for 9AM's 240min vs. ~8 for 1AM's 120min) for the SAME
    unchanged retry chain to keep re-attempting after an invalidation.

## Structural finding, verified both analytically and empirically

**`"model1_pending_or_invalidated"` is a misnomer for D3: it is ALWAYS `PENDING`, never a terminal
`INVALIDATED`**, because `confirm_in_ltf_window_v2`'s own retry loop (`while True: ...; if result is
None or result.status != INVALIDATED: return result`) can structurally never return INVALIDATED --
proven by code trace AND by a deterministic test using the real, unmodified functions on a
hand-built candle sequence that invalidates internally at least once before resolving
(`tests/test_model1_rejection_diagnostics.py`).

## Full taxonomy, by model (sum of EURUSD + USDCAD + AUDUSD; reconciles exactly to the user's
## stated baseline)

| | 1AM | 9AM |
|---|---|---|
| Triggers with Key Level | 11206 | 8712 |
| Model-1 confirmed | 1805 (16.1%) | 3311 (38.0%) |
| `no_model1_anchor_found` | 4634 (41.3%) | 1932 (22.2%) |
| `model1_pending_or_invalidated` (= always PENDING) | 3464 (30.9%) | 3469 (39.8%) |
| `window_empty_before_search` | 1303 (11.6%) | **0 (0.0%)** |

Identity check: `confirmed + sum(rejections) == triggers` holds exactly for both models (1805+9401=11206;
3311+5401=8712).

**9AM NEVER shows `window_empty_before_search` (0 of 8712), while it accounts for 11.6% of 1AM's
triggers.** This is a direct, mechanical consequence of the two models' different activation/
confirmation window relationship: 9AM's activation sub-window (09:00-11:00 NY) closes well before
its confirmation window (09:00-13:00 NY, 240min) -- `eligible_start = max(window_start,
activation_instant) < window_end` essentially always holds given the 2-hour buffer. 1AM's single,
shorter 120-minute window gives activation (which can occur anywhere within it) much less room
before the SAME window's own close -- so `eligible_start >= window_end` is reachable far more often.

## Anchor-probe disambiguation within `no_model1_anchor_found`

| | 1AM | 9AM |
|---|---|---|
| `zero_anchors_ever` (no anchor existed on the first search) | 622 (13.4% of `no_anchor_found`) | 19 (1.0%) |
| `anchor_found_but_chain_exhausted` (an anchor existed, engulf/retest never completed) | 4012 (86.6%) | 1913 (99.0%) |

**For both models, the large majority of "no anchor found" cases DID find at least one anchor** --
the retry chain simply exhausted its available window before ever engulfing. This is a materially
different picture from "no anchor ever existed": most of 1AM's `no_model1_anchor_found` triggers
had SOMETHING to work with, just not enough room to complete the sequence. Scope limitation,
stated plainly: this probes only the FIRST `find_first_valid_anchor` call, not every intermediate
anchor the retry chain itself cycles through after each invalidation.
