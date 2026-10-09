"""Late fees (GLOSSARY: Late fees).

Not owed: for a billed late-fee line on invoice X, due = the latest due-date extension from the contract's Schedule 1
*payment_terms* contact (own text), else the ledger/invoice due date; paid = the ledger's paid date. No fee within the
grace days; otherwise ceil(days_late / 30) fee months, each round_half_up(r% x base) with simple or compounding base.
Finding = billed fee lines - expected fees, on the invoice that bills them.

Risk: an open invoice in the latest AP register whose (extended) due date is 1..14 days after as_of; amount = one
month's fee on the open amount less what we dispute on it, in the invoice currency, converted once.
"""
from __future__ import annotations

import math
from datetime import date
from decimal import Decimal

import config

from ..money import ZERO, month_of, parse_date, pct, to_usd
from ..outcome import Outcome
from ..world import World, norm_id


def due_date(world: World, iid: str, base_due: date | None, contract) -> tuple[date | None, object]:
    """(effective due date, extension record or None)."""
    best = None
    for x in world.extensions:
        if x["invoice_id"] != iid or not x["own_text"]:
            continue
        if contract is not None:
            ok, _, _ = world.authorised(contract, x["sender_addr"], x["sender_name"] or "", "payment_terms",
                                        parse_date(x["received"][:10]))
            if not ok:
                continue
        if best is None or x["received"] > best["received"]:
            best = x
    return (best["new_due"], best) if best else (base_due, None)


def _invoice_doc(world: World, iid: str):
    for inv in sorted(world.invoices, key=lambda i: i.received):
        if inv.invoice_id == iid:
            return inv
    return None


def expected_fees(principal: Decimal, rate: Decimal, n: int, compounding: bool) -> list[Decimal]:
    fees, base = [], principal
    for _ in range(n):
        f = pct(rate, base)
        fees.append(f)
        if compounding:
            base = base + f
    return fees


def evaluate_not_owed(world: World) -> list[Outcome]:
    ledger = world.ledger()
    out = []
    seen = set()
    for inv in sorted(world.invoices, key=lambda i: i.received):
        if inv.invoice_id in seen:
            continue
        seen.add(inv.invoice_id)
        fee_lines = [l for l in inv.lines if l.kind == "late_fee" and (l.late_fee or {}).get("invoice_id")]
        if not fee_lines:
            continue
        c = world.contract_for(inv)
        if c is None or c.late_rate is None:
            continue
        diff = ZERO
        ev, used = [], []
        for l in fee_lines:
            x = norm_id(l.late_fee["invoice_id"])
            row = ledger.get(x)
            xdoc = _invoice_doc(world, x)
            base_due = (row.due_date if row else None) or (xdoc.due_date if xdoc else None)
            due, ext = due_date(world, x, base_due, world.contract_for(xdoc) if xdoc else c)
            if row is None or due is None:
                continue
            if row.paid_date is None:          # A10: no paid date, nothing to count from (and never guess one)
                continue
            days_late = (row.paid_date - due).days
            principal = row.amount if row.amount is not None else Decimal(str(l.late_fee.get("principal") or 0))
            n = 0 if days_late <= c.grace_days else math.ceil(days_late / 30)
            fees = expected_fees(principal, c.late_rate, n, c.compounding)
            m = int(l.late_fee.get("month_index") or 1)
            expected = fees[m - 1] if 1 <= m <= len(fees) else ZERO
            if l.amount - expected > 0:
                diff += l.amount - expected
                ev += [s for s in (ext["src"] if ext else None, row.src, l.src) if s]
        if diff <= 0:
            continue
        fx = world.fx_rate(c, month_of(inv.issue_date)) if (inv.currency != "USD" and inv.issue_date) else None
        usd = to_usd(diff, inv.currency, fx[0] if fx else None)
        if usd is None:
            continue
        o = Outcome("late_fee_not_owed", "finding", invoice_id=inv.invoice_id, amount_usd=usd, contract=c,
                    fact_levels=[3], term_levels=[1, 2], inr=inv.currency != "USD", feedback_used=used)
        o.evidence = ev + [c.spans[k] for k in ("extension", "late_fee") if k in c.spans]
        o.features.update(scan=inv.is_scan, extraction_conf=inv.conf)
        out.append(o)
    return out


def evaluate_risk(world: World, disputed_by_invoice: dict) -> list[Outcome]:
    ledger = world.ledger()
    out = []
    for iid, row in ledger.items():
        if row.status in ("paid", "credited") or row.paid_date is not None:
            continue
        xdoc = _invoice_doc(world, iid)
        c = world.contract_for(xdoc) if xdoc else _contract_by_currency(world, row.currency)
        if c is None or c.late_rate is None:
            continue
        due, ext = due_date(world, iid, row.due_date or (xdoc.due_date if xdoc else None), c)
        if due is None:
            continue
        gap = (due - world.as_of).days
        if not 0 < gap <= config.RISK_WINDOW_DAYS:
            continue
        principal = row.amount if row.amount is not None else (xdoc.total if xdoc else None)
        if principal is None:
            continue
        currency = (row.currency or (xdoc.currency if xdoc else "USD") or "USD").upper()
        if config.ASSUME_RISK_PRINCIPAL_EXCLUDES_OUR_DISPUTES:
            principal -= disputed_by_invoice.get(iid, ZERO)
        fee = pct(c.late_rate, max(principal, ZERO))
        idate = row.invoice_date or (xdoc.issue_date if xdoc else None)
        fx = world.fx_rate(c, month_of(idate)) if (currency != "USD" and idate) else None
        usd = to_usd(fee, currency, fx[0] if fx else None)
        if usd is None:
            continue
        o = Outcome("late_fee_risk", "finding", invoice_id=iid, amount_usd=usd, deadline=due, contract=c,
                    remedy="payment_reminder", fact_levels=[3], inr=currency != "USD")
        o.evidence = [s for s in (row.src, ext["src"] if ext else None) if s] + \
            ([c.spans["late_fee"]] if "late_fee" in c.spans else [])
        o.features["boundary"] = gap in (1, config.RISK_WINDOW_DAYS)
        out.append(o)
    return out


def _contract_by_currency(world: World, currency):
    cs = [c for c in world.contracts.values() if c.currency == (currency or "USD").upper()]
    return cs[0] if len(cs) == 1 else None
