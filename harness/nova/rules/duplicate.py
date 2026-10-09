"""Duplicates (GLOSSARY: Duplicates).

1. The same invoice number sent again: a finding only when the latest AP register shows it paid (or scheduled) and
   the resend asks for payment again; amount = the invoice total.
2. Two invoice numbers billing the same shipment line (same AWB incl. house suffix, same Annex E code, same quantity;
   monthly charges: same code and month): flag the invoice with the later date; amount = the duplicated lines on it,
   less any credit note referencing that invoice.
Returns the outcomes and the lines they consume (excluded from the overcharge rule so money isn't counted twice).
"""
from __future__ import annotations

from decimal import Decimal

import config

from ..money import ZERO, month_of, parse_date, to_usd
from ..outcome import Outcome
from ..world import World, norm_id

LINE_KINDS = {"freight", "fuel", "security", "dg", "dry_ice", "storage", "delivery", "customs", "peak",
              "account_fee", "programme_fee", "handling", "other"}


def evaluate(world: World) -> tuple[list[Outcome], set]:
    out: list[Outcome] = []
    consumed: set = set()
    ledger = world.ledger()
    copies: dict[str, list] = {}
    for inv in sorted(world.invoices, key=lambda i: i.received):
        copies.setdefault(inv.invoice_id, []).append(inv)
    # 1. resends of the same number
    for iid, invs in copies.items():
        if len(invs) < 2:
            continue
        first = invs[0]
        for later in invs[1:]:
            consumed.update((later.doc_id, l.idx) for l in later.lines)
            email = world.emails.get(later.eml_id) or {}
            refs = [r for r in email.get("invoice_refs") or [] if norm_id(r.get("invoice_id")) == iid]
            asks = any(r.get("asks_for_payment") for r in refs)
            row = ledger.get(iid)
            if not asks or row is None:
                continue
            resend_day = parse_date(later.received[:10])
            paid = row.status == "scheduled" or (row.status == "paid" and row.paid_date is not None and (
                not config.ASSUME_RESEND_NEEDS_PAYMENT_BEFORE_RESEND or row.paid_date <= resend_day))
            if not paid:
                continue
            c = world.contract_for(first)
            total = later.total if later.total is not None else row.amount
            if total is None:
                continue
            fx = world.fx_rate(c, month_of(first.issue_date)) if (c and first.currency != "USD" and first.issue_date) else None
            usd = to_usd(total, first.currency, fx[0] if fx else None)
            if usd is None:
                continue
            ask_src = next((_ref_src(world, later.eml_id, r) for r in refs if r.get("asks_for_payment")), None)
            o = Outcome("duplicate", "finding", invoice_id=iid, amount_usd=usd, contract=c,
                        shipments=[(l.awb, world.pickup(l.awb, l.pickup_printed)[1]) for l in later.lines if l.awb],
                        fact_levels=[3], inr=first.currency != "USD")
            o.evidence = [s for s in (row.src, ask_src, later.total_src) if s]
            o.features.update(scan=later.is_scan, extraction_conf=later.conf, native_amount=total)
            out.append(o)
            break
    # 2. the same shipment line on two invoice numbers
    firsts = [v[0] for v in copies.values()]
    index: dict[tuple, list] = {}
    for inv in firsts:
        c = world.contract_for(inv)
        for l in inv.lines:
            if l.kind not in LINE_KINDS:
                continue
            if l.kind in ("account_fee", "programme_fee"):
                if not l.ref_period:
                    continue
                k = (c.id if c else None, None, l.code or l.kind, l.ref_period, None)
            else:
                if not l.awb:
                    continue
                qty = l.qty if config.ASSUME_DUPLICATE_LINE_NEEDS_SAME_QTY else None
                k = (c.id if c else None, l.awb, l.code or l.kind, None, qty)
            index.setdefault(k, []).append((inv, l))
    per_invoice: dict[str, list] = {}
    for k, hits in index.items():
        if len({inv.invoice_id for inv, _ in hits}) < 2:
            continue
        hits.sort(key=lambda h: (h[0].issue_date or parse_date(h[0].received[:10]), h[0].received))
        first_inv = hits[0][0]
        for inv, l in hits[1:]:
            if inv.invoice_id == first_inv.invoice_id:
                continue
            per_invoice.setdefault(inv.invoice_id, []).append((inv, l, hits[0]))
    for iid, items in per_invoice.items():
        inv = items[0][0]
        c = world.contract_for(inv)
        amount = sum((l.amount for _, l, _ in items), ZERO)
        credit = sum((cn.total or ZERO for cn in world.credit_notes
                      if iid in {norm_id(x) for x in (cn.credit or {}).get("invoice_ids") or []}), ZERO)
        amount -= min(credit, amount)
        if amount <= 0:
            consumed.update((inv.doc_id, l.idx) for _, l, _ in items)
            continue
        fx = world.fx_rate(c, month_of(inv.issue_date)) if (c and inv.currency != "USD" and inv.issue_date) else None
        usd = to_usd(amount, inv.currency, fx[0] if fx else None)
        if usd is None:
            continue
        consumed.update((inv.doc_id, l.idx) for _, l, _ in items)
        o = Outcome("duplicate", "finding", invoice_id=iid, amount_usd=usd, contract=c, fact_levels=[3],
                    features={"native_amount": amount},
                    shipments=[(l.awb, world.pickup(l.awb, l.pickup_printed)[1]) for _, l, _ in items if l.awb],
                    inr=inv.currency != "USD")
        o.evidence = [s for _, l, (_, fl) in items for s in (fl.src, l.src) if s]
        alias = c.alias_src.get(items[0][1].code) if c else None
        if alias:
            o.evidence.append(alias)
        o.features.update(scan=inv.is_scan, extraction_conf=inv.conf)
        out.append(o)
    return out, consumed


def _ref_src(world: World, eml_id: str, ref: dict):
    from ..world import Src
    d = world.docs.get(eml_id)
    return Src.of(d, ref.get("ref")) if d else None
