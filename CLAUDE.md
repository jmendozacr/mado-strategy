# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Repository Purpose

This is not a software project — there is no source code, build system, package manifest, or test suite. It is a knowledge base of structured notes transcribed from the "CRT 2026 Mentorship" YouTube series by trading educator **Mado**, covering **Candle Range Theory (CRT)**, a price-action trading methodology derived from ICT (Inner Circle Trader) concepts (liquidity, order flow, Fair Value Gaps, Order Blocks, Turtle Soup, etc.).

## Structure

- `docs/charter-N.md` — one file per mentorship episode, in viewing order. Each new episode transcribed gets the next sequential `charter-N.md`.

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

## Working in This Repo

- There is nothing to build, lint, or test.
- Edits are prose/content edits to Markdown notes — treat accuracy to the source video (timestamps, terminology) as the main correctness bar.
