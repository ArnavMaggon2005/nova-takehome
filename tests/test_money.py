"""Decimal half-up rounding and number parsing (GLOSSARY: Amounts). Values are invented."""
from __future__ import annotations

import sys
from decimal import Decimal as D
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "harness"))
from nova.money import dec, line_amount, number_in_text, pct, quarter_bounds, round2, to_usd  # noqa: E402


def test_half_up_ties_away_from_zero():
    assert round2(D("2.345")) == D("2.35")
    assert round2(D("2.344999")) == D("2.34")
    assert round2(D("-2.345")) == D("-2.35")


def test_line_and_percent():
    assert line_amount(D("6.01"), D("241")) == D("1448.41")
    assert pct(D("20.16"), D("1448.41")) == D("292.00")


def test_inr_once_per_finding():
    assert to_usd(D("7438.14"), "INR", D("87.04")) == D("85.46")
    assert to_usd(D("10"), "INR", None) is None
    assert to_usd(D("12.345"), "USD", None) == D("12.35")


def test_parse_printed_numbers():
    assert dec("1,701.31") == D("1701.31")
    assert dec("INR127,024.44") == D("127024.44")
    assert dec("23.23%") == D("23.23")
    assert dec("n/a") is None
    assert number_in_text("1701.31", "QQX1 AB123 Air freight 299 kg 5.69 1,701.31 19/05/2041")
    assert number_in_text("85", "Charge 85.00 USD")
    assert not number_in_text("5.70", "rate 5.69")


def test_quarter_bounds():
    assert quarter_bounds("2041-Q1") == (__import__("datetime").date(2041, 1, 1), __import__("datetime").date(2041, 3, 31))
    assert quarter_bounds("2041-Q4")[1].isoformat() == "2041-12-31"
