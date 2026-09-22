# Dukascopy EURUSD + GBPUSD descriptive preflight receipt

**Date**: 2026-09-22
**Branch**: `dukascopy-eurusd-gbpusd-experiment`
**Commit**: `42863878dba8e07b44b0ccef29e55641dc3f6db1`

## Problem being documented

The approved Dukascopy descriptive probe requires a traceable receipt proving that: (1) the source CSV files are byte-identical to the hashes recorded in the signed preflight; (2) the research adapter accepted both files without parser error; (3) all run artifacts are hash-anchored to the external run root; and (4) no outcomes, strategy statistics, production changes, dataset copies, or protocol amendments occurred. This document is that receipt.

## Scope declaration

This receipt covers **source integrity, parser acceptance, provenance, and artifact integrity only**. It is not a statistical run, a closure verdict, a baseline update, or a protocol amendment. No outcomes were computed. No production modules were modified. No dataset copies were created inside the repository. No protocol changes were made.

## Environment

| Field | Value |
|-------|-------|
| JForex desktop | `4.8.18` |
| JForex API | `4.8.13` |
| Observed CSV header | `Time (EET),Open,High,Low,Close,Volume ` (trailing space preserved) |

## Source file verification

The files reside outside the repository. Sizes and SHA-256 digests are reproduced verbatim from the signed preflight (`dukascopy-eurusd-gbpusd-preflight-2026-09-22.md`). No copy or mutation was performed.

| Instrument | Bytes | Rows (excl. header) | Zero-volume rows | First EET timestamp | Last EET timestamp | SHA-256 |
|------------|------:|--------------------:|-----------------:|--------------------|--------------------|---------|
| EURUSD | 88,625,458 | 1,509,415 | 14,745 | `2022.08.08 00:00:00` | `2026.08.19 23:59:00` | `F43EC0BE4CD09F5BE0D0B957C9EC87E8E9544C22760A6ACF9C2BB677BD2832E6` |
| GBPUSD | 88,122,339 | 1,509,415 | 8,461 | `2022.08.08 00:00:00` | `2026.08.19 23:59:00` | `520D5B8391BB8485199ECBE812756937D8FAD6DDB3889EE4EB8128D34809A77A` |

## Offline domain probe

| Field | Value |
|-------|-------|
| Rendered HTML SHA-256 | `5401661C87911D3773D112F271123671EA73CAA7E69AFDD21DB578C37322B01D` |

## Run artifacts

External run root: `D:\Josué\Documents\dukascopy-eurusd-gbpusd-runs\dry-2026-09-22`

| Artifact | SHA-256 |
|----------|---------|
| `descriptive-summary.json` | `9F1E54490FA0FBB37287218EABBD6674821B5AE15137716CBE58E2EC5B1F88AD` |
| `exclusion-ledger.json` | `5F312586CFA127853717FCD53D1C63EC558360D38F2AB13B305CB4DF7ADE8471` |
| `run-manifest.json` | `CB2B1477430B42F9873CEF97F636402EF079009C07470AE341B05E8F7E3BDCF1` |

All artifact paths are external to the repository and are referenced by hash only.

## Explicit non-occurrences

- No outcomes were computed.
- No strategy statistics were produced.
- No production module was modified.
- No dataset copy was staged or committed into the repository.
- No protocol or preregistration amendment was made.
- No baseline was updated.

## Verdict

The descriptive preflight is complete. Source bytes match the signed preflight hashes. The parser accepted both files. Run artifacts are hash-anchored to the external run root at the commit above. Provenance is established. The experiment remains at its pre-outcome state; no statistical authorization has been granted or implied by this receipt.
