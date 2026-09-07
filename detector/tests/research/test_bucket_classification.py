import pytest

from research.bucket_classification import classify

# Mapping-verification: all 4 input combinations map to the documented
# bucket exactly. Each case's comment states the real-world meaning of
# that bucket, per `classify`'s own docstring.
_CASES = [
    pytest.param("aligned", "aligned", "A", id="both-aligned-A"),
    pytest.param("opposed", "aligned", "B", id="only-displacement-aligned-B"),
    pytest.param("aligned", "opposed", "C", id="only-ob-aligned-C"),
    pytest.param("opposed", "opposed", "D", id="both-opposed-D"),
]


@pytest.mark.parametrize("ob_alignment, displacement_alignment, expected_bucket", _CASES)
def test_classify_maps_every_combination_to_its_documented_bucket(
    ob_alignment, displacement_alignment, expected_bucket
):
    assert classify(ob_alignment, displacement_alignment) == expected_bucket
