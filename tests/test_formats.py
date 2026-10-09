"""Formats the practice files never show: other date styles, route separators and Schedule 1 category wording."""
from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "harness"))

from nova.extract import _numeric_order, parse_loose_date, parse_table  # noqa: E402
from nova.world import norm_categories, norm_lane  # noqa: E402


def test_loose_dates():
    assert parse_loose_date("2041-07-09") == "2041-07-09"
    assert parse_loose_date("09-Jul-2041") == "2041-07-09"
    assert parse_loose_date("9 July 2041") == "2041-07-09"
    assert parse_loose_date("Jul 9, 2041") == "2041-07-09"
    assert parse_loose_date("2041/07/09") == "2041-07-09"
    assert parse_loose_date("09.07.2041") == "2041-07-09"
    assert parse_loose_date("07/09/2041", "month_first") == "2041-07-09"
    assert parse_loose_date("-") is None and parse_loose_date(None) is None


def test_column_order_inference():
    assert _numeric_order(["03/04/2041", "25/04/2041"]) == "day_first"
    assert _numeric_order(["04/03/2041", "04/25/2041"]) == "month_first"


def test_lane_separators():
    assert norm_lane("BOS → LAX") == norm_lane("BOS-LAX") == norm_lane("bos – lax") == "BOS-LAX"
    assert norm_lane("BOS to LAX") == "BOS-LAX"


def test_category_synonyms():
    assert norm_categories(["Pricing", "payment terms"]) == {"rates", "payment_terms"}
    assert norm_categories(["billing disputes"]) == {"billing_disputes"}
    assert norm_categories(["Waiver approvals", "FX / treasury"]) == {"waivers", "treasury"}
    assert norm_categories(["notices"]) == {"notices"}


def test_table_rows_with_text_dates_and_shared_currency_cell():
    page = "\n".join(["Milestone | Waybill no. | Date | Location",
                      "Collected | QZ1000001 | 09-Jul-2041 | XAA",
                      "Delivered | QZ1000001 | 12-Jul-2041 | XBB"])
    spec = {"table_kind": "tracking_export", "sheet": 1, "header_line": 1,
            "columns": {"event": 0, "awb": 1, "event_date": 2, "station": 3},
            "event_values": [{"printed": "Collected", "meaning": "PICKED_UP"},
                             {"printed": "Delivered", "meaning": "DELIVERED"}]}
    rows = parse_table(spec, [page])
    assert [(r["awb"], r["event"], r["date"]) for r in rows] == [("QZ1000001", "PICKED_UP", "2041-07-09"),
                                                                  ("QZ1000001", "DELIVERED", "2041-07-12")]
