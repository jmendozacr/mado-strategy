# Dukascopy Canonical Backtest — Official Run + Replay Receipt (2026-09-25)

Official evidence run for `dukascopy-backtest-readiness` (S-003), executed after
the manifest-validation correction documented in `apply-progress.md`'s
"S-003 adjustment 2" section. Run against the retained external run at
`D:\Josué\Documents\dukascopy-run-2026-09-22` (see
`openspec/explore/dukascopy-derived-manifest-receipt-2026-09-22.md`).

## Manifest Identity

| Field | Value |
|---|---|
| Manifest file | `D:\Josué\Documents\dukascopy-run-2026-09-22\run-manifest.json` |
| `manifest_sha256` (raw file bytes, what `--expected-manifest-sha256` validates) | `e3c2caafb0a181a167a79d514fc9542886634643f4a543b3fbbd9367c75b745c` |
| `canonical_manifest_sha256` (parsed/re-canonicalized form, diagnostic only) | `a89a2e010360a4abacf13f23393b986e4d8e8d854d2785405d0681016415ce12` |
| `schema_version` | `2` |

The two hashes are legitimately different: the retained manifest file is
pretty-printed JSON, while `canonical_manifest_sha256` is the SHA-256 of the
parsed manifest re-serialized as compact, key-sorted JSON. Only the raw-file
hash gates the run.

## Selected Costs (all-in, approved)

| Pair | Cost |
|---|---|
| EURUSD | `0.00011` (1.1 pips) |
| GBPUSD | `0.00015` (1.5 pips) |

## Six Required Derived-File Hashes (SHA-256, validated pre-simulation)

| Artifact | SHA-256 |
|---|---|
| `DUKASCOPY_EURUSD_D1.csv` | `501f4040b592a960f04f35a0ceaaa26c3cea62ccf8e870ae5f579f0393312010` |
| `DUKASCOPY_EURUSD_H4.csv` | `746b766e2c29df8e4c61b447b6366b1c52c18a87ab9caa1e202bb2ec8d2c9b41` |
| `DUKASCOPY_EURUSD_M15.csv` | `490d20cb96a9b01cce24440d402113166238065855db6b65bbd670076bf4d474` |
| `DUKASCOPY_GBPUSD_D1.csv` | `f55db9dd8ce4fccf0d2aff1aef4f8ce03740cc37f858a693319731774adb8b5e` |
| `DUKASCOPY_GBPUSD_H4.csv` | `5f5407ad47e07e82e4235b9a7ef603d2b8972146f2c14105740bb9d0b856c302` |
| `DUKASCOPY_GBPUSD_M15.csv` | `e9db3907b0e8630adddd03f733e554c29ce59ee33ce3bebd9606de2598f6bcce` |

The manifest also declares one additional, non-CSV provenance entry —
`Dukascopy-gap-ledger-2026-09-22.json` (`d9026e3a1dbcd4a4cad0e826ebe814f95fd5c6f2aeb625393996d780931860f5`)
— which the corrected `_validate_manifest_identity` now permits without
weakening the six-CSV requirement.

## Output Directories

- Official: `D:\Josué\Documents\dukascopy-run-2026-09-22\canonical-backtest-official`
- Replay: `D:\Josué\Documents\dukascopy-run-2026-09-22\canonical-backtest-replay`

Both commands used identical flags except `--output-dir`:

```
uv run --project detector python -m research.dukascopy_eurusd_gbpusd.backtest \
  --manifest "D:\Josué\Documents\dukascopy-run-2026-09-22\run-manifest.json" \
  --expected-manifest-sha256 e3c2caafb0a181a167a79d514fc9542886634643f4a543b3fbbd9367c75b745c \
  --derived-root "D:\Josué\Documents\dukascopy-run-2026-09-22" \
  --output-dir <official-or-replay-dir> \
  --eurusd-cost 0.00011 \
  --gbpusd-cost 0.00015
```

Both runs exited `0`.

## Output Artifact SHA-256 (identical in both directories)

| Artifact | SHA-256 |
|---|---|
| `receipt.json` | `74bd9b95d8411e189c49abdb16e6ba706ad4e81300c9820d0d215ead1064d8d1` |
| `DUKASCOPY_EURUSD_trades.json` | `b1a517b757d3f35bd232f021cd39f9e6316c68f9ace7b65ddd9014d4d02e4341` |
| `DUKASCOPY_GBPUSD_trades.json` | `f9346b668e14691c599e98d8e56f05baea78e942bbe31769f5f73de13469d097` |

## Replay Equality

`Get-FileHash -Algorithm SHA256` computed independently for both directories
for all three files above; official and replay hashes matched exactly for
every file (`equal=True` for all three). No byte-level divergence.

## Per-Instrument Summary (from `receipt.json`)

| Instrument | `candidate_count` | `signals_considered` | `trades_opened` |
|---|---|---|---|
| DUKASCOPY_EURUSD | 1968 | 36202 | 1943 |
| DUKASCOPY_GBPUSD | 2002 | 36558 | 1986 |

## Source Provenance (from manifest, carried into `receipt.json`)

| Strategy instrument | Source path | `source_sha256` |
|---|---|---|
| DUKASCOPY_EURUSD | `D:\Josué\Documents\dukascopy-original-2026-09-21\EURUSD_1 Min_Bid_2022.08.08_2026.08.19.csv` | `f43ec0be4cd09f5be0d0b957c9ec87e8e9544c22760a6acf9c2bb677bd2832e6` |
| DUKASCOPY_GBPUSD | `D:\Josué\Documents\dukascopy-original-2026-09-21\GBPUSD_1 Min_Bid_2022.08.08_2026.08.19.csv` | `520d5b8391bb8485199ecbe812756937d8fad6ddb3889ee4eb8128d34809a77a` |
