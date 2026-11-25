# Deliverable C — Failure Mode Taxonomy

Implementation: `failure_modes/taxonomy.py`. Three independent dimensions -- never collapsed into
five mutually-exclusive labels (confirmed combinable in practice: `docs/26-...`'s cross-tab shows a
"slow" failure can be `material`, `partial`, or `none` excursion, never forced into one bucket).

## Dimension 1 — Duration

Reported as a **continuous** distribution (median 6 bars, P10=1, P90=45 -- `docs/24-...`). The only
duration-related category used anywhere is `n_observable_bars == 0`, a data-integrity fact (feeds
Dimension 3), not a chosen cut. `duration_tercile_labels()` produces purely descriptive percentile
bins (`fast_tercile`/`mid_tercile`/`slow_tercile`) of THIS sample's own distribution, used only to
make the cross-tab in `docs/26-...` readable -- never to threshold, select, or filter any other
result, and never claimed as a natural category.

## Dimension 2 — Favorable excursion before SL (`ExcursionClass`)

| Class | Range | Justification |
|---|---|---|
| `none` | `mfe_pre_sl_r < 0.25R` | reuses `CONTINUATION_REVERSAL_THRESHOLD_R`, already pre-registered in Phase 2/3 for an unrelated purpose |
| `partial` | `0.25R <= mfe_pre_sl_r < 1.0R` | upper bound = the position's own risk distance, a structural unit |
| `material` | `mfe_pre_sl_r >= 1.0R` | same structural unit |
| `unknown` | path not `RECONSTRUCTIBLE`, or risk invalid | never guessed |

Neither cut point was chosen by inspecting which split best separates any outcome; both are reused
or structural units fixed before this phase's first real-data run (`docs/22-...`).

## Dimension 3 — Path integrity

`RECONSTRUCTIBLE` / `AMBIGUOUS` / `INSUFFICIENT` -- purely structural (how many bars exist between
entry and exit), not a statistical choice. See `docs/24-...` for the exact counts.

## Why these are independent, not exclusive

`failure_modes.taxonomy.FailureModeClassification` carries `duration_bars`, `excursion_class`, and
`integrity` as three separate fields on the same record. `tests/test_failure_mode_taxonomy.py::
test_dimensions_vary_independently_not_as_one_exclusive_label` constructs a fast+no-excursion case,
a slow+material-excursion case, and a fast+insufficient-path case, and confirms all three are
distinguishable along different axes rather than collapsing to one label. The real-data cross-tab in
`docs/26-failure-mode-atlas.md` confirms this empirically: "slow" failures span `none`/`partial`/
`material` excursion in real proportions 34/224/159 -- no single duration bucket maps to one
excursion class.
