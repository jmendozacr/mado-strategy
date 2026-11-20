# Trader–algorithm fidelity audit (Stage 1)

This local application lets a trader review historical CRT sessions one closed M15 candle at a time and record an immutable human assessment. It does not display algorithm decisions or trade outcomes. It does not place orders, run a full backtest, or change strategy parameters.

## Windows startup

Start the Python API from the repository root:

```text
cd audit/trader-algorithm-fidelity
python server.py --port 8765
```

In a second terminal, start the React frontend:

```text
cd audit/trader-algorithm-fidelity/frontend
npm install
npm run dev
```

Open `http://127.0.0.1:5173`. Keep both terminals running. The Python server on `127.0.0.1:8765` serves the API; Vite proxies `/api` requests to it. If the frontend shows `Request failed: 502`, start or restart the Python server. Local development does not need a build or an external service. The backend needs Python 3.12+; the frontend needs Node.js and npm.

## Causal contract

The API owns each case's replay cursor. A M15 candle is available at its close (`open + 15 minutes`). Every response contains only candles whose availability is at or before that cursor. H4 feeder candles are reconstructed from that closed M15 prefix on the New York clock. A forming H4 shows accumulated OHLC and has no final availability timestamp. An incomplete 16-bar feeder bucket is marked as a gap; it is never filled synthetically. The client cannot request an arbitrary future cursor.

The review window is the four-hour NY feeder session: 1:00–5:00 AM New York for the 1AM model, or 9:00 AM–1:00 PM New York for the 9AM model. An evaluable case can finish only at that window's end and only after a decision is recorded at the terminal cursor; earlier `wait` entries remain interim observations. At the terminal cursor, `wait` is a valid final no-trade assessment. If the replay marks a case `non_evaluable`, record a separate data issue instead; that can close the review early, but the append-only finish event marks it `metric_eligible: false`. A data issue is never represented as “no signal.” Future concordance metrics must include only finished cases whose persisted `metric_eligible` value is true.

The chart's reference High/Low are CRT price levels, not automatically detected Key Levels. Stage 1 records the trader's Key Level type, price, availability, and touch assessment manually. Automatic D3/C2 Key Level overlays and comparison traces belong to Stage 2, when their causal provenance can be preserved. No Key Level computed from future bars is exposed in this MVP.

Decisions are appended to `audit/trader-algorithm-fidelity/runtime/events.jsonl`, with a server-assigned event ID, historical cursor, last available M15, dataset SHA-256, rules/configuration version, reason, and wall-clock recording time. Corrections create new events referring to earlier events; original records remain. Long and short trade prices must have entry between stop and target in the declared direction. Declared event times must be causal; a Model #1 anchor must be the open time of an existing M15 candle whose close is available by the cursor. Uncertainty and conflicting observations remain recordable in notes and “Uncertain” fields. Keep this local journal private when sharing the repository.

Timestamp inputs labeled UTC mean enter the UTC clock reading regardless of the computer timezone; the browser's timezone is not applied. The reference feeder field is instead a New York wall time (EST/EDT resolved from the case date). The API stores timestamps as explicit UTC instants.

## Pilot selection

`selection.py` produces `pilot_manifest.json` once, using seed `20261119`. It selects 30 unique sessions across EURUSD, USDCAD, AUDUSD and both models:

- 10 with a historical D3/C2 filled trade, sampled from the existing immutable trade CSV without considering outcome or R;
- 10 whose complete reference and activation windows prove no High/Low sweep, a necessary condition for a D3/C2 trigger;
- 10 fixed DST-boundary or data-gap candidates.

The list and replay API expose only pair, NY date, model, and review status. Selection strata and historical outcomes stay server-private. This deliberately enriched pilot is not a representative sample of market opportunity rates. A session with missing required candles is marked non-evaluable rather than repaired.

## Checks

```text
cd audit/trader-algorithm-fidelity
python -m unittest discover -s tests -v
cd frontend
npm run typecheck
npm test
npm run test:e2e
```

The Playwright CLI test starts an isolated API on port 8766 with a separate journal under `runtime/`, starts or reuses Vite on port 5173, and launches Microsoft Edge. It checks the 30-case listing, causal candle visibility, decision persistence after reload, and the unavailable-API error. Run `npm install` first to install its test runner. The other tests cover M15 close availability, provisional H4 OHLC, EST/EDT conversion, decision history, the HTTP privacy boundary, and reproducible selection. The source dataset, charters, D3/C2 code, and historical audit outputs are read only.

## Scope

Stage 1 contains replay, charts, case selection, and human decision capture. Algorithm comparison, discrepancy classification, statistics, and exports are reserved for Stages 2 and 3.
