# Checkpoint and Scope Authorization

## Checkpoint

- Checkout: `D:\Josué\Documents\proyectos\mado-strategy-research-loss-pattern-discovery`
- Branch: `research/loss-pattern-discovery`
- `HEAD`: `8e38a0e40582c18a6ee4135bc2c1556f8690d634` ("docs(research): record Unit 2 commit SHAs")
- Working tree: clean at the time this experiment started.

## Scope authorization (explicit, recorded here per standing practice)

Every prior phase in this engagement (the Loss Pattern Discovery lab, both `raza-crt-candle2-9am`
units) operated under a standing "no new strategy construction" boundary -- strictly retrospective
classification or gating of the EXISTING D3/C2 signal population, never a new entry/target rule.

**This experiment is different and was explicitly authorized as a new scope** after flagging the
conflict directly: it constructs a NEW trigger-generation pipeline (daily bias -> H4 FVG-gap-sweep
requirement -> a fresh M15 Model-1 search starting at 13:00) and a NEW target rule (the opposite
reference-range edge). The user confirmed: *"Yes, authorize it as a new research variant"* -- kept
in its own research directory, backtest-only (no live trading), no detector/scanner changes.

## What stays unchanged from the rest of this boundary

- `detector/`, `scanner/`, `docs/` (the Mado charters), `research/loss-pattern-discovery/`, and
  `research/raza-crt-candle2-9am/` remain read-only.
- `audit/trader-algorithm-fidelity/` (the paused 30-session human pilot) remains untouched and
  uninspected -- unrelated to, and unaffected by, this authorization.
- The original D3/C2 pipeline, ledger, and historical data remain read-only, used only as a
  reference for comparison.
- No AI/ML training, no GUI, no live order submission -- backtest-only, same as every prior unit.

## What IS newly authorized for this experiment only

- A new M15 entry-trigger search (Mado's own `entries.model1._track_anchor`/
  `causal_anchor_v2.confirm_in_ltf_window_v2`, reused UNMODIFIED, but invoked with a new search
  window and a daily-bias-fixed direction instead of the original D3/C2 trigger population).
- A new target rule (the opposite reference-range edge), implemented by feeding
  `backtest.levels.take_profit` (reused unmodified) a different context object -- never a new
  formula.
- New daily-bias and H4-gap-sweep classification logic, specific to this experiment.
