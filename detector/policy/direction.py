"""DirectionPolicy V1 — arbitration of OrderFlowEvent against BiasEvidence.

EVERY rule in this module is an ENGINEERING / RESEARCH HYPOTHESIS, not a
mentorship definition. The mentorship corpus (docs/charter-1..5.md) defines
the EVIDENCE primitives this module consumes; it defines no arbitration
between them. P1-P4 are four co-equal pre-registered candidates, none
preferred, none measured against outcomes here.

The four policies share one Order Flow contract and differ only along two
axes: how BiasEvidence is normalised to a direction (B-B/B-C/B-D) and how
the two sources are combined (DB-A/DB-B/DB-D).
"""

from collections.abc import Callable
from dataclasses import dataclass
from typing import Literal

from composite.order_flow import OrderFlowEvent
from primitives.bias import BiasEvidence

__all__ = [
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
]

Direction = Literal["bullish", "bearish"]
# One alias for both the normalised bias and the final decision: they share
# the same three-valued domain, in which `unresolved` is a first-class
# answer — never None, never False, never an exception.
DirectionOutcome = Literal["bullish", "bearish", "unresolved"]
DirectionReason = Literal[
    "NO_EVIDENCE",
    "SINGLE_SOURCE",
    "AGREEMENT",
    "CONFLICT_UNRESOLVED",
    "CONFLICT_RESOLVED_BY_PRIORITY",
    "CORROBORATION_MISSING",
]


def relevant_order_flow_event(
    events: list[OrderFlowEvent], cutoff_index: int
) -> OrderFlowEvent | None:
    """The eligible event (`confirmation_index <= cutoff_index`) with the
    highest `confirmation_index`, or None when none is eligible.

    `confirmation_index` is a globally unique key over a valid event list
    (REQ-OF-09 and its same-direction companion invariant, both pinned in
    `tests/test_order_flow.py`), so this argmax is provably unique — no
    tie-break is needed, and inventing one would be a silent policy.

    Selection ALWAYS refreshes to the newest eligible event, including when
    the direction is unchanged (REQ-DIRPOL-02.1). There is deliberately no
    expiry, decay, timeout or window: unlimited Order Flow persistence is a
    COMMON V1 RESEARCH HYPOTHESIS shared identically by P1-P4, not an
    architectural truth and not mentorship-derived. Any bounded-persistence
    variant needs a parameter this design refuses to invent, and belongs to
    a future iteration.
    """
    eligible = [e for e in events if e.confirmation_index <= cutoff_index]
    if not eligible:
        return None
    return max(eligible, key=lambda e: e.confirmation_index)


# --- Bias normalizers (DIR-P03 axis) -----------------------------------------
#
# Each reads `close_signal` and `wick_signal` ONLY. `close_relation` is
# never re-derived here: BiasEvidence already derived the two signals
# independently and never arbitrates them internally (REQ-BIAS-04), and
# this layer must not undo that separation.
#
# B-A (close priority, wick fallback) is deliberately absent: the design
# pass COLLAPSED it into B-D (they differ on exactly 2 of 12 rows, both
# requiring a doji close), so shipping it would be pseudo-diversity.


def normalize_bias_strict_agreement(evidence: BiasEvidence) -> DirectionOutcome:
    """B-B — resolves only when both axes name the SAME direction; a single
    present axis never suffices, and `conflict` never resolves."""
    if evidence.close_signal is not None and evidence.close_signal == evidence.wick_signal:
        return evidence.close_signal
    return "unresolved"


def normalize_bias_non_contradiction(evidence: BiasEvidence) -> DirectionOutcome:
    """B-C — resolves whenever the present axes do not contradict each
    other, so one present axis is enough. `conflict` counts as a
    contradiction: a both-wick candle carries a genuine two-sided reading,
    and treating it as directional would fabricate evidence. That is a
    SEMANTIC judgement about what `conflict` means — never a claim about
    how often it occurs.
    """
    close, wick = evidence.close_signal, evidence.wick_signal
    if wick == "conflict":
        return "unresolved"
    if close is None:
        return wick or "unresolved"
    if wick is None or wick == close:
        return close
    return "unresolved"


def normalize_bias_close_only(evidence: BiasEvidence) -> DirectionOutcome:
    """B-D — `close_signal` decides alone; there is no wick fallback, so a
    doji close stays `unresolved` however unambiguous the wick is."""
    return evidence.close_signal or "unresolved"


# --- Combiners (DIR-P02 axis) ------------------------------------------------
#
# Each is a TOTAL pure function over
# of_direction {bullish, bearish, None} x bias_direction {bullish, bearish,
# unresolved}. "Bias absent" is not a separate column: an absent bias
# enters as `unresolved`, which is why the corrected V1 domain (a bias is
# mandatory at every cutoff >= 1) leaves no combiner cell unreachable.
#
# DB-C (Bias priority) is deliberately absent — DEFERRED POLICY
# ALTERNATIVE, label SOURCE-TENSION: excluded for parsimony and because
# P1-P4 already span the behaviour space, NOT because it was proven wrong.
# It must not exist as a reachable production path.


def combine_strict_agreement(
    of_direction: Direction | None, bias_direction: DirectionOutcome
) -> DirectionOutcome:
    """DB-A (P2) — corroboration required: resolves only when both sources
    are present and name the same direction. A single present source is
    NEVER enough."""
    if of_direction is not None and of_direction == bias_direction:
        return of_direction
    return "unresolved"


def combine_order_flow_priority(
    of_direction: Direction | None, bias_direction: DirectionOutcome
) -> DirectionOutcome:
    """DB-B (P1) — a present Order Flow direction wins always, including
    against an explicitly disagreeing bias; bias only fills the gap where
    structural evidence is missing."""
    if of_direction is not None:
        return of_direction
    return bias_direction


def combine_evidence_preserving(
    of_direction: Direction | None, bias_direction: DirectionOutcome
) -> DirectionOutcome:
    """DB-D (P3, P4) — every present source is used: agreement decides, a
    lone present source decides, and explicit disagreement vetoes to
    `unresolved`. Bias can therefore veto a present Order Flow direction,
    but can never REPLACE it with the opposite one."""
    if of_direction is None:
        return bias_direction
    if bias_direction == "unresolved":
        return of_direction
    return of_direction if of_direction == bias_direction else "unresolved"


def decision_reason(
    of_direction: Direction | None,
    bias_direction: DirectionOutcome,
    direction: DirectionOutcome,
) -> DirectionReason:
    """The single exhaustive, mutually-exclusive reason rule governing ALL
    combiners — stated once so no combiner can drift into its own private
    reason vocabulary. A source counts as "present" only when it names a
    direction; a bias that normalised to `unresolved` (or was absent at
    cutoff 0) is not evidence.
    """
    of_present = of_direction is not None
    bias_present = bias_direction != "unresolved"

    if not of_present and not bias_present:
        return "NO_EVIDENCE"
    if of_present and bias_present:
        if of_direction == bias_direction:
            return "AGREEMENT"
        if direction == "unresolved":
            return "CONFLICT_UNRESOLVED"
        return "CONFLICT_RESOLVED_BY_PRIORITY"
    single_source = of_direction if of_present else bias_direction
    return "SINGLE_SOURCE" if direction == single_source else "CORROBORATION_MISSING"


# --- The decision, its precondition, and the four V1 policies ----------------


class CutoffDomainError(Exception):
    """Invalid caller state: `cutoff_index` does not name a valid
    OHLCSeries position. DirectionPolicy validates only what it can know
    WITHOUT the series — a cutoff must be non-negative — and deliberately
    validates no upper bound, since it never receives the series or its
    length; an over-large cutoff is not this module's error to catch (the
    Order Flow side already yields no eligible events for one, and the
    Bias side already fails via `BiasAlignmentError` since dense evidence
    cannot exist beyond the series either). Named and raised in the style
    of `core.pairing_table.PairingError` / `ingestion.loader.LoadError` —
    kept separate from `BiasAlignmentError` because a negative cutoff is
    invalid regardless of what (if anything) the caller passes for bias;
    it is a cutoff-domain violation, not a Bias-alignment one."""


class BiasAlignmentError(Exception):
    """Invalid caller state: the BiasEvidence handed to a policy is not the
    one observed at `cutoff_index`. Named and raised in the style of
    `core.pairing_table.PairingError` / `ingestion.loader.LoadError` — the
    repo's convention for a contract a caller can only violate by having a
    bug."""


@dataclass(frozen=True)
class DirectionDecision:
    """`policy_id` IS the version — no separate `policy_version` field, it
    would only restate the suffix. Order Flow evidence is carried by
    REFERENCE (`order_flow_confirmation_index`), never as an embedded event.
    There is no `bias_observation_index` field either: the alignment
    invariant pins it to `cutoff_index`, so it would carry no information.
    """

    policy_id: str
    cutoff_index: int
    direction: DirectionOutcome
    order_flow_confirmation_index: int | None
    order_flow_direction: Direction | None
    normalized_bias_direction: DirectionOutcome | None
    reason: DirectionReason


def _require_valid_cutoff(cutoff_index: int) -> None:
    """`cutoff_index < 0` is covered by NEITHER of `_require_aligned_bias`'s
    two branches (`== 0`, `>= 1`) — it must be rejected on its own, first,
    before any Bias-specific logic runs, so a negative cutoff cannot be
    smuggled past validation by an artificially constructed BiasEvidence
    whose `observation_index` happens to match it."""
    if cutoff_index < 0:
        raise CutoffDomainError(
            f"cutoff_index must be >= 0 (no OHLCSeries position is negative), "
            f"got {cutoff_index}"
        )


def _require_aligned_bias(bias_evidence: BiasEvidence | None, cutoff_index: int) -> None:
    """The V1 domain contract. `detect_bias_evidence` is DENSE on 1..N-1 —
    index 0 yields no evidence, every later index yields exactly one — so
    presence is not optional:

        cutoff_index == 0  ->  bias_evidence MUST be absent
        cutoff_index >= 1  ->  bias_evidence MUST be present, observed
                               EXACTLY at cutoff_index

    An absent bias at a later cutoff is therefore a caller bug, not a
    "missing evidence" case: accepting it would silently run a different,
    undocumented policy on structural evidence alone. Exact alignment
    (rather than `<=`) is what keeps arbitrarily stale evidence — a
    cutoff of 500 reading an observation from index 220 — from becoming a
    hidden staleness policy nobody wrote down.
    """
    if cutoff_index == 0:
        if bias_evidence is not None:
            raise BiasAlignmentError(
                f"bias_evidence must be absent at cutoff_index 0 (no candle precedes "
                f"index 0), got observation_index {bias_evidence.observation_index}"
            )
        return
    if bias_evidence is None:
        raise BiasAlignmentError(
            f"bias_evidence is required at cutoff_index {cutoff_index}: BiasEvidence is "
            f"dense from index 1 onward, so its absence is invalid caller state"
        )
    if bias_evidence.observation_index != cutoff_index:
        raise BiasAlignmentError(
            f"bias_evidence must be observed exactly at cutoff_index {cutoff_index}, got "
            f"observation_index {bias_evidence.observation_index}"
        )


def _decide(
    policy_id: str,
    normalize: Callable[[BiasEvidence], DirectionOutcome],
    combine: Callable[[Direction | None, DirectionOutcome], DirectionOutcome],
    order_flow_events: list[OrderFlowEvent],
    bias_evidence: BiasEvidence | None,
    cutoff_index: int,
) -> DirectionDecision:
    """The shared body of all four policies: they differ ONLY in which
    normalizer and combiner they bind, so the pipeline itself is written
    once and the identity of each policy stays a single readable line."""
    _require_valid_cutoff(cutoff_index)
    _require_aligned_bias(bias_evidence, cutoff_index)

    event = relevant_order_flow_event(order_flow_events, cutoff_index)
    of_direction = None if event is None else event.direction
    # An absent bias (cutoff 0 only) enters the combiner as `unresolved`:
    # "no bias" and "a bias that resolved to nothing" are the same amount
    # of evidence. The distinction survives in the reported field.
    bias_direction = "unresolved" if bias_evidence is None else normalize(bias_evidence)
    direction = combine(of_direction, bias_direction)

    return DirectionDecision(
        policy_id=policy_id,
        cutoff_index=cutoff_index,
        direction=direction,
        order_flow_confirmation_index=None if event is None else event.confirmation_index,
        order_flow_direction=of_direction,
        normalized_bias_direction=None if bias_evidence is None else bias_direction,
        reason=decision_reason(of_direction, bias_direction, direction),
    )


def direction_policy_structural_priority_v1(
    order_flow_events: list[OrderFlowEvent],
    bias_evidence: BiasEvidence | None,
    cutoff_index: int,
) -> DirectionDecision:
    """P1 = B-D + DB-B — structure outranks candle shape at both levels:
    structural evidence decides whenever it exists, and Bias only fills the
    gap where it does not."""
    return _decide(
        "direction_policy_structural_priority_v1",
        normalize_bias_close_only,
        combine_order_flow_priority,
        order_flow_events,
        bias_evidence,
        cutoff_index,
    )


def direction_policy_corroboration_v1(
    order_flow_events: list[OrderFlowEvent],
    bias_evidence: BiasEvidence | None,
    cutoff_index: int,
) -> DirectionDecision:
    """P2 = B-B + DB-A — the strict corner: corroboration is demanded at
    both levels, so a lone source never decides. That it reports
    `unresolved` often is its defining limitation, stated up front and
    deliberately never quantified here."""
    return _decide(
        "direction_policy_corroboration_v1",
        normalize_bias_strict_agreement,
        combine_strict_agreement,
        order_flow_events,
        bias_evidence,
        cutoff_index,
    )


def direction_policy_noncontradiction_v1(
    order_flow_events: list[OrderFlowEvent],
    bias_evidence: BiasEvidence | None,
    cutoff_index: int,
) -> DirectionDecision:
    """P3 = B-C + DB-D — self-similar: the same non-contradiction
    epistemics applied at both levels. The only V1 policy that can decide
    from wick-only evidence on a doji close."""
    return _decide(
        "direction_policy_noncontradiction_v1",
        normalize_bias_non_contradiction,
        combine_evidence_preserving,
        order_flow_events,
        bias_evidence,
        cutoff_index,
    )


def direction_policy_bias_veto_v1(
    order_flow_events: list[OrderFlowEvent],
    bias_evidence: BiasEvidence | None,
    cutoff_index: int,
) -> DirectionDecision:
    """P4 = B-D + DB-D — Bias can block, but never command Order Flow.

    CLARIFICATION-1 (normative): "Bias cannot independently overrule
    structural direction, but explicit disagreement can veto a resolved
    decision" means Bias IS a sufficient sole source when Order Flow is
    absent (DB-D's single-source cell); what it cannot do is FLIP a present
    Order Flow direction — only veto it to `unresolved`. The DB-D table
    governs this reading.
    """
    return _decide(
        "direction_policy_bias_veto_v1",
        normalize_bias_close_only,
        combine_evidence_preserving,
        order_flow_events,
        bias_evidence,
        cutoff_index,
    )
