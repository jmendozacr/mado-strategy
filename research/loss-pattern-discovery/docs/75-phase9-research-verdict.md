# Deliverable H — Phase 9 Research Verdict

Criteria fixed in `docs/67` section 3, BEFORE the full 3-pair run. Reported exactly as
pre-registered, both dimensions independently, never collapsed into one label.

## Integrity dimension: `PARTIAL_IDENTITY_RECONCILIATION`

The `EVENT_LEVEL_RECONCILED` bar requires THREE things simultaneously: `fully_matched == True`,
ZERO duplicate `signal_id`s in either set, and the Phase 8 funnel counts/E1 endpoint reproducing
exactly. The first and third hold exactly (Deliverable A: 2047/2047, zero mismatches; Deliverable
A's `e1_endpoint` block reproduces Phase 5-8's numbers exactly). **The second does not**: 3
`signal_id` values are each shared by two different trades (6 rows total), found by
`detect_duplicate_signal_ids` and investigated (not silently accepted) in Deliverable A.

Per the pre-registered fallback, this is `PARTIAL_IDENTITY_RECONCILIATION`: the set difference is
fully explained (cross-instrument index collisions in `signal_id`'s own formula, verified from
source, zero impact on the TRUE primary key `stable_id`, zero impact on any prior phase's
findings), not an unexplained discrepancy. It falls short of the strict `EVENT_LEVEL_RECONCILED`
bar only because that bar's letter requires literally zero duplicates in either raw set,
regardless of whether they are harmless. The computed `validated_event_by_event` flag in
`artifacts/phase9_event_identity_reconciliation.json` is `False` for exactly this reason, and this
verdict reports that flag's result honestly rather than rounding it up.

## Selection dimension: `MULTIPLE_SELECTION_MECHANISMS`

Both pre-registered conditions hold simultaneously:

**`CONFIRMATION_REJECTIONS_DOMINATE`** (in absolute count removed, confirmation-stage rejection
exceeds Stage-6 rejection, for both models):

| | Confirmation-stage removed (triggers - confirmed) | Stage-6 removed (confirmed - candidates) |
|---|---|---|
| 1AM | **9401** | 1087 |
| 9AM | **5401** | 1505 |

9401 >> 1087 and 5401 >> 1505 -- holds for both models.

**`STAGE6_ATTRITION_MATERIAL`** (Stage-6 removes >=20% of `model1_confirmed` for either model):

| | Stage-6 removed / confirmed |
|---|---|
| 1AM | 1087 / 1805 = **60.2%** |
| 9AM | 1505 / 3311 = **45.5%** |

Both exceed the 20% bar (the criterion only required EITHER model; both satisfy it).

Since BOTH conditions hold simultaneously, the pre-registered logic assigns
`MULTIPLE_SELECTION_MECHANISMS`: the confirmation stage dominates the absolute count of rejected
events, AND the Stage-6 RR floor independently removes a large, material share of what does
confirm. Neither mechanism is negligible; neither alone explains the full 1AM/9AM selection
picture.

## Summary table

| Dimension | Verdict |
|---|---|
| Integrity | `PARTIAL_IDENTITY_RECONCILIATION` |
| Selection | `MULTIPLE_SELECTION_MECHANISMS` |

Both verdicts were determined by applying the Section 3 criteria mechanically to the computed
numbers above -- no criterion was adjusted after seeing the result.
