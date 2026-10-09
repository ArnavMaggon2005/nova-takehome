"""Deterministic checks on model output: every number must be printed on the line it cites.

A number found on a different line of the same page is accepted and its reference repaired; a number found nowhere in
the document is an error. Errors are fed back to the model once (extract.py) and then lower the extraction confidence.
"""
from __future__ import annotations

from .money import dec, number_in_text

NUMERIC_KEYS = {"qty", "rate", "amount", "principal", "rate_pct", "fee", "pct", "inr_per_usd", "threshold_usd",
                "low_kg", "high_kg", "chargeable_weight", "actual_weight", "total", "subtotal", "tax_amount",
                "flat_rate_pct", "weight", "quantity", "pieces"}
REF_KEYS = ("ref", "id_ref", "total_ref", "date_ref")


def _line(pages_lines: list[list[str]], page: int, line: int) -> str | None:
    if 1 <= page <= len(pages_lines) and 1 <= line <= len(pages_lines[page - 1]):
        return pages_lines[page - 1][line - 1]
    return None


def _locate(pages_lines, value, page_hint: int) -> tuple[int, int] | None:
    """Find a line holding `value`, preferring the hinted page; None when absent everywhere."""
    order = [page_hint] + [p for p in range(1, len(pages_lines) + 1) if p != page_hint]
    for p in order:
        if not 1 <= p <= len(pages_lines):
            continue
        for i, text in enumerate(pages_lines[p - 1], 1):
            if number_in_text(value, text):
                return p, i
    return None


def check(data, pages: list[str]) -> tuple[list[str], dict]:
    """-> (errors, stats). Repairs refs in place when a number is on another line."""
    pages_lines = [p.split("\n") for p in pages]
    errors: list[str] = []
    stats = {"checked": 0, "ok": 0, "repaired": 0, "missing": 0}

    def visit(obj, path: str):
        if isinstance(obj, list):
            for i, x in enumerate(obj):
                visit(x, f"{path}[{i}]")
            return
        if not isinstance(obj, dict):
            return
        ref = obj.get("ref") if isinstance(obj.get("ref"), dict) else None
        if ref is None and isinstance(obj.get("span"), dict):
            sp = obj["span"]
            ref = {"page": sp.get("page"), "line": sp.get("line_from")}
        for k, v in obj.items():
            if isinstance(v, (dict, list)):
                visit(v, f"{path}.{k}")
                continue
            if k not in NUMERIC_KEYS or v in (None, "") or dec(v) is None:
                continue
            r = ref
            if k == "total" and isinstance(obj.get("total_ref"), dict):
                r = obj["total_ref"]
            if r is None:
                continue
            stats["checked"] += 1
            page, line = int(r.get("page") or 1), int(r.get("line") or 0)
            text = _line(pages_lines, page, line) or ""
            span_text = " ".join(filter(None, (_line(pages_lines, page, line + d) for d in (-1, 0, 1))))
            if number_in_text(v, text):
                stats["ok"] += 1
            elif number_in_text(v, span_text):
                stats["ok"] += 1
            else:
                hit = _locate(pages_lines, v, page)
                if hit:
                    stats["repaired"] += 1
                    if r is obj.get("ref"):
                        r["page"], r["line"] = hit
                else:
                    stats["missing"] += 1
                    errors.append(f"{path}.{k} = {v!r} is not printed on page {page} line {line} "
                                  f"({text[:90]!r}) nor anywhere else in the document")
        # rate rows carry a list of per-period rates under one ref
        if isinstance(obj.get("rates"), list) and ref is not None:
            text = _line(pages_lines, int(ref.get("page") or 1), int(ref.get("line") or 0)) or ""
            for j, rr in enumerate(obj["rates"]):
                if isinstance(rr, dict) and rr.get("rate") is not None:
                    stats["checked"] += 1
                    if number_in_text(rr["rate"], text):
                        stats["ok"] += 1
                    else:
                        stats["missing"] += 1
                        errors.append(f"{path}.rates[{j}].rate = {rr['rate']!r} is not on its row line ({text[:90]!r})")

    visit(data, "$")
    return errors, stats


def confidence(stats: dict) -> float:
    n = stats.get("checked", 0)
    if not n:
        return 0.9
    return max(0.0, min(1.0, (stats["ok"] + stats["repaired"] * 0.9) / n))
