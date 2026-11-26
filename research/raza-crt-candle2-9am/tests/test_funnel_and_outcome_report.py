from raza_stats.funnel_and_outcome_report import (
    SYMBOLS,
    load_classifications,
    build_trigger_table,
    funnel_by_group,
    order_placement_vs_h4_close,
)


def test_funnel_by_group_sums_to_the_pooled_baseline():
    """Requirement: denominators reconcile exactly to the already-
    verified Phase 8-10 9AM baseline (8712 triggers, 3311 confirmed,
    1806 candidates, 1427 filled)."""
    data = load_classifications()
    rows = build_trigger_table(data)
    funnel = funnel_by_group(rows)
    assert funnel["TOTAL"]["n_signals"] == 8712
    assert funnel["TOTAL"]["confirmed"] == 3311
    assert funnel["TOTAL"]["candidate"] == 1806
    assert funnel["TOTAL"]["filled"] == 1427
    assert sum(funnel[g]["n_signals"] for g in ("INSIDE", "OUTSIDE", "EXACT_BOUNDARY", "MISSING_OR_INCOMPLETE")) == 8712


def test_order_is_never_placed_after_the_h4_close_under_the_current_9am_window():
    """The decisive timeline finding: the 9AM confirmation window's own
    deadline (13:00 NY) coincides with the current candle's own close
    -- an order can never be placed strictly AFTER that close under the
    EXISTING window design. Verified directly against the real ledger,
    never assumed."""
    data = load_classifications()
    rows = build_trigger_table(data)
    result = order_placement_vs_h4_close(rows)
    assert result["order_placed_after_1300"] == 0
    assert result["missing"] == 0
    assert result["total"] == 1427
