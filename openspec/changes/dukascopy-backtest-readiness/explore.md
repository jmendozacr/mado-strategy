# Exploration: Dukascopy Backtest Readiness

**Triage**: L  
**Persona lens**: architect

## Cross-Change Lessons Consulted

- Dukascopy preflight and replay records (#685, #686, #687, #691) establish hashed inputs, DST/identity rules, a research-only seam, and a byte-identical exploratory statistics replay.
- The archived backtest reckoning records that `never confirmed` is a disclosure defect at real scale, while admission logic remains correct.
- No additional matching pattern, discovery, or bugfix memories were found. CodeGraph was unavailable (`gentle-ai` has no `codegraph` command), so investigation used targeted `rg` and direct reads.

## Affected Flows

| Flow | Current E2E spec | Expected action |
|---|---|---|
| Produce canonical backtest outputs | `detector/tests/test_cli_backtest_e2e.py` | Modify |
| Run retained EURUSD/GBPUSD Dukascopy experiment | `research/dukascopy_eurusd_gbpusd/tests/test_seam.py` | Modify |
| Verify reproducible two-pair evidence | none found | Create |

## Current State

Main already contains the bounded Dukascopy experiment through merged PRs #4–#16; `dukascopy-eurusd-gbpusd-experiment` is an older divergent branch, not unadopted work. The retained outcome and replay are reproducible statistics receipts, not a corrected canonical backtest run. Provider data is normalised in `research/dukascopy_eurusd_gbpusd/adapter.py`, validated by `manifest.py`, and passed through `seam.py` into production pure functions; no versioned runner command reconstructs the full run.

`backtest/population.py` assigns every `retest_index is None` signal to `excluded_never_confirmed`, although Model-1 can be confirmed and merely never retested. `backtest/simulate.py` intentionally begins SL/TP resolution at `fill_index + 1`; therefore stop touches on the fill candle are ignored without a report disclosure. `viz/trades_table.py` publishes both misleading omissions.

## Architecture Touchpoints (A3)

| Layer/Component | Action | Why | Baseline fit |
|---|---|---|---|
| backtest population/metrics | modify | Correct canonical reconciliation and disclosure ownership | aligns |
| viz trades report | modify | Surface corrected labels and fill-candle exposure | aligns |
| research Dukascopy ingress/run seam | extend | Deterministic two-pair command and receipt | deviates |

The baseline describes `detector/` only, while the already-merged research seam is now material; refresh the baseline during design or post-verify. The research entry point needs an ADR preserving the rule that production never imports provider-specific code.

## Affected Areas

| Path | Impact | Why |
|---|---|---|
| `detector/backtest/population.py` | Modify | Split/rename the no-retest disclosure |
| `detector/backtest/simulate.py` | Modify | Measure fill-candle stop exposure without changing execution semantics |
| `detector/backtest/metrics.py` | Modify | Carry the disclosure metric |
| `detector/viz/trades_table.py` | Modify | Render honest summary text |
| `detector/tests/test_backtest_{population,simulate,metrics}.py` | Modify | Pin canonical semantics |
| `detector/tests/test_cli_backtest_e2e.py` | Modify | Pin published output |
| `research/dukascopy_eurusd_gbpusd/` | Modify/Create | Reproducible orchestration using the existing adapter, manifest, streaming, and seam |
| `openspec/explore/dukascopy-*-receipt-*.md` | Create | Retain hashes, configuration, command, and results |

## Sensitive Areas Crosscheck

No registered sensitive paths are required. The research manifest is experiment provenance, not production data ownership or an authorisation control. No broker, order, payment, privacy, or deployment behaviour changes.

## Approaches

### 1. Canonical fixes plus research-only runner
Correct disclosure at its canonical owners, add a thin deterministic research command over existing modules, and retain a hashed receipt. **Pros**: honest all-callers semantics; repeatable; preserves dependency direction. **Cons**: introduces one executable research component. **Effort**: Medium. **Pattern fit**: hybrid; detector changes align, runner is outside the baseline.

### 2. Convert files then invoke the production CLI twice
**Pros**: reuses an existing entry point. **Cons**: duplicates provider conversion/provenance, cannot naturally enforce the frozen two-pair manifest atomically, and risks coupling research rules to MT5-shaped ingress. **Effort**: Medium. **Pattern fit**: poor at the ingress boundary.

### 3. Repeat the prior manual execution and document it
**Pros**: least code. **Cons**: the missing versioned orchestration remains, so another operator cannot reproduce the run from a command. **Effort**: Low. **Pattern fit**: insufficient for the stated outcome.

## Recommendation

Use approach 1. Keep provider-specific loading and orchestration under `research/`, call the existing production pure functions inward, and fix reporting only in canonical backtest owners. Do not merge the stale experiment branch wholesale.

## Risks

- Changing a reconciliation field can break literal report contracts; treat it as an explicit output-contract migration.
- Fill-candle disclosure must not silently change the established `fill_index + 1` execution rule.
- External raw files may be absent; the runner must fail closed on paths/hashes rather than fabricate evidence.
- Existing receipts prove a different statistical outcome; they must not be presented as the new corrected backtest.

## Open Questions

- type: technical
  question: "Should the corrected no-retest bucket be one renamed bucket or separate confirmed-no-retest and genuinely-unconfirmed buckets?"
  why_it_matters: "This fixes the public reconciliation contract and determines migration compatibility."

## Ready for Proposal

**Status**: yes  
**Reason**: The implementation boundaries and preferred approach are clear; the remaining bucket shape is a reversible design decision.  
**Recommended action**: Proceed to proposal, explicitly replacing “merge the branch” with “verify already-adopted scope, then add the missing reproducible backtest path.”
