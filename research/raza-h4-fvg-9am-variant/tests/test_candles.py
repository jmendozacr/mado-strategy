from raza_h4fvg.candles import classify_sweep_and_close


def test_inside_close_after_low_sweep():
    pos, side = classify_sweep_and_close(1.10, 1.09, 1.095, 1.085, 1.093)
    assert pos == "INSIDE"
    assert side == "LOW_ONLY"


def test_outside_close_after_high_sweep():
    pos, side = classify_sweep_and_close(1.10, 1.09, 1.105, 1.095, 1.102)
    assert pos == "OUTSIDE"
    assert side == "HIGH_ONLY"


def test_exact_boundary_within_tolerance():
    pos, _ = classify_sweep_and_close(1.10, 1.09, 1.105, 1.085, 1.10)
    assert pos == "EXACT_BOUNDARY"


def test_double_sweep_detected():
    _, side = classify_sweep_and_close(1.10, 1.09, 1.105, 1.085, 1.095)
    assert side == "BOTH"


def test_neither_side_swept():
    _, side = classify_sweep_and_close(1.10, 1.09, 1.098, 1.092, 1.095)
    assert side == "NEITHER"
