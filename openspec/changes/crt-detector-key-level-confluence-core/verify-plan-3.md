## Plan Verify Result

**Change**: crt-detector-key-level-confluence-core
**Iteration**: 3/3 (final budgeted)
**Mode**: plan
**Write mode**: n/a — `spec_source: internal`, ticket bodies not composed

---

### Verdict: ready

Scope check clean (orchestrator, mechanical): every `in_scope` item from the triage artefact traces to ≥1 REQ-ID and ≥1 slice; nothing in signed spec V3 or slices V3 exceeds `out_of_scope` (Swing, source-attribution column, tolerance parameter, ICTOrderBlock/BreakerBlock/RejectionBlock detectors, partial exits — all correctly absent).

Blind executor judge (opus, anti-anchoring, spec+design+slices only): **"Ready to execute."** Zero blocking questions. Verified two hard preflights directly against the repo: `pairs/H4/`+`pairs/M15/` hold all three instruments; `git diff f44b2c4..HEAD -- detector/` is empty, confirming design §8.5's premise that obs #419 still describes HEAD. Independently re-derived the W-band arithmetic (142984 − 17143 − 20780 = 105061; 41160/105061 = 0.392 cap) and confirmed it now matches design §9.1.

Orchestrator action: proceed directly to `/build --scope=skeleton` (Step 8b publish skipped — `spec_source: internal`).

### Non-Gating Execution Notes

| Type | Note | Owner/timing |
|---|---|---|
| **executor-local (surface this to whoever builds S-000.7/S-004)** | **`--types model1` bypasses the gate as designed.** `viz/table.py:51-56` and `viz/chart.py:92-95` render Model-1 rows from `aligned_signals` when non-None, **else fall back to `model1_signals`**. `_filter_by_types` sets `aligned_signals=None` for `--types model1` while leaving `model1_signals` populated — so the design's `_filter_to_confluent` predicate (defined over `AlignedSignal` only) narrows nothing observable in that mode. Gated rows/markers leak, violating REQ-56.2. Spec already settles the desired behaviour (Out of Scope: "the gate applies uniformly regardless of flags") — no decision needed, just an implementation gap the design's interface contract (§6) never named. **16 of 18** `_run_backtest` calls in `test_cli_backtest_e2e.py` use `--types model1`; `--types alignment` appears in **no** e2e test — so the planned suite would go green while exercising the leaky path almost exclusively. Fix: narrow `model1_signals` alongside `aligned_signals` in `_filter_to_confluent`, guarded on `aligned_signals is not None` (keeps single-series/REQ-56.6 untouched), plus one new `--types model1` gate assertion — no current slice task covers it. Judge's own classification: not blocking (spec already resolved the *what*; this is *how*, and unambiguous) — but real enough to name explicitly rather than bury in a general note. | S-000.7 (implementation) / S-004 (add the missing assertion) |
| executor-local | REQ-53.4's literal wording ("imports only core.key_level, never any other detector module") is unsatisfiable against existing code — the frozen allow-list in design §8.4 is current imports + `core.key_level`, not a single-entry set. | S-005.6 |
| build-preflight | Run `cd detector && uv run pytest` green before S-000 starts — not independently verified this pass (`uv` not on PATH in the judge's shell). | before S-000 |
| non-gating, spec-text only | REQ-59.2's explanatory tail overreaches: it claims earlier-cut signals' CSV presence is "unaffected by confluence outcome," but the CSV gate has no never-confirmed carve-out — flipping such a signal's `key_level` *would* change CSV presence (only its bucket membership is unaffected). The normative scenario body is correctly scoped; don't assert the tail. | S-005.5 test author |
| non-gating, spec-text only | REQ-57.3 still reads as an absolute anchor ("rows an equivalent run produced before this change") — harmless here (`--types fvg` can't reach the gate) but should be written as a pinned expected-value assertion, not a pre/post diff, to avoid ADR-016's exact trap resurfacing. | S-004.5 test author |
| informational | `.importlinter` cannot express SEAM-01 (`cli` isn't a root package; no allow-list contract type) — confirms design §8.4's AST-based mechanism is the only viable approach, not a shortcut. | S-005.6, confirmed not a gap |

**Repo hygiene note (resolved before this artefact was persisted)**: design.md and slices.md were uncommitted at judge review time; committed at `7484b94` immediately after.

### Iteration History

| Iteration | Verdict | Findings |
|---|---|---|
| 1 | gaps | 16 (1 empirical, 1 self-contradiction, 2 fixture-breaking) — routed to spec V2/design V2 |
| 2 | gaps | 12 + 1 user-mandated criterion — routed to spec V3/design V3/slices V3 |
| 3 | **ready** | 0 blocking; 6 non-gating notes carried into build context above |
