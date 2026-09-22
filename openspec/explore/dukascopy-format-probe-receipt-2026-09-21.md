# Dukascopy format probe receipt

This receipt records a one-day technical format test only. It is not historical-window evidence, a closure schedule, a dataset commit, or a statistical experiment.

## Request

| Field | Value |
|-------|-------|
| Instrument | `EURUSD` (web export label `EUR/USD`) |
| Date | `2026-08-19` |
| Period | `1 Minute` |
| Timezone | `UTC` |
| Offer side | `Bid` |
| Export filename | `EUR-USD_1Minute_BID_2026-08-19_00_00-23_59_Etc_UTC.csv` |
| Retrieval date | 2026-09-21 |
| Retrieval path | `C:\Users\Josué\AppData\Local\Temp\dukascopy-eurusd-format-2026-08-19.csv` |

## Observed format

- Header: `Etc/UTC,Open,High,Low,Close,Volume`.
- First observed row: `2026-08-19T00:00:00+00:00`.
- Last observed row: `2026-08-19T23:59:00+00:00`.
- Total lines: 1,435 (header plus 1,434 one-minute rows).
- SHA-256: `DA51610EF5AEB0144DF50D0728759893C5AAB128D4EB97D44F19A381D20A0B89`.

## Interpretation

The export format is machine-readable and includes UTC timestamps plus OHLCV fields. The sample confirms format usability only. It does not establish complete coverage, closure semantics, reproducibility, or historical availability for 2022-08-08 through 2026-08-19.

The web widget exposed a single-day date selection in this interaction. A full-window export would therefore require verified range behavior or repeated daily requests; neither is assumed by this receipt.

## Controls

- No production code, datasets, baselines, statistical protocol, or instrument identities were changed.
- The raw sample remains outside the repository and is not staged or committed.
- No strategy performance or hypothesis statistic was computed.
- `GBPUSD` was not downloaded in this format-only test.
