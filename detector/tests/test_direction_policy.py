"""DirectionPolicy V1 (REQ-DIRPOL-01..17).

Every rule exercised here is an ENGINEERING / RESEARCH HYPOTHESIS over the
frozen evidence primitives, never a mentorship definition — the same
provenance note the implementation module carries.
"""

from datetime import datetime, timedelta

import pytest
from hypothesis import given, settings
from hypothesis import strategies as st

import policy.direction as policy_direction
from composite.order_flow import OrderFlowEvent, detect_order_flow_events
from core.candle import Candle, OHLCSeries
from policy.direction import (
    BiasAlignmentError,
    CutoffDomainError,
    combine_evidence_preserving,
    combine_order_flow_priority,
    combine_strict_agreement,
    decision_reason,
    direction_policy_bias_veto_v1,
    direction_policy_corroboration_v1,
    direction_policy_noncontradiction_v1,
    direction_policy_structural_priority_v1,
    normalize_bias_close_only,
    normalize_bias_non_contradiction,
    normalize_bias_strict_agreement,
    relevant_order_flow_event,
)
from primitives.bias import BiasEvidence
from primitives.swing import SwingPoint

_REJECTION = SwingPoint(index=0, price=1.0950, kind="low")
_BREAK = SwingPoint(index=1, price=1.1050, kind="high")


def _ohlc_candle(draw, index: int) -> Candle:
    open_ = draw(st.floats(min_value=1.0, max_value=2.0, allow_nan=False))
    close = draw(st.floats(min_value=1.0, max_value=2.0, allow_nan=False))
    wick_up = draw(st.floats(min_value=0.0, max_value=0.05, allow_nan=False))
    wick_down = draw(st.floats(min_value=0.0, max_value=0.05, allow_nan=False))
    return Candle(
        timestamp=datetime(2026, 1, 1) + timedelta(hours=index),
        open=open_,
        high=max(open_, close) + wick_up,
        low=min(open_, close) - wick_down,
        close=close,
    )


@st.composite
def _ohlc_series(draw, min_size=3, max_size=30):
    size = draw(st.integers(min_value=min_size, max_value=max_size))
    candles = tuple(_ohlc_candle(draw, i) for i in range(size))
    return OHLCSeries(candles=candles, instrument="EURUSD", timeframe="1H")


def _event(direction: str, confirmation_index: int) -> OrderFlowEvent:
    """A structurally-shaped OrderFlowEvent whose only field under test is
    `confirmation_index` — DirectionPolicy reads no other field for
    selection (REQ-DIRPOL-02)."""
    return OrderFlowEvent(
        direction=direction,
        rejection_reference=_REJECTION,
        break_reference=_BREAK,
        rejection_index=confirmation_index - 1,
        confirmation_index=confirmation_index,
    )


# --- REQ-DIRPOL-02: relevant Order Flow event selection ----------------------

def test_no_events_yields_no_relevant_event():
    assert relevant_order_flow_event([], cutoff_index=100) is None


def test_no_eligible_events_yields_no_relevant_event():
    """Every event confirmed strictly after the cutoff is invisible — the
    only OF rule V1 has is `confirmation_index <= cutoff_index`."""
    assert relevant_order_flow_event([_event("bullish", 140)], cutoff_index=100) is None


def test_single_bullish_event_is_relevant():
    event = _event("bullish", 40)

    assert relevant_order_flow_event([event], cutoff_index=100) is event


def test_single_bearish_event_is_relevant():
    event = _event("bearish", 40)

    assert relevant_order_flow_event([event], cutoff_index=100) is event


def test_event_confirmed_exactly_at_cutoff_is_eligible():
    """The eligibility bound is inclusive (`<=`): a decision taken at
    `cutoff_index` may use evidence confirmed by that same candle's close."""
    event = _event("bullish", 100)

    assert relevant_order_flow_event([event], cutoff_index=100) is event


def test_newer_same_direction_event_refreshes_the_reference():
    """REQ-DIRPOL-02.1: selection is ALWAYS argmax(confirmation_index), even
    when direction is unchanged — the relevant reference never "sticks" to
    the older event. This is what collapses the OF-A/OF-B candidates into
    one: they agree on direction AND on evidence identity."""
    older, newer = _event("bullish", 100), _event("bullish", 140)

    assert relevant_order_flow_event([older, newer], cutoff_index=200) is newer


def test_newer_opposite_direction_event_supersedes():
    older, newer = _event("bullish", 100), _event("bearish", 140)

    assert relevant_order_flow_event([older, newer], cutoff_index=200) is newer


def test_selection_is_independent_of_input_order():
    older, newer = _event("bullish", 100), _event("bearish", 140)

    assert relevant_order_flow_event([newer, older], cutoff_index=200) is newer


def test_future_events_never_displace_an_eligible_past_event():
    past, future = _event("bullish", 40), _event("bearish", 300)

    assert relevant_order_flow_event([past, future], cutoff_index=100) is past


@given(
    confirmation_indices=st.lists(
        st.integers(min_value=0, max_value=60), min_size=0, max_size=12, unique=True
    ),
    directions=st.lists(st.sampled_from(["bullish", "bearish"]), min_size=0, max_size=12),
    cutoff_index=st.integers(min_value=0, max_value=60),
)
@settings(max_examples=300)
def test_relevant_event_is_the_unique_argmax_over_eligible_events(
    confirmation_indices, directions, cutoff_index
):
    """`confirmation_index` is a globally unique key over any valid event
    list (REQ-OF-09 + its same-direction companion), so the argmax is
    provably unique and NO tie-break is needed or permitted — this property
    pins that DirectionPolicy never invents one. Indices are drawn `unique`
    precisely because a duplicate is not a valid event list."""
    events = [
        _event(directions[i] if i < len(directions) else "bullish", index)
        for i, index in enumerate(confirmation_indices)
    ]
    eligible = [e for e in events if e.confirmation_index <= cutoff_index]

    relevant = relevant_order_flow_event(events, cutoff_index)

    if not eligible:
        assert relevant is None
    else:
        assert relevant in eligible
        assert all(e.confirmation_index <= relevant.confirmation_index for e in eligible)


# --- REQ-DIRPOL-03..05: bias normalizer truth tables -------------------------
#
# All three tables are total over the FULL 12-cell domain
# close_signal {bullish, bearish, None} x wick_signal {bullish, bearish,
# conflict, None} — every cell of every table is pinned below, so no
# normalizer can silently acquire an undocumented row.
#
# B-A (close priority, wick fallback) is NOT implemented: the design pass
# COLLAPSED it into B-D (they differ on exactly 2/12 rows, both requiring a
# doji close). It exists here as a historical note only and must never be
# reachable as a production code path.

_CLOSE_SIGNALS = ["bullish", "bearish", None]
_WICK_SIGNALS = ["bullish", "bearish", "conflict", None]


def _bias(close_signal, wick_signal, observation_index: int = 7) -> BiasEvidence:
    """close_relation is not read by any normalizer (REQ-DIRPOL-03.1): the
    normalizers consume the two derived signals only, never re-derive from
    the relation. It is filled with a value consistent with `close_signal`
    purely so the fixture stays a realistic BiasEvidence."""
    relation = {"bullish": "above", "bearish": "below", None: "inside"}[close_signal]
    return BiasEvidence(
        observation_index=observation_index,
        close_relation=relation,
        close_signal=close_signal,
        wick_signal=wick_signal,
    )


def _rows(table: dict) -> list:
    return [
        pytest.param(close, wick, table[(close, wick)], id=f"close={close}-wick={wick}")
        for close in _CLOSE_SIGNALS
        for wick in _WICK_SIGNALS
    ]


_B_B = {  # strict agreement: both axes must name the SAME direction
    ("bullish", "bullish"): "bullish",
    ("bullish", "bearish"): "unresolved",
    ("bullish", "conflict"): "unresolved",
    ("bullish", None): "unresolved",
    ("bearish", "bullish"): "unresolved",
    ("bearish", "bearish"): "bearish",
    ("bearish", "conflict"): "unresolved",
    ("bearish", None): "unresolved",
    (None, "bullish"): "unresolved",
    (None, "bearish"): "unresolved",
    (None, "conflict"): "unresolved",
    (None, None): "unresolved",
}

_B_C = {  # non-contradiction: a single non-contradicted axis suffices
    ("bullish", "bullish"): "bullish",
    ("bullish", "bearish"): "unresolved",
    ("bullish", "conflict"): "unresolved",
    ("bullish", None): "bullish",
    ("bearish", "bullish"): "unresolved",
    ("bearish", "bearish"): "bearish",
    ("bearish", "conflict"): "unresolved",
    ("bearish", None): "bearish",
    (None, "bullish"): "bullish",
    (None, "bearish"): "bearish",
    (None, "conflict"): "unresolved",
    (None, None): "unresolved",
}

_B_D = {  # close-only, no wick fallback: wick_signal is never read
    ("bullish", wick): "bullish" for wick in _WICK_SIGNALS
} | {
    ("bearish", wick): "bearish" for wick in _WICK_SIGNALS
} | {
    (None, wick): "unresolved" for wick in _WICK_SIGNALS
}


@pytest.mark.parametrize("close_signal, wick_signal, expected", _rows(_B_B))
def test_b_b_strict_agreement_truth_table(close_signal, wick_signal, expected):
    """REQ-DIRPOL-03 (B-B): resolves only when close and wick agree on a
    direction. A single axis is never enough, and `conflict` never resolves."""
    assert normalize_bias_strict_agreement(_bias(close_signal, wick_signal)) == expected


@pytest.mark.parametrize("close_signal, wick_signal, expected", _rows(_B_C))
def test_b_c_non_contradiction_truth_table(close_signal, wick_signal, expected):
    """REQ-DIRPOL-04 (B-C): resolves whenever the present axes do not
    contradict each other. `conflict` IS a contradiction (a both-wick candle
    is a structurally valid, first-class state, not a rare exception) — the
    justification is semantic, never frequency-based."""
    assert normalize_bias_non_contradiction(_bias(close_signal, wick_signal)) == expected


@pytest.mark.parametrize("close_signal, wick_signal, expected", _rows(_B_D))
def test_b_d_close_only_truth_table(close_signal, wick_signal, expected):
    """REQ-DIRPOL-05 (B-D): close_signal alone decides; there is no wick
    fallback, so a doji close is `unresolved` even when the wick is
    unambiguous. That is exactly the 2-row difference against the collapsed
    B-A candidate."""
    assert normalize_bias_close_only(_bias(close_signal, wick_signal)) == expected


def test_b_d_ignores_wick_signal_entirely():
    """Mutation guard for B-D's defining property, stated once as an
    invariant rather than inferred from the 12 rows above: the wick axis
    cannot change B-D's answer for any close_signal."""
    for close_signal in _CLOSE_SIGNALS:
        answers = {
            normalize_bias_close_only(_bias(close_signal, wick)) for wick in _WICK_SIGNALS
        }
        assert len(answers) == 1


# --- REQ-DIRPOL-06..08: combiner truth tables (pure functions) ---------------
#
# REACHABILITY NOTE (pre-implementation audit, Step 1b). The combiners take
# `bias_direction` in {bullish, bearish, unresolved} — "bias absent" is NOT
# a separate column, it enters as "unresolved". Consequently ALL 9 cells of
# every combiner are exercised by legitimate, valid-domain DirectionPolicy
# calls; none is a totality-only cell reachable solely by bypassing the
# policy-level precondition. The state the corrected domain DOES make
# unreachable is a DECISION-level field combination, not a combiner cell:
# `order_flow_direction is not None` together with
# `normalized_bias_direction is None` — pinned separately by
# `test_order_flow_present_with_bias_absent_is_unreachable`.
#
# DB-C (Bias priority) is NOT implemented — DEFERRED POLICY ALTERNATIVE,
# label SOURCE-TENSION. No V1 policy uses it and it must not be reachable.

_OF_DIRECTIONS = ["bullish", "bearish", None]
_BIAS_DIRECTIONS = ["bullish", "bearish", "unresolved"]

_DB_A = {  # strict agreement: a single present source is NEVER enough
    ("bullish", "bullish"): ("bullish", "AGREEMENT"),
    ("bullish", "bearish"): ("unresolved", "CONFLICT_UNRESOLVED"),
    ("bullish", "unresolved"): ("unresolved", "CORROBORATION_MISSING"),
    ("bearish", "bullish"): ("unresolved", "CONFLICT_UNRESOLVED"),
    ("bearish", "bearish"): ("bearish", "AGREEMENT"),
    ("bearish", "unresolved"): ("unresolved", "CORROBORATION_MISSING"),
    (None, "bullish"): ("unresolved", "CORROBORATION_MISSING"),
    (None, "bearish"): ("unresolved", "CORROBORATION_MISSING"),
    (None, "unresolved"): ("unresolved", "NO_EVIDENCE"),
}

_DB_B = {  # Order Flow priority: OF wins whenever present, even on conflict
    ("bullish", "bullish"): ("bullish", "AGREEMENT"),
    ("bullish", "bearish"): ("bullish", "CONFLICT_RESOLVED_BY_PRIORITY"),
    ("bullish", "unresolved"): ("bullish", "SINGLE_SOURCE"),
    ("bearish", "bullish"): ("bearish", "CONFLICT_RESOLVED_BY_PRIORITY"),
    ("bearish", "bearish"): ("bearish", "AGREEMENT"),
    ("bearish", "unresolved"): ("bearish", "SINGLE_SOURCE"),
    (None, "bullish"): ("bullish", "SINGLE_SOURCE"),
    (None, "bearish"): ("bearish", "SINGLE_SOURCE"),
    (None, "unresolved"): ("unresolved", "NO_EVIDENCE"),
}

_DB_D = {  # evidence-preserving: one source suffices, disagreement vetoes
    ("bullish", "bullish"): ("bullish", "AGREEMENT"),
    ("bullish", "bearish"): ("unresolved", "CONFLICT_UNRESOLVED"),
    ("bullish", "unresolved"): ("bullish", "SINGLE_SOURCE"),
    ("bearish", "bullish"): ("unresolved", "CONFLICT_UNRESOLVED"),
    ("bearish", "bearish"): ("bearish", "AGREEMENT"),
    ("bearish", "unresolved"): ("bearish", "SINGLE_SOURCE"),
    (None, "bullish"): ("bullish", "SINGLE_SOURCE"),
    (None, "bearish"): ("bearish", "SINGLE_SOURCE"),
    (None, "unresolved"): ("unresolved", "NO_EVIDENCE"),
}


def _cells(table: dict) -> list:
    return [
        pytest.param(of, bias, table[(of, bias)], id=f"of={of}-bias={bias}")
        for of in _OF_DIRECTIONS
        for bias in _BIAS_DIRECTIONS
    ]


@pytest.mark.parametrize("of_direction, bias_direction, expected", _cells(_DB_A))
def test_db_a_strict_agreement_truth_table(of_direction, bias_direction, expected):
    """REQ-DIRPOL-06 (DB-A, used by P2): resolves ONLY when both sources are
    present and equal — every other cell is unresolved."""
    direction = combine_strict_agreement(of_direction, bias_direction)

    assert (direction, decision_reason(of_direction, bias_direction, direction)) == expected


@pytest.mark.parametrize("of_direction, bias_direction, expected", _cells(_DB_B))
def test_db_b_order_flow_priority_truth_table(of_direction, bias_direction, expected):
    """REQ-DIRPOL-07 (DB-B, used by P1): a present Order Flow direction wins
    always, including against an explicitly disagreeing bias."""
    direction = combine_order_flow_priority(of_direction, bias_direction)

    assert (direction, decision_reason(of_direction, bias_direction, direction)) == expected


@pytest.mark.parametrize("of_direction, bias_direction, expected", _cells(_DB_D))
def test_db_d_evidence_preserving_truth_table(of_direction, bias_direction, expected):
    """REQ-DIRPOL-08 (DB-D, used by P3 and P4): agreement decides, a single
    present source decides, explicit disagreement vetoes to unresolved."""
    direction = combine_evidence_preserving(of_direction, bias_direction)

    assert (direction, decision_reason(of_direction, bias_direction, direction)) == expected


@pytest.mark.parametrize(
    "combine", [combine_strict_agreement, combine_order_flow_priority, combine_evidence_preserving]
)
def test_no_combiner_ever_fabricates_a_direction_from_no_evidence(combine):
    """Mutation guard shared by all three tables: with neither source
    present, no combiner may return anything but `unresolved`."""
    assert combine(None, "unresolved") == "unresolved"


@pytest.mark.parametrize(
    "combine", [combine_strict_agreement, combine_order_flow_priority, combine_evidence_preserving]
)
@pytest.mark.parametrize("of_direction", _OF_DIRECTIONS)
@pytest.mark.parametrize("bias_direction", _BIAS_DIRECTIONS)
def test_every_combiner_is_total_over_its_domain(combine, of_direction, bias_direction):
    """Each combiner is a TOTAL pure function over the full 3x3 domain — no
    input falls through to None or raises."""
    assert combine(of_direction, bias_direction) in ("bullish", "bearish", "unresolved")


# --- REQ-DIRPOL-01: valid-domain contract (Bias temporal alignment) ----------
#
# Corrected pre-implementation (Step 1a audit). `detect_bias_evidence` is
# DENSE on 1..N-1: index 0 never produces evidence, every later index
# produces exactly one. Combined with exact alignment, the V1 domain is:
#
#   cutoff_index == 0  -> bias_evidence MUST be None
#   cutoff_index >= 1  -> bias_evidence MUST be present, observation_index
#                         == cutoff_index
#
# `cutoff_index=500, bias_evidence=None` is therefore INVALID CALLER STATE,
# not a legitimate "missing evidence" case, and must fail loudly rather
# than silently decide on structural evidence alone.

_POLICIES = [
    direction_policy_structural_priority_v1,
    direction_policy_corroboration_v1,
    direction_policy_noncontradiction_v1,
    direction_policy_bias_veto_v1,
]
_POLICY_IDS = [
    "direction_policy_structural_priority_v1",
    "direction_policy_corroboration_v1",
    "direction_policy_noncontradiction_v1",
    "direction_policy_bias_veto_v1",
]


@pytest.mark.parametrize("policy", _POLICIES, ids=_POLICY_IDS)
def test_cutoff_zero_with_absent_bias_is_valid(policy):
    """The only cutoff at which an absent bias is legitimate — index 0 has
    no previous candle, so no BiasEvidence can exist there."""
    decision = policy([], None, cutoff_index=0)

    assert decision.direction == "unresolved"
    assert decision.reason == "NO_EVIDENCE"
    assert decision.normalized_bias_direction is None


@pytest.mark.parametrize("policy", _POLICIES, ids=_POLICY_IDS)
def test_cutoff_zero_with_present_bias_is_invalid(policy):
    with pytest.raises(BiasAlignmentError, match="cutoff_index 0"):
        policy([], _bias("bullish", "bullish", observation_index=0), cutoff_index=0)


@pytest.mark.parametrize("policy", _POLICIES, ids=_POLICY_IDS)
def test_absent_bias_at_a_later_cutoff_is_invalid_caller_state(policy):
    """The correction that tightened the signed spec: a caller at
    cutoff 500 with no BiasEvidence has a bug, because BiasEvidence is
    dense — silently treating it as "bias missing" would let a broken
    caller run a different, undocumented policy."""
    with pytest.raises(BiasAlignmentError, match="500"):
        policy([], None, cutoff_index=500)


@pytest.mark.parametrize("policy", _POLICIES, ids=_POLICY_IDS)
def test_stale_bias_evidence_is_invalid(policy):
    """Exact alignment, not `<=`: the rejected weaker precondition would
    admit 280-candle-stale evidence as a hidden, undocumented policy."""
    with pytest.raises(BiasAlignmentError, match="220"):
        policy([], _bias("bullish", "bullish", observation_index=220), cutoff_index=500)


@pytest.mark.parametrize("policy", _POLICIES, ids=_POLICY_IDS)
def test_future_bias_evidence_is_invalid(policy):
    with pytest.raises(BiasAlignmentError, match="501"):
        policy([], _bias("bullish", "bullish", observation_index=501), cutoff_index=500)


@pytest.mark.parametrize("policy", _POLICIES, ids=_POLICY_IDS)
def test_exactly_aligned_bias_is_valid(policy):
    decision = policy([], _bias("bullish", "bullish", observation_index=500), cutoff_index=500)

    assert decision.cutoff_index == 500
    assert decision.normalized_bias_direction is not None


@pytest.mark.parametrize("policy", _POLICIES, ids=_POLICY_IDS)
def test_negative_cutoff_is_invalid(policy):
    """cutoff_index=-1 names no OHLCSeries position. It is covered by
    NEITHER `cutoff_index == 0` NOR `cutoff_index >= 1` — a cutoff below
    zero needs its own explicit rejection, not an assumption that it falls
    through to the `>= 1` branch (it doesn't: -1 >= 1 is false)."""
    with pytest.raises(CutoffDomainError, match="-1"):
        policy([], None, cutoff_index=-1)


@pytest.mark.parametrize("policy", _POLICIES, ids=_POLICY_IDS)
def test_deeply_negative_cutoff_is_invalid(policy):
    with pytest.raises(CutoffDomainError, match="-100"):
        policy([], None, cutoff_index=-100)


@pytest.mark.parametrize("policy", _POLICIES, ids=_POLICY_IDS)
def test_negative_cutoff_is_rejected_before_bias_alignment_is_even_checked(policy):
    """Guards against the cutoff-domain check being bypassed by an
    artificially constructed BiasEvidence whose observation_index also
    happens to be negative. The real detector never produces one, but the
    type alone does not forbid it, so cutoff validity must be checked
    first and must not depend on what the caller passes for bias."""
    with pytest.raises(CutoffDomainError, match="-1"):
        policy([], _bias("bullish", "bullish", observation_index=-1), cutoff_index=-1)


# --- REQ-DIRPOL-10..13: the four policies ------------------------------------

def _decide(policy, of_direction, close_signal, wick_signal, cutoff_index=20):
    """One valid-domain call: an optional Order Flow event confirmed well
    before the cutoff, plus the mandatory exactly-aligned BiasEvidence."""
    events = [] if of_direction is None else [_event(of_direction, cutoff_index - 5)]
    bias = _bias(close_signal, wick_signal, observation_index=cutoff_index)
    return policy(events, bias, cutoff_index=cutoff_index)


def test_p1_structural_priority_lets_order_flow_override_a_disagreeing_bias():
    """REQ-DIRPOL-10 (P1 = B-D + DB-B): structural evidence decides whenever
    it is available, even against an explicit bias disagreement."""
    decision = _decide(direction_policy_structural_priority_v1, "bullish", "bearish", "bearish")

    assert (decision.direction, decision.reason) == ("bullish", "CONFLICT_RESOLVED_BY_PRIORITY")


def test_p1_lets_bias_fill_missing_structural_evidence():
    decision = _decide(direction_policy_structural_priority_v1, None, "bullish", "bullish")

    assert (decision.direction, decision.reason) == ("bullish", "SINGLE_SOURCE")


def test_p1_uses_the_close_only_normalizer():
    """P1's normalizer is B-D: a doji close with an unambiguous wick stays
    unresolved (the row that separates P1 from any B-C-based policy)."""
    decision = _decide(direction_policy_structural_priority_v1, None, None, "bullish")

    assert (decision.direction, decision.reason) == ("unresolved", "NO_EVIDENCE")


def test_p2_corroboration_resolves_only_on_full_agreement():
    """REQ-DIRPOL-11 (P2 = B-B + DB-A)."""
    decision = _decide(direction_policy_corroboration_v1, "bullish", "bullish", "bullish")

    assert (decision.direction, decision.reason) == ("bullish", "AGREEMENT")


def test_p2_rejects_a_single_axis_bias_even_when_order_flow_agrees():
    """P2's normalizer is B-B: close-only bias never resolves, so the
    corroboration DB-A demands is unavailable. Reported as
    CORROBORATION_MISSING however often it fires — prevalence is never
    measured or reasoned about here."""
    decision = _decide(direction_policy_corroboration_v1, "bullish", "bullish", None)

    assert (decision.direction, decision.reason) == ("unresolved", "CORROBORATION_MISSING")


def test_p2_never_decides_from_bias_alone():
    decision = _decide(direction_policy_corroboration_v1, None, "bullish", "bullish")

    assert (decision.direction, decision.reason) == ("unresolved", "CORROBORATION_MISSING")


def test_p3_noncontradiction_decides_from_a_wick_only_doji():
    """REQ-DIRPOL-12 (P3 = B-C + DB-D): the only V1 policy that can decide
    from wick-only evidence on a doji close."""
    decision = _decide(direction_policy_noncontradiction_v1, None, None, "bullish")

    assert (decision.direction, decision.reason) == ("bullish", "SINGLE_SOURCE")


def test_p3_treats_explicit_disagreement_as_a_veto():
    decision = _decide(direction_policy_noncontradiction_v1, "bullish", "bearish", "bearish")

    assert (decision.direction, decision.reason) == ("unresolved", "CONFLICT_UNRESOLVED")


def test_p4_bias_veto_blocks_a_disagreeing_order_flow():
    """REQ-DIRPOL-13 (P4 = B-D + DB-D)."""
    decision = _decide(direction_policy_bias_veto_v1, "bullish", "bearish", "bearish")

    assert (decision.direction, decision.reason) == ("unresolved", "CONFLICT_UNRESOLVED")


def test_p4_bias_alone_is_sufficient_when_order_flow_is_absent():
    """CLARIFICATION-1 (REQ-DIRPOL-13.1), normative reading, half 1 of 2:
    under P4 Bias IS a sufficient sole source when Order Flow is absent.
    The prose "Bias cannot independently overrule structural direction"
    admits a stricter misreading; the DB-D table governs."""
    decision = _decide(direction_policy_bias_veto_v1, None, "bullish", "bullish")

    assert (decision.direction, decision.reason) == ("bullish", "SINGLE_SOURCE")


def test_p4_bias_can_never_flip_a_present_order_flow_direction():
    """CLARIFICATION-1, half 2 of 2: what Bias cannot do is REPLACE a
    present Order Flow direction with the opposite one — only veto it to
    `unresolved`. Checked across the whole 12-row bias domain, both
    directions, so no single row can be the accident that keeps it true."""
    for of_direction in ("bullish", "bearish"):
        opposite = "bearish" if of_direction == "bullish" else "bullish"
        for close_signal in _CLOSE_SIGNALS:
            for wick_signal in _WICK_SIGNALS:
                decision = _decide(
                    direction_policy_bias_veto_v1, of_direction, close_signal, wick_signal
                )
                assert decision.direction != opposite


@pytest.mark.parametrize("policy, policy_id", list(zip(_POLICIES, _POLICY_IDS)), ids=_POLICY_IDS)
def test_decision_carries_its_policy_id_and_evidence_references(policy, policy_id):
    """REQ-DIRPOL-14: `policy_id` IS the version (no separate
    policy_version field), and the Order Flow evidence is carried by
    REFERENCE (`confirmation_index`), never as an embedded event object.
    There is no `bias_observation_index` field: the alignment invariant
    pins it to `cutoff_index`, so it would carry zero information."""
    decision = _decide(policy, "bullish", "bullish", "bullish")

    assert decision.policy_id == policy_id
    assert decision.cutoff_index == 20
    assert decision.order_flow_confirmation_index == 15
    assert decision.order_flow_direction == "bullish"
    assert decision.normalized_bias_direction == "bullish"
    assert not hasattr(decision, "policy_version")
    assert not hasattr(decision, "bias_observation_index")


@pytest.mark.parametrize("policy", _POLICIES, ids=_POLICY_IDS)
def test_absent_order_flow_leaves_both_reference_fields_none(policy):
    decision = _decide(policy, None, "bullish", "bullish")

    assert decision.order_flow_confirmation_index is None
    assert decision.order_flow_direction is None


# --- REQ-DIRPOL-15: DirectionReason reachability under the VALID domain ------
#
# Re-derived post-correction (Step 1b audit). No surviving reason value
# depends on the now-unreachable "Order Flow present + Bias absent" state:
# SINGLE_SOURCE's Order-Flow-only variant is reached with a bias that is
# PRESENT but normalises to `unresolved`, and CORROBORATION_MISSING with a
# bias that is present and resolved while Order Flow has not yet fired.

def test_reason_no_evidence_is_reachable():
    assert _decide(direction_policy_bias_veto_v1, None, None, "conflict").reason == "NO_EVIDENCE"


def test_reason_single_source_is_reachable_from_bias_alone():
    assert _decide(direction_policy_bias_veto_v1, None, "bullish", None).reason == "SINGLE_SOURCE"


def test_reason_single_source_is_reachable_from_order_flow_alone():
    """The corrected justification: the bias is PRESENT (as the domain
    requires) but normalises to `unresolved`, leaving Order Flow the only
    source. The old justification — an absent bias alongside a present
    Order Flow — is unreachable in the corrected domain."""
    assert _decide(direction_policy_bias_veto_v1, "bullish", None, None).reason == "SINGLE_SOURCE"


def test_reason_agreement_is_reachable():
    assert _decide(direction_policy_bias_veto_v1, "bullish", "bullish", None).reason == "AGREEMENT"


def test_reason_conflict_unresolved_is_reachable():
    decision = _decide(direction_policy_bias_veto_v1, "bullish", "bearish", None)

    assert decision.reason == "CONFLICT_UNRESOLVED"


def test_reason_conflict_resolved_by_priority_is_reachable_only_via_p1():
    """P1's unique fingerprint in a decision log: it is the only V1 policy
    whose combiner resolves a conflict instead of vetoing it."""
    conflict = dict(of_direction="bullish", close_signal="bearish", wick_signal="bearish")

    assert _decide(direction_policy_structural_priority_v1, **conflict).reason == (
        "CONFLICT_RESOLVED_BY_PRIORITY"
    )
    for policy in _POLICIES:
        if policy is not direction_policy_structural_priority_v1:
            assert _decide(policy, **conflict).reason != "CONFLICT_RESOLVED_BY_PRIORITY"


def test_reason_corroboration_missing_is_reachable_only_via_p2():
    """P2's unique fingerprint: DB-A is the only combiner that refuses a
    lone present source."""
    lone_bias = dict(of_direction=None, close_signal="bullish", wick_signal="bullish")

    assert _decide(direction_policy_corroboration_v1, **lone_bias).reason == "CORROBORATION_MISSING"
    for policy in _POLICIES:
        if policy is not direction_policy_corroboration_v1:
            assert _decide(policy, **lone_bias).reason != "CORROBORATION_MISSING"


# --- REQ-DIRPOL-16: pairwise meaningful difference (valid domain only) -------
#
# Re-derived under the corrected domain (Step 1c gate). Every counterexample
# below uses a PRESENT, exactly-aligned BiasEvidence at a cutoff >= 1 — none
# relies on the unreachable "bias absent at cutoff >= 1" state. All 6 pairs
# stay genuinely distinct, so no policy collapse was found.

def test_p1_differs_from_p2():
    """Bias alone, agreeing on both axes: P1 decides from it (DB-B),
    P2 refuses without Order Flow corroboration (DB-A)."""
    case = dict(of_direction=None, close_signal="bullish", wick_signal="bullish")

    assert _decide(direction_policy_structural_priority_v1, **case).direction == "bullish"
    assert _decide(direction_policy_corroboration_v1, **case).direction == "unresolved"


def test_p1_differs_from_p3():
    case = dict(of_direction="bullish", close_signal="bearish", wick_signal="bearish")

    assert _decide(direction_policy_structural_priority_v1, **case).direction == "bullish"
    assert _decide(direction_policy_noncontradiction_v1, **case).direction == "unresolved"


def test_p1_differs_from_p4_isolating_the_combiner_axis():
    """P1 and P4 share the B-D normalizer, so this pair isolates DIR-P02:
    OF priority (DB-B) vs. evidence preservation (DB-D)."""
    case = dict(of_direction="bullish", close_signal="bearish", wick_signal="bearish")

    assert _decide(direction_policy_structural_priority_v1, **case).direction == "bullish"
    assert _decide(direction_policy_bias_veto_v1, **case).direction == "unresolved"


def test_p2_differs_from_p3():
    case = dict(of_direction=None, close_signal="bullish", wick_signal="bullish")

    assert _decide(direction_policy_corroboration_v1, **case).direction == "unresolved"
    assert _decide(direction_policy_noncontradiction_v1, **case).direction == "bullish"


def test_p2_differs_from_p4():
    case = dict(of_direction=None, close_signal="bullish", wick_signal="bullish")

    assert _decide(direction_policy_corroboration_v1, **case).direction == "unresolved"
    assert _decide(direction_policy_bias_veto_v1, **case).direction == "bullish"


def test_p3_differs_from_p4_isolating_the_normalizer_axis():
    """P3 and P4 share the DB-D combiner, so this pair isolates DIR-P03:
    non-contradiction (B-C) vs. close-only (B-D) on a doji close whose only
    directional evidence is the wick."""
    case = dict(of_direction=None, close_signal=None, wick_signal="bullish")

    assert _decide(direction_policy_noncontradiction_v1, **case).direction == "bullish"
    assert _decide(direction_policy_bias_veto_v1, **case).direction == "unresolved"


# --- REQ-DIRPOL-17 + audit invariants ----------------------------------------

@pytest.mark.parametrize("policy", _POLICIES, ids=_POLICY_IDS)
@pytest.mark.parametrize("of_direction", ["bullish", "bearish", None])
def test_unresolved_is_first_class_for_every_valid_input(policy, of_direction):
    """Every valid call returns a fully-populated DirectionDecision whose
    `direction` is one of exactly three literals — never None, never False,
    never an exception. `unresolved` is an answer, not a failure."""
    for close_signal in _CLOSE_SIGNALS:
        for wick_signal in _WICK_SIGNALS:
            decision = _decide(policy, of_direction, close_signal, wick_signal)

            assert decision.direction in ("bullish", "bearish", "unresolved")
            assert decision.reason in (
                "NO_EVIDENCE", "SINGLE_SOURCE", "AGREEMENT", "CONFLICT_UNRESOLVED",
                "CONFLICT_RESOLVED_BY_PRIORITY", "CORROBORATION_MISSING",
            )
            assert decision.normalized_bias_direction in ("bullish", "bearish", "unresolved")
            assert (decision.order_flow_direction is None) == (of_direction is None)


@given(series=_ohlc_series())
@settings(max_examples=200)
def test_no_order_flow_event_can_be_eligible_at_cutoff_zero(series):
    """Reachability premise for the audit, sourced from OrderFlowEvent's own
    structure (a rejection needs a confirmed swing, and confirmation needs a
    later candle still), NOT from any DirectionPolicy-level constant: no
    event can ever be eligible at cutoff 0. Combined with the corrected
    domain (bias mandatory from cutoff 1 onward), "Order Flow present and
    Bias absent" is structurally unreachable — see the decision-level pin
    below."""
    for event in detect_order_flow_events(series):
        assert event.confirmation_index >= 1


@pytest.mark.parametrize("policy", _POLICIES, ids=_POLICY_IDS)
def test_order_flow_present_with_bias_absent_is_unreachable(policy):
    """The decision-level consequence of the Step 1b audit: a bias-absent
    decision can only be produced at cutoff 0, where no Order Flow event is
    eligible — so the two reference fields can never be populated while
    `normalized_bias_direction` is None. Events confirmed later are
    correctly ignored rather than admitted."""
    decision = policy([_event("bullish", 4)], None, cutoff_index=0)

    assert decision.normalized_bias_direction is None
    assert decision.order_flow_direction is None
    assert decision.order_flow_confirmation_index is None


@pytest.mark.parametrize("policy", _POLICIES, ids=_POLICY_IDS)
def test_unlimited_order_flow_persistence_v1_hypothesis(policy):
    """Tests the V1 unlimited-persistence RESEARCH HYPOTHESIS, NOT a proven
    property and NOT a mentorship rule: an Order Flow event stays the
    relevant reference forever while no newer eligible event exists, however
    stale it has become. A future revision that adopts an expiry rule should
    read a failure here as the hypothesis being replaced, never as a
    regression."""
    ancient = _event("bullish", 5)
    bias = _bias("bullish", "bullish", observation_index=10_000)

    decision = policy([ancient], bias, cutoff_index=10_000)

    assert decision.order_flow_confirmation_index == 5
    assert decision.order_flow_direction == "bullish"


def test_public_surface_excludes_the_non_v1_policy_components():
    """B-A (collapsed into B-D) and DB-C (DEFERRED POLICY ALTERNATIVE,
    SOURCE-TENSION) must not be reachable production code paths."""
    assert not [name for name in dir(policy_direction) if "bias_priority" in name]
    assert set(policy_direction.__all__) == {
        "BiasAlignmentError",
        "CutoffDomainError",
        "DirectionDecision",
        "combine_evidence_preserving",
        "combine_order_flow_priority",
        "combine_strict_agreement",
        "decision_reason",
        "direction_policy_bias_veto_v1",
        "direction_policy_corroboration_v1",
        "direction_policy_noncontradiction_v1",
        "direction_policy_structural_priority_v1",
        "normalize_bias_close_only",
        "normalize_bias_non_contradiction",
        "normalize_bias_strict_agreement",
        "relevant_order_flow_event",
    }
