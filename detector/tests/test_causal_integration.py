"""Group 8 (REQ-CAUSAL-12/13): the causal generator's `list[AlignedSignal]`
output is a drop-in input to the UNMODIFIED `build_stage6_population`,
`evaluate_direction_policies`, and `simulate` — no code change to any of
those three needed, only causally-correct inputs."""

from datetime import datetime, timedelta

from causal.generate import generate_causal_aligned_signals
from composite.order_flow import detect_order_flow_events
from core.candle import Candle, OHLCSeries
from core.config import DetectorConfig
from core.key_level import KeyLevel
from core.results import DetectionStatus
from fixtures.synthetic import model1_pending_setup
from backtest.population import build_stage6_population
from backtest.simulate import simulate
from evaluation.direction import DirectionEvidence, evaluate_direction_policies
from primitives.bias import detect_bias_evidence

_LTF_START = datetime(2026, 1, 1, 12, 0)  # 07:00 NY -- inside the default kill zone
_LTF_SPECS = [
    (1.1000, 1.1020, 1.0980, 1.1010),  # 0 -- LTF range: H=1.1020 L=1.0980
    (1.1010, 1.1035, 1.1000, 1.1015),  # 1 -- anchor, purges High (bearish)
    (1.1000, 1.1005, 1.0950, 1.0960),  # 2 -- confirms (wick entry)
    (1.0960, 1.1012, 1.0955, 1.0965),  # 3 -- retest (retest_index=3)
    (1.0965, 1.0968, 1.0900, 1.0910),  # 4 -- expansion -> CONFIRMED
]
_HTF_START = datetime(2026, 1, 1, 0, 0)
_HTF_SPECS = [
    (1.1000, 1.1020, 1.0500, 1.1010),  # 0 -- HTF range: H=1.1020 L=1.0500 (wide, for RR headroom)
    (1.1015, 1.1035, 1.0400, 1.0450),  # 1 -- purges BOTH sides, true_break @1
]
_KEY_LEVEL = KeyLevel(kind="fvg", top=1.1040, bottom=1.1030, origin_index=0, expiry_index=None)


def _ltf_series(extra_specs: list[tuple[float, float, float, float]] = ()) -> OHLCSeries:
    specs = list(_LTF_SPECS) + list(extra_specs)
    candles = tuple(
        Candle(timestamp=_LTF_START + timedelta(hours=i), open=o, high=h, low=l, close=c)
        for i, (o, h, l, c) in enumerate(specs)
    )
    return OHLCSeries(candles=candles, instrument="EURUSD", timeframe="15M")


def _htf_series() -> OHLCSeries:
    candles = tuple(
        Candle(timestamp=_HTF_START + timedelta(hours=4 * i), open=o, high=h, low=l, close=c)
        for i, (o, h, l, c) in enumerate(_HTF_SPECS)
    )
    return OHLCSeries(candles=candles, instrument="EURUSD", timeframe="4H")


def _causal_tags():
    return generate_causal_aligned_signals(_ltf_series(), _htf_series(), htf_key_levels=[_KEY_LEVEL])


# Deliberately NOT a literal copy of test_alignment.py's reject/continuation
# fixtures: those close candle2 below range0's low, which is ALSO below the
# low of a second, competing CRT range that independently starts at index 1
# (candle1's own high/low) -- under causal's H-A rule (largest purge_index
# wins, unlike legacy's timestamp-window matching), that second range would
# win the HTF context selection instead of range0, entangling this
# key_level_reaction test with H-A's own range-competition semantics. Each
# fixture below is shaped so the index-1 range either never resolves (stays
# pending, dropped) or never exists long enough to compete, leaving range0
# as the only candidate either way.
_REACTION_HTF_SPECS_REJECT = [
    (1.1000, 1.1020, 1.0980, 1.1010),  # 0 — range H=1.1020 L=1.0980
    (1.1010, 1.1035, 1.1000, 1.1005),  # 1 — purges High(1.1035), closes back inside (1.1005) -> poke_side=high
    (1.1000, 1.1005, 1.0995, 1.1000),  # 2 — close=1.1000 (range0's own midpoint) -> false_break for range0;
    #       low=1.0995 only POKES (never resolves) the competing range starting at index 1 ([1.1000,1.1035]),
    #       which then has no further candle and is dropped unresolved.
]
_REACTION_HTF_SPECS_CONTINUATION = [
    (1.1000, 1.1020, 1.0980, 1.1010),  # 0 — range H=1.1020 L=1.0980
    (1.1010, 1.1035, 1.1000, 1.1025),  # 1 — purges High(1.1035), closes OUTSIDE (above 1.1020) -> true_break
    #       immediately at index 1 itself; the series ends here, so a competing range starting at
    #       index 1 never even gets a candle to test resolution against.
]
_REACTION_KEY_LEVEL = KeyLevel(kind="fvg", top=1.1050, bottom=1.1030, origin_index=0, expiry_index=None)


def _reaction_htf_series(specs) -> OHLCSeries:
    candles = tuple(
        Candle(timestamp=_HTF_START + timedelta(hours=i), open=o, high=h, low=l, close=c)
        for i, (o, h, l, c) in enumerate(specs)
    )
    return OHLCSeries(candles=candles, instrument="EURUSD", timeframe="1H")


def _bearish_tag(tags):
    return next(t for t in tags if t.ltf_signal.anchor_index == 1 and t.ltf_signal.direction == "bearish")


def test_causal_purge_candle_closing_back_inside_is_tagged_reject_close_inside():
    """REQ-CAUSAL parity with legacy `tag_alignment` (test_alignment.py's
    equivalent): `generate_causal_aligned_signals` must populate
    `key_level_reaction`, not leave it `None`, once a key_level is
    credited — it was previously never set at all (always `None`)."""
    tags = generate_causal_aligned_signals(
        _ltf_series(), _reaction_htf_series(_REACTION_HTF_SPECS_REJECT), htf_key_levels=[_REACTION_KEY_LEVEL],
    )
    tag = _bearish_tag(tags)
    assert tag.key_level == _REACTION_KEY_LEVEL
    assert tag.key_level_reaction == "reject_close_inside"


def test_causal_purge_candle_closing_outside_is_tagged_continuation():
    tags = generate_causal_aligned_signals(
        _ltf_series(), _reaction_htf_series(_REACTION_HTF_SPECS_CONTINUATION), htf_key_levels=[_REACTION_KEY_LEVEL],
    )
    tag = _bearish_tag(tags)
    assert tag.key_level == _REACTION_KEY_LEVEL
    assert tag.key_level_reaction == "continuation"


def test_causal_aligned_signal_with_no_key_level_has_no_reaction():
    tags = generate_causal_aligned_signals(_ltf_series(), _reaction_htf_series(_REACTION_HTF_SPECS_REJECT))
    tag = _bearish_tag(tags)
    assert tag.key_level is None
    assert tag.key_level_reaction is None


def test_stage6_admits_a_candidate_from_causal_signals_unmodified():
    tags = _causal_tags()
    population = build_stage6_population(tags, _ltf_series(), DetectorConfig())

    assert len(population.candidates) == 1
    candidate = population.candidates[0]
    assert candidate.direction == "bearish"
    assert candidate.retest_index == 3
    assert candidate.take_profit == 1.0500  # from the causal HTF context, unchanged by Stage6
    assert population.excluded_no_key_level == 0
    assert population.excluded_rr_floor == 0


def test_direction_evaluation_accepts_causal_population_unmodified():
    series = _ltf_series()
    tags = generate_causal_aligned_signals(series, _htf_series(), htf_key_levels=[_KEY_LEVEL])
    population = build_stage6_population(tags, series, DetectorConfig())

    evidence = DirectionEvidence(
        series=series,
        order_flow_events=tuple(detect_order_flow_events(series)),
        bias_evidence=tuple(detect_bias_evidence(series)),
    )
    rows = evaluate_direction_policies(population, evidence)
    assert len(rows) == 4  # one row per frozen policy
    assert all(row.signal_id == population.candidates[0].signal_id for row in rows)


def test_simulate_accepts_causal_signals_with_a_longer_outcome_view():
    """Candidate-View-vs-Outcome-View: the Candidate universe is built from
    the ORIGINAL (shorter) series; `simulate()` is fed the SAME aligned
    signals plus a LONGER series for fill/exit resolution (REQ-CAUSAL-05's
    explicitly-permitted exception). The frozen Candidate's own economic
    fields must be identical either way -- only fill/exit may see the
    extra candles."""
    original_series = _ltf_series()
    tags = generate_causal_aligned_signals(original_series, _htf_series(), htf_key_levels=[_KEY_LEVEL])
    config = DetectorConfig()

    candidate_view = build_stage6_population(tags, original_series, config).candidates
    assert len(candidate_view) == 1

    # Outcome View: extra candles appended AFTER the Candidate View already
    # settled -- the price collapses well past take_profit (1.0500).
    outcome_series = _ltf_series(
        extra_specs=[
            (1.0910, 1.0915, 1.0400, 1.0410),  # 5 -- SL/TP sweep candle
        ]
    )
    outcome_candidates = build_stage6_population(tags, outcome_series, config).candidates
    assert len(outcome_candidates) == 1
    assert outcome_candidates[0] == candidate_view[0]  # I3: unchanged by the extra candle

    trades, report = simulate(tags, outcome_series, config)
    assert report.trades_opened == 1
    assert trades[0].outcome in ("win", "loss")  # resolved now that more data exists
    assert trades[0].exit_index is not None
