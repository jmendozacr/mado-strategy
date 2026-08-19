# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Repository Purpose

Primarily this is not a software project — there is no build system, package manifest, or test suite at the repo root. It is a knowledge base of structured notes transcribed from the "CRT 2026 Mentorship" YouTube series by trading educator **Mado**, covering **Candle Range Theory (CRT)**, a price-action trading methodology derived from ICT (Inner Circle Trader) concepts (liquidity, order flow, Fair Value Gaps, Order Blocks, Turtle Soup, etc.). The one exception is the `detector/` subproject — a small, self-contained Python codebase that encodes the methodology as detection rules — see below.

## Structure

- `docs/charter-N.md` — one file per mentorship episode, in viewing order. Each new episode transcribed gets the next sequential `charter-N.md`.
- `detector/` — the CRT/ICT pattern detector subproject (source code; see "`detector/` Subproject" below).

## File Format Convention

Each `charter-N.md` follows this pattern:

1. **Header**: episode title, YouTube channel (`Mado`), video link, total duration.
2. **Timestamped sections**: `##`/`###` headings group concepts, with bullet points citing `[HH:MM:SS]` marks tied to the source video.
3. **Terminology stays bilingual**: prose is in Spanish (Rioplatense-adjacent educational Spanish), but CRT/ICT domain terms are kept in English on first use with a Spanish gloss in parentheses (e.g., `Liquidez (*Liquidity*)`), since the trading terminology is standardized in English.
4. **Worked examples**: a "Ejemplos Gráficos" section near the end walks through chart examples referenced in the video, timestamped.
5. **Closing section**: a brief conclusion/next-steps note, sometimes followed by the video URL repeated as a link.

## Conceptual Throughline (for context when editing/extending notes)

The episodes build cumulatively — later charters assume earlier ones:

1. **Ep 1** — CRT fundamentals: a candle as a time-based range (Liquidity + Time + Price), CRT High/Low as BSL/SSL, true break vs. false break (Turtle Soup), and the 3-candle/2-candle/multi-candle CRT models.
2. **Ep 2** — LTF execution: Model-1 entry (liquidity purge + engulfing close + retest), wick-vs-body entry rules, and the HTF CRT → LTF Model-1 timeframe pairing table.
3. **Ep 3** — Syncing HTF (order flow, bias, draw on liquidity, key levels) → ITF (narrative/context, kill zones) → LTF (execution: time, entry model, stop-loss, target).
4. **Ep 4** — The full Turtle Soup Sequence (TSQ): Turtle Soup → Model-1 → Breaker Block → OTE (60–75% Fib zone) → Kiss of Death, and its HTF→LTF timeframe alignment table.
5. **Ep 5** — Mapping TSQ phases onto a single candle's own OHLC/OLHC anatomy (open→low→high→close for bullish, open→high→low→close for bearish).

When adding new charters, preserve this progression and keep terminology consistent with earlier episodes (e.g., CRT High/Low, BSL/SSL, DOL, Model-1, TSQ phase names) rather than introducing synonyms.

## `detector/` Subproject

A CRT/ICT price-action pattern detector for MetaTrader 5-exported OHLC data, encoding the methodology from `docs/charter-1..5.md` as detection rules (Swing, FVG, CRT range, MSS, Model-1) plus HTF↔LTF alignment, a chart overlay, and a CSV detections table. Layered pure-function pipeline (`core` → `primitives` → `composite`/`entries` → `alignment` → `viz`/`cli`; `ingestion` is a leaf) — full design at `openspec/changes/crt-pattern-detector-v1/design.md`.

- **Stack**: Python 3.12, managed with `uv`. Dependencies: pandas, numpy, matplotlib (runtime); pytest, hypothesis, import-linter (dev).
- **Setup**: `cd detector && uv sync --extra dev`.
- **Test command**: `cd detector && uv run pytest`.
- **Import-layering check**: `cd detector && uv run lint-imports` (enforces `.importlinter`'s ADR-01 layers contract).
- **Run**: `uv run --project detector python -m detector.cli --csv PATH --symbol SYM --output-dir PATH` (from the repo root).
- Strict TDD applies to this subproject's implementation work — see the change's slices at `openspec/changes/crt-pattern-detector-v1/slices.md`.

## Working in This Repo

- Outside `detector/`, there is nothing to build, lint, or test — edits are prose/content edits to Markdown notes; treat accuracy to the source video (timestamps, terminology) as the main correctness bar.
- Inside `detector/`, treat it as a normal Python codebase: run tests and the import-linter check before considering a change done (see "`detector/` Subproject" above).
