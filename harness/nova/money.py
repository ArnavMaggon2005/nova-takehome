"""Money and number helpers. Decimal only; the only rounding anywhere is half up to cents (GLOSSARY: Amounts)."""
from __future__ import annotations

import re
from datetime import date, datetime, timedelta
from decimal import ROUND_HALF_UP, Decimal, InvalidOperation

CENT = Decimal("0.01")
ZERO = Decimal("0")


def round2(x: Decimal) -> Decimal:
    return Decimal(x).quantize(CENT, rounding=ROUND_HALF_UP)


def dec(x) -> Decimal | None:
    """Parse '1,701.31', 'USD 2,493.71', 'INR127,024.44', '23.23%', 1701.31 -> Decimal; None when there is no number."""
    if x is None:
        return None
    if isinstance(x, Decimal):
        return x
    if isinstance(x, (int, float)) and not isinstance(x, bool):
        return Decimal(str(x))
    s = str(x).strip()
    m = re.search(r"-?\d[\d,]*(?:\.\d+)?|-?\.\d+", s.replace("−", "-"))
    if not m:
        return None
    try:
        return Decimal(m.group(0).replace(",", ""))
    except InvalidOperation:
        return None


def pct(p: Decimal, base: Decimal) -> Decimal:
    """p percent of base, rounded half up to cents."""
    return round2(Decimal(p) / Decimal(100) * Decimal(base))


def line_amount(rate: Decimal, qty: Decimal) -> Decimal:
    return round2(Decimal(rate) * Decimal(qty))


def to_usd(amount: Decimal, currency: str, fx: Decimal | None) -> Decimal | None:
    """Convert once per finding: round_half_up(amount_inr / fx, 2). USD passes through. None if fx is missing."""
    if (currency or "USD").upper() == "USD":
        return round2(amount)
    if fx is None or fx == 0:
        return None
    return round2(Decimal(amount) / Decimal(fx))


def money_str(x: Decimal) -> str:
    return f"{round2(x):.2f}"


def number_tokens(text: str) -> set[str]:
    """Every number in a line, normalised (thousands separators dropped, trailing zeros kept as written and stripped)."""
    out = set()
    for m in re.finditer(r"\d[\d,]*(?:\.\d+)?", text or ""):
        raw = m.group(0).rstrip(",")
        flat = raw.replace(",", "")
        out.add(flat)
        try:
            d = Decimal(flat)
            out.add(format(d.normalize(), "f"))
            out.add(f"{d:.2f}")
        except InvalidOperation:
            pass
    return out


def number_in_text(value, text: str) -> bool:
    """Does a number appear in text (ignoring thousands separators and trailing zeros)?"""
    d = dec(value)
    if d is None:
        return False
    toks = number_tokens(text)
    return any(t in toks for t in (format(d, "f"), format(d.normalize(), "f"), f"{d:.2f}"))


# ---- dates --------------------------------------------------------------------------------------------------------
def parse_date(s) -> date | None:
    """ISO 'YYYY-MM-DD' (what the extractor is asked to return). Anything else -> None."""
    if s is None:
        return None
    if isinstance(s, datetime):
        return s.date()
    if isinstance(s, date):
        return s
    m = re.match(r"^\s*(\d{4})-(\d{2})-(\d{2})", str(s))
    if not m:
        return None
    try:
        return date(int(m.group(1)), int(m.group(2)), int(m.group(3)))
    except ValueError:
        return None


def month_of(d: date) -> str:
    return f"{d.year:04d}-{d.month:02d}"


def quarter_of(d: date) -> str:
    return f"{d.year:04d}-Q{(d.month - 1) // 3 + 1}"


def quarter_bounds(period: str) -> tuple[date, date]:
    y, q = int(period[:4]), int(period[-1])
    start = date(y, 3 * (q - 1) + 1, 1)
    end_month = 3 * q
    end = (date(y + (end_month == 12), (end_month % 12) + 1, 1) - timedelta(days=1))
    return start, end


def add_years(d: date, n: int) -> date:
    try:
        return d.replace(year=d.year + n)
    except ValueError:                       # 29 Feb
        return d.replace(year=d.year + n, day=28)
