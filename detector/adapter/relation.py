"""Group C (spec.md REQ-STAT-27): explicit, exhaustive mapping from
`evaluation.direction.PolicyRelation` to `selection.model.Relation` — no
permissive string cast. Kept as separate enums per layer boundary
(`.importlinter`'s `selection-layer1-purity` contract)."""

from adapter.errors import RelationMappingError
from evaluation.direction import PolicyRelation
from selection.model import Relation

_RELATION_MAP: dict[PolicyRelation, Relation] = {
    PolicyRelation.ALIGNED: Relation.ALIGNED,
    PolicyRelation.OPPOSED: Relation.OPPOSED,
    PolicyRelation.UNRESOLVED: Relation.UNRESOLVED,
}


def map_relation(policy_relation: PolicyRelation) -> Relation:
    try:
        return _RELATION_MAP[policy_relation]
    except KeyError:
        raise RelationMappingError(
            f"unexpected PolicyRelation value {policy_relation!r} — no permissive cast"
        ) from None
