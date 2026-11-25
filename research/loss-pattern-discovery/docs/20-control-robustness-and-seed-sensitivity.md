# Deliverable D — Control Robustness: Match Quality + Seed Sensitivity

## Match quality (unchanged by this phase's fix, as expected)

The price-causality fix only changes which PRICE a control's own reference bar contributes -- it
does not change which bar is chosen as a control (NY-hour matching, ATR-nearest selection, exclusion
buffer are all timestamp-based and untouched). Confirms this: Phase 3.1's `audit_match_quality()`
output is byte-for-byte identical to Phase 3's -- 1262/1262 matched fresh, 0 unmatched, mean NY-hour
diff 0.58h, 100% within the 1h tolerance, ATR diff ~2.7e-7, zero instrument/period/direction
mismatches. See `docs/15-control-group-audit.md` for the full table; not repeated here since nothing
changed.

## Seed sensitivity (limited, explicitly exploratory) — continuation vs. control, 1d horizon

Design: hold everything fixed (1262 eligible events, NY-hour tolerance, pool size, ATR matching,
exclusion buffer, 1d horizon, same statistic) and vary ONLY the control-sampling seed. Seeds
pre-declared before running (`stats/seed_sensitivity.py`): `20261124` (this lab's original seed) plus
`1, 2, 3, 4` (arbitrary small integers) -- never chosen after seeing a result, and no seed is
cherry-picked for the report below; all five are shown.

| Seed | P(continuation) diff (SL - control) | 90% CI | Excludes zero? |
|---|---|---|---|
| 20261124 | -2.61pp | [-5.83, +0.62] | No |
| 1 | -1.43pp | [-4.69, +1.92] | No |
| 2 | -0.16pp | [-3.22, +2.92] | No |
| 3 | -1.03pp | [-4.06, +2.08] | No |
| 4 | -1.43pp | [-4.43, +1.64] | No |

- **Sign**: negative in all 5 seeds (`stable_sign_across_seeds = true`).
- **Magnitude**: ranges from -0.16pp to -2.61pp -- more than a 16x spread between the smallest and
  largest magnitude, for equally-valid control draws.
- **Significance**: zero of five seeds exclude zero at 90% CI (`any_exclude_zero = false`).

**Interpretation, per the brief's own stated rule**: the sign does not flip, but the magnitude varies
substantially across equally-valid control samples, and the difference never reaches significance
under any of them (including the original seed, once the price-causality fix is applied -- see
`docs/19-...`). Per the instruction ("si el hallazgo cambia de signo o magnitud sustancialmente...
considéralo frágil"), this is treated as **fragile / sensitive to control design**, not as stable
exploratory evidence. It is also, independently, never statistically significant -- a second,
separate reason not to treat it as a finding.

This check was deliberately NOT extended to recovery-to-entry: the brief scoped the seed-sensitivity
check to continuation specifically (section 7), and recovery's own primary-endpoint conclusion did
not change sign or cross into significance under the single price-causality fix already applied
(`docs/19-...`), so no further seed search was run for it, consistent with "no realices búsquedas de
subgrupos ni optimización de umbrales."
