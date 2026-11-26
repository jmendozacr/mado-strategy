# Deliverable F — Robustness & Selection Limitations

## Support

Both models clear the pre-registered minimum (20 events per subgroup, Phase 5's own
`MIN_COMMON_SUPPORT_PER_MODEL`) for the primary contrast, with considerable margin: 1AM's smaller
subgroup has 255 events, 9AM's smaller subgroup has 626. No group triggered
`INSUFFICIENT_STATISTICAL_EVIDENCE`.

## Heterogeneity

- **By instrument**: direction is consistent across all 3 instruments for both models (Deliverable
  E's per-instrument table) -- no instrument reverses the sign. AUDUSD, which showed heterogeneity
  in earlier phases' OTHER analyses, does not show it here: its own 1AM diff (+1.15pp) and 9AM
  diff (+3.17pp) sit squarely within the range the other two instruments show. This is reported
  plainly, in either direction, per the brief's explicit instruction not to hide AUDUSD's
  previously-observed heterogeneity -- here, there simply isn't any for this specific contrast.
- **By period**: Deliverable D's distribution table shows the confirmation-path composition
  itself is stable across all 4 periods for both models. A full period-by-period E1 contrast was
  not separately re-run (per the brief's "no combinatorial subgroup search" instruction) -- the
  instrument-level check above already demonstrates the direction is not driven by a narrow
  subset of the data.
- **By model**: THIS is where the real heterogeneity lives (Deliverable E's H2) -- 9AM's CI
  excludes zero, 1AM's does not, despite both pointing the same direction. This is the
  `MODEL_SPECIFIC_ASSOCIATION` pattern the pre-registered criteria (docs/79 section 5) were built
  to detect.

## Selection limitations (named explicitly, never papered over)

- **Stage-6/fill selection interacts with path complexity.** Deliverable E's composition table
  shows the zero-invalidation share drops from the confirmed population to the executed+evaluable
  population, for BOTH models (1AM: 73.0% -> 58.8%; 9AM: 56.1% -> 44.0%). Since Phase 9 proved
  100% of Stage-6 attrition is the RR floor alone, this means: **confirmed signals that needed at
  least one internal invalidation before confirming are, descriptively, more likely to survive the
  RR floor than signals that confirmed directly.** No mechanism is proposed or tested for this --
  it is reported as a selection fact relevant to interpreting Deliverable E's within-model
  contrast (the contrast is computed WITHIN the already-selected executed population, so this
  selection effect does not bias the contrast itself, but it does mean the EXECUTED population's
  own path-complexity composition is not representative of the CONFIRMED population's).
- **Session/feeder confounding is not ruled out.** As the brief itself cautions: common statistical
  support across the `internal_invalidation_count` groups does not establish that a 1AM
  zero-invalidation signal and a 9AM zero-invalidation signal are economically or structurally
  equivalent -- the two models' underlying feeder/session mechanics differ in ways Phase 8/9
  already characterized (different windows, different activation sub-windows, different
  confirmation-rate levels). This phase's within-model design (never comparing across models on
  the raw contrast) is specifically chosen to avoid conflating that confound with the
  path-complexity association -- but the STANDARDIZED cross-model gap (H3) still carries whatever
  residual confounding standardization-by-composition cannot remove.
- **Multiple testing was bounded by design, not by correction.** This phase tested exactly one
  pre-registered binary contrast per model (plus one descriptive standardization and one
  descriptive composition comparison) -- never a sweep over `internal_invalidation_count`
  thresholds, confirmation_elapsed_minutes bins, or any other correlated counter (docs/79 section
  2's explicit scope limitation). No correction for multiple comparisons was applied because none
  was needed under this design; a future phase introducing additional contrasts would need to
  address this explicitly.
- **2015-2026 remains previously examined**, not genuine out-of-sample data, for this finding as
  for every prior phase's.

## What would need to change before this association could inform anything predictive

A dedicated, separately-authorized phase would need to: (1) pre-register a held-out validation
window; (2) test whether the association survives under that holdout; (3) establish, if it does,
whether it adds information beyond what `risk_atr` and confirmation-window timing (already tested
and ruled out, Phases 5-7) jointly explain. None of that is attempted here.
