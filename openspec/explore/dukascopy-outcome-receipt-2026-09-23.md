# Dukascopy exploratory outcome receipt

This receipt records one completed, read-only execution of the frozen EURUSD + GBPUSD research experiment. The raw inputs, derived bars, manifest, ledger, and outcome JSON remain outside the repository.

## Provenance

| Field | Value |
|---|---|
| Run ID | `dukascopy-eurusd-gbpusd-2026-09-22-001` |
| External run root | `D:\Josué\Documents\dukascopy-run-2026-09-22` |
| Manifest SHA-256 | `e3c2caafb0a181a167a79d514fc9542886634643f4a543b3fbbd9367c75b745c` |
| Outcome artifact | `outcome-results-2026-09-22.json` |
| Outcome SHA-256 | `5bc888d345b570dcb8b87c1ade558686392372f51a3d4cab3e0ae061d418e945` |
| Source revision | `c37f5bc` |
| Candidate admission cutoff | `2026-08-19T00:00:00Z` |
| Outcome follow-up cutoff | `2026-08-19T20:30:00Z` |
| Retained gap-ledger entries | 430, all explained |

## Execution population

| Strategy identity | Candidates | Observations | Candidate fingerprint |
|---|---:|---:|---|
| `DUKASCOPY_EURUSD` | 1,968 | 7,872 | `a04cb6590e1a5446083d01b9ec1208ebf3f706b2b44f209fd73767c2021e037b` |
| `DUKASCOPY_GBPUSD` | 2,002 | 8,008 | `28cc66be330163e9cf409d0ff323e58546e2e9032ff3c0759860ad8cd8e90a8f` |
| Total | 3,970 | 15,880 | — |

## Frozen-statistics output

| Direction policy | EST-B | 95% bootstrap interval | Eligibility |
|---|---:|---|---|
| `direction_policy_structural_priority_v1` | 0.2187 | [0.0077, 0.4282] | Eligible |
| `direction_policy_corroboration_v1` | -0.1009 | [-1.2072, 0.8821] | Not eligible: below MEI, lower bound not positive, instrument veto |
| `direction_policy_noncontradiction_v1` | 0.2297 | [0.0157, 0.4413] | Eligible; nominated |
| `direction_policy_bias_veto_v1` | 0.1805 | [-0.1112, 0.4732] | Not eligible: below MEI, lower bound not positive |

The canonical nomination result was `direction_policy_noncontradiction_v1`. Its instrument estimates were 0.2409 for `DUKASCOPY_EURUSD` and 0.2187 for `DUKASCOPY_GBPUSD`.

## Interpretation boundary

This is an exploratory outcome from the preregistered two-instrument research variant. It does not authorize a production code change, baseline replacement, instrument substitution, or a claim that the original three-instrument strategy has been reproduced.

## Reproducibility replay

An identical second execution read the same retained inputs and derived bars, with the same manifest, cutoff boundaries, code revision, and frozen 10,000-replicate resampling plan. It wrote its result to the separate external directory `D:\Josué\Documents\dukascopy-run-2026-09-23-replay`.

| Artifact | SHA-256 | Comparison |
|---|---|---|
| First outcome: `outcome-results-2026-09-22.json` | `5bc888d345b570dcb8b87c1ade558686392372f51a3d4cab3e0ae061d418e945` | Baseline |
| Replay outcome: `outcome-results-2026-09-23-replay.json` | `5bc888d345b570dcb8b87c1ade558686392372f51a3d4cab3e0ae061d418e945` | Byte-identical |

The replay therefore reproduced the retained outcome artifact exactly. This establishes reproducibility of this documented local run; it does not establish that Dukascopy publishes an immutable, versioned closure calendar or extend the finding beyond the approved EURUSD + GBPUSD research variant.
