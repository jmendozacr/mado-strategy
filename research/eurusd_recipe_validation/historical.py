"""The historical figures this reproduction is checked against, and the
parameters it had to reconstruct -- RESEARCH TOOLING, not a production
entry point.

Everything in `VERIFIED_*` is a FACT carried forward from the two surviving
memory records of the original comparison. Everything in
`RECONSTRUCTED_PARAMETERS` is this package's own best rebuild of a
parameter the records did not carry. The whole point of separating them in
code -- rather than only in prose -- is that the generated report prints
the distinction automatically and cannot drift from it.

Sources
-------
M1: memory record `mado-eurusd-scanner-recipe` -- the final recipe running
    live in `scanner/rules.py`.
M2: memory record `prop-firm-sizing-rolling-window-vs-aggregate` -- the
    rejected-lever evidence.
U:  the user, confirming a parameter directly in this session.
"""
from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class Reconstruction:
    """One parameter the surviving records did not carry."""

    parameter: str
    value: str
    basis: str


# --- VERIFIED historical facts (never recomputed, only compared against) ---

VERIFIED_TRADE_COUNTS: dict[str, int] = {
    "baseline": 1681,       # M2
    "lever_b": 975,         # M2
    "lever_a_plus_b": 768,  # M2
}

# (variant key, risk % per trade) -> Phase-1 rolling-window fail_dd %, at the
# static 10% max-drawdown cap. M2.
VERIFIED_FAIL_DD_PCT: dict[tuple[str, float], float] = {
    ("baseline", 0.50): 10.2,
    ("lever_b", 0.50): 16.0,
    ("baseline", 0.75): 13.7,
    ("lever_b", 0.75): 19.6,
    ("lever_a_plus_b", 0.75): 23.2,
}

# Aggregate, non-windowed Calmar ratio -- the statistic that favoured the
# REJECTED lever and is exactly why the windowed check mattered. M2.
VERIFIED_CALMAR: dict[str, float] = {
    "baseline": 4.35,
    "lever_b": 6.46,
}

VERIFIED_PARAMETERS: tuple[Reconstruction, ...] = (
    Reconstruction("pair", "EURUSDm only", "M1"),
    Reconstruction("signal filter", 'key_level_reaction == "reject_close_inside"', "M1"),
    Reconstruction("exit", "the detector's natural CRT-opposite-extreme take_profit", "M1"),
    Reconstruction("session", "02:00-11:00 America/New_York, DST-aware", "M1 + scanner/rules.py"),
    Reconstruction("within-pair concurrency cap", "2R", "M1"),
    Reconstruction("daily risk rule", "stop taking new trades after the 2nd loss of the day", "M1"),
    Reconstruction("rejected daily-risk alternative", "max 1 trade/day (hurt results; not re-tested here)", "M1"),
    Reconstruction("H4 source", "raw broker-native H4, NOT the UTC4aligned file", "M1"),
    Reconstruction("rolling window length", "250 days (Phase 1 + Phase 2 combined)", "U"),
    Reconstruction("max-drawdown cap", "10% Phase 1 / 5% Phase 2, static from INITIAL balance", "M1 + U"),
    Reconstruction("daily loss limit", "5%, static from INITIAL balance", "M2 + U"),
    Reconstruction("lever B threshold", "key-level zone width <= 25 pips", "M2"),
    Reconstruction("lever A lever", "BacktestConfig.min_risk_reward, documented default 2.0", "M2"),
)

# --- RECONSTRUCTED parameters (this package's rebuild, NOT recovered) ---

RECONSTRUCTED_PARAMETERS: tuple[Reconstruction, ...] = (
    Reconstruction(
        "BacktestConfig.kill_zone_gated",
        "False",
        "FORCED, not chosen. With the library default (True) the detector's own NY 07:00-11:00 "
        "kill-zone gate subsumes the recipe's 02:00-11:00 session, making that session filter a "
        "no-op (1014 trades either way). Only with the gate off does the recipe's stated session "
        "govern, and only then does the baseline count reconcile with the historical 1681. See "
        "the report's live/backtest mismatch note.",
    ),
    Reconstruction(
        "lever A: min_risk_reward",
        "2.5",
        "PINNED BY CROSS-CHECK, not recovered. M2 names the lever but not the value. Sweeping it "
        "against M2's own lever-A+B count of 768 is decisive: 2.5 yields 755 (-1.7%), 3.0 yields "
        "589 (-23%), 3.5 yields 443. 2.5 is the only candidate consistent with the record.",
    ),
    Reconstruction(
        "lever C: NY-only session",
        "07:00-11:00 NY-local",
        "M2 names the lever but no window and gives no number to check against. Reuses the "
        "existing KillZoneConfig default (core/config.py) rather than inventing a window.",
    ),
    Reconstruction(
        "key-level zone width basis",
        "the credited AlignedSignal.key_level, (top - bottom) * 10000",
        "M2 says 'the Daily Key Level's own price range in pips'. The credited key level is "
        "whichever tier the detector credited (H4 FVG or Daily order block when a Daily CSV is "
        "supplied); there is no separate 'Daily key level' field to read.",
    ),
    Reconstruction(
        "BacktestConfig.partial_fraction",
        "0.0 primary, 0.5 reported alongside",
        "The library default is 0.5 (REQ-68, a LATER addition than this comparison). M1 describes "
        "the exit only as the natural take_profit level and says nothing about a partial leg. The "
        "choice is not cosmetic: at 0.0 the historical lever ORDERING reproduces, at 0.5 lever B "
        "reverses and looks better than the baseline. Both are published.",
    ),
    Reconstruction(
        "concurrency tie convention",
        "a trade exiting on bar N frees its slot for a trade entering on bar N",
        "See concurrency.py. The alternative yields 1613 baseline trades against this one's 1642 "
        "(historical: 1681).",
    ),
    Reconstruction(
        "daily-loss day key",
        "the NY-local calendar date of the loss's own ENTRY",
        "See daily_risk.py. Switching the timezone to UTC changes nothing (1642 either way).",
    ),
    Reconstruction(
        "Calmar ratio definition",
        "(total R / years) / peak-to-trough drawdown in R",
        "M2 quotes Calmar values but not the formula. This definition is risk%-independent. It "
        "reproduces the historical BASELINE value closely and the historical LEVER-B value not at "
        "all -- see the report's cross-check table.",
    ),
    Reconstruction(
        "rolling-window profit target",
        "none modelled",
        "A real challenge stops at its profit target, which truncates exposure. M2 mentions no "
        "target, so every window runs its full length, making the reported fail rates an upper "
        "bound.",
    ),
)
