# Human pilot protocol (Stage 1)

For Josué, running the 30-case fidelity pilot. This protocol explains how to use the application; it does not define or reinterpret any CRT/ICT trading rule. Apply the charters (`docs/charter-1.md`..`charter-11.md`) as the sole source of truth for what counts as a valid CRT, Key Level, or Model #1 — this app only lets you look, mark, and record.

## 1. Start the application (Windows)

Two terminals, both from the repo root:

```text
cd audit/trader-algorithm-fidelity
python server.py --port 8765
```

```text
cd audit/trader-algorithm-fidelity/frontend
npm install
npm run dev
```

Open `http://127.0.0.1:5173`. If you see `Request failed: 502`, the Python server isn't running — restart it. Keep both terminals open for the whole session.

## 2. Start a session

Pick a case from **Historical case**. A case you haven't opened shows `not_started`; click **Start case**. The app shows only market information available up to that instant — never later candles, never which category the case belongs to, never D3/C2's own decision.

## 3. Use the H4/Daily context

- **H4** is NY-feeder-anchored (opens at 9PM/1AM/5AM/9AM, respecting EST/EDT). **Daily** opens at 17:00 New York — an engineering convention for this tool, not a charter rule, and not the same as any broker's native Daily file.
- Drag, use the arrow buttons, or the +/− zoom buttons to review. Panning far enough back automatically loads older pages — give it a moment on the first few pages (each real history page takes under a second to load).
- A candle drawn with a dashed amber outline is still **forming** (today's incomplete bar); one in solid amber is a **data gap** — a real missing M15 candle before the cursor, not a weekend closure. Neither is fabricated data.
- Switch **New York / UTC** in the header to change which clock the axes and tooltips use. The case's own two clocks are always both shown in the toolbar.

## 4. Identify CRT, Key Levels, and Model #1 — manually, per the charters

The app never shows you an automatically detected Key Level or CRT. To record what you see:

1. Choose a **Type** in "Mark what you see": Key Level, Max/Min, Model #1 anchor (M15), or a horizontal price level.
2. For anything tied to a specific candle, click **Select on chart**, then click that candle on H4, Daily, or M15. Its real timestamp is captured for you — never type a date for an anchor.
3. Fill in price and, for a Key Level, the documented type (FVG, Order Block, Breaker, etc., in your own words, matching charter terminology).
4. **Save annotation.** It is appended immediately with its timestamp, timeframe, and time convention; it cannot be edited or deleted afterward.

Use the **Your price marker** field for a quick visual check across all three charts without saving anything.

## 5. Recording your read in the decision panel

- **Save an interim decision** (`Keep waiting`) any time you want to pin an observation before the window closes — every save is a separate, immutable record with the cursor at that instant.
- **Record a trade** (`Buy`/`Sell`): fill entry, stop, and target. The app rejects geometry that doesn't place the entry between stop and target in the stated direction.
- **Record a discard**: pick `Discard opportunity` and a reason (invalid CRT, no sweep, no Key Level, invalid touch, no Model #1, timing, missing data, other).
- **Record a data problem**: only when the case is marked non-evaluable (an incomplete data bucket — the app tells you with a banner), pick `Report data problem`. This is not a judgment that no opportunity existed; see the rules below.

## 6. Finishing a session

**Finish case** becomes enabled only once you've reached the documented review window's end (1AM: 1:00-5:00 NY; 9AM: 9:00 AM-1:00 PM NY) and saved a decision at that exact cursor — or, for a non-evaluable case, once a data-problem record exists. Finishing is final; the case moves to `finished` and can no longer advance.

## 7. Resuming after closing the browser

Nothing is lost. Reopen the app, pick the same case from the dropdown — its status, cursor, decisions, and annotations are all read back from the server's journal. If it was `in_progress`, continue from where you left off; if `finished`, you can still review everything, just not add to it.

## 8. Never consult the future or D3/C2

The backend enforces this structurally (no response ever contains a candle, Key Level, or decision beyond the current cursor, and the case's selection category and D3/C2's own trade data are never sent to the frontend at all). On your side: don't open `data/*_D1_*.csv`, `data/*_H4_*.csv`, or anything under `audit/2026-11-17-causal-lookahead-audit/` while reviewing a case — those are the detector's own source and trade files, not part of this tool, and opening them would let you see what you're specifically meant not to know yet.

## Protocol rules

- **Never use a trade's later outcome to decide whether the opportunity was valid at the time.** Judge only with what the charters require and what was available at that cursor.
- **Never revise an earlier decision to match a result you later learn.** Decisions are append-only by design; a correction is a new record referencing the old one, not an edit.
- **When a charter rule is ambiguous, record the ambiguity and the interpretation you used in your notes.** Do not invent a definitive rule to resolve it yourself — flag it for later discussion.
- **A `data_issue` record is not "no opportunity."** It means the data was insufficient to judge, full stop; it is excluded from fidelity metrics, not counted as a negative signal.
- **These 30 sessions are an enriched fidelity pilot, not a representative sample.** They were selected to surface implementation bugs (deliberately mixing cases with a known D3/C2 trade, cases with a proven no-sweep, and boundary/DST/gap cases), not to estimate how often real opportunities occur or how profitable they are. Don't draw rate or profitability conclusions from them.
