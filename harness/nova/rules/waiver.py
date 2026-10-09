"""Waived but billed (GLOSSARY: Waivers; MSA waiver-scope and conditional-waiver clauses).

A waiver counts when the sender's address is the contract's Schedule 1 *waivers* contact (or a person feedback
confirmed for that category, contract and date), it is in their own text, it names the shipment (AWB), the month or
the invoice, and any condition is shown to be met. It covers only the charge and shipments it names. A waiver seen
only quoted in someone else's email, with no original held, is cannot_determine (ask for the original). A one-off
approval in feedback makes the waiver count for the named months on that one key only.
"""
from __future__ import annotations

from datetime import date

import config

from ..money import ZERO, month_of, parse_date, to_usd
from ..outcome import Outcome
from ..terms import holder_for
from ..world import World, norm_id


def evaluate(world: World, skip_lines: set) -> tuple[list[Outcome], set]:
    firsts = {}
    for inv in sorted(world.invoices, key=lambda i: i.received):
        firsts.setdefault(inv.invoice_id, inv)
    hits: dict[str, dict] = {}
    cds: dict[str, Outcome] = {}
    for w in world.waivers:
        when = parse_date(w.received[:10]) or world.as_of
        for inv in firsts.values():
            c = world.contract_for(inv)
            if c is None:
                continue
            code, kind = c.code_for(w.label)
            lines = [l for l in inv.lines if (inv.doc_id, l.idx) not in skip_lines and _targets(w, inv, l)
                     and ((code and l.code == code) or l.kind == kind)]
            if not lines:
                continue
            if kind == "freight":
                awbs = {l.awb for l in lines}
                lines += [l for l in inv.lines if l.kind == "fuel" and l.awb in awbs]
            if not w.own_text:
                if _original_held(world, w):
                    continue
                cds.setdefault(inv.invoice_id, _cannot(world, w, inv, c, lines))
                continue
            ok, person, fb = world.authorised(c, w.sender_addr, w.sender_name, "waivers", when)
            if not ok:
                continue
            if w.conditional and w.condition_met != "yes":
                continue
            h = hits.setdefault(inv.invoice_id, {"inv": inv, "c": c, "lines": {}, "ev": [], "fb": []})
            for l in lines:
                h["lines"][l.idx] = l
            h["ev"] += [s for s in (w.src, person.src if person else None) if s]
            if fb is not None:
                h["fb"].append(fb)
    # one-off approvals: the waiver covers the named months on that key only
    for fb in world.feedback:
        if fb.decision != "one_off_approval" or fb.fact_type != "waiver_scope" or fb.key[0] != "waived_but_billed":
            continue
        inv = firsts.get(fb.key[1])
        if inv is None:
            continue
        c = world.contract_for(inv)
        months = {str(m)[:7] for m in (fb.value or {}).get("months") or []}
        person = str((fb.subject or {}).get("person") or "").lower()
        codes = {c.code_for(w.label) for w in world.waivers if " ".join(w.sender_name.split()).lower() == person}
        lines = [l for l in inv.lines if _line_month(l, inv) in months
                 and (not codes or any((cd and l.code == cd) or l.kind == k for cd, k in codes))]
        if not lines:
            continue
        h = hits.setdefault(inv.invoice_id, {"inv": inv, "c": c, "lines": {}, "ev": [], "fb": []})
        for l in lines:
            h["lines"][l.idx] = l
        h["fb"].append(fb)
        cds.pop(inv.invoice_id, None)
    out, consumed = [], set()
    for iid, h in hits.items():
        inv, c = h["inv"], h["c"]
        amount = sum((l.amount for l in h["lines"].values()), ZERO)
        if amount <= 0:
            continue
        fx = world.fx_rate(c, month_of(inv.issue_date)) if (inv.currency != "USD" and inv.issue_date) else None
        usd = to_usd(amount, inv.currency, fx[0] if fx else None)
        if usd is None:
            continue
        consumed.update((inv.doc_id, i) for i in h["lines"])
        o = Outcome("waived_but_billed", "finding", invoice_id=iid, amount_usd=usd, contract=c, fact_levels=[3],
                    term_levels=[2], shipments=[(l.awb, world.pickup(l.awb, l.pickup_printed)[1])
                                                for l in h["lines"].values() if l.awb],
                    inr=inv.currency != "USD", feedback_used=h["fb"], features={"native_amount": amount})
        o.evidence = h["ev"][:1] + [l.src for l in h["lines"].values() if l.src] + h["ev"][1:] + \
            ([c.spans["waiver_authority"]] if "waiver_authority" in c.spans else [])
        o.features.update(scan=inv.is_scan, extraction_conf=inv.conf)
        out.append(o)
    for iid, o in cds.items():
        if iid not in hits:
            out.append(o)
    return out, consumed


def _targets(w, inv, l) -> bool:
    if l.awb and l.awb in w.awbs:
        return True
    if w.months and _line_month(l, inv) in w.months:
        return True
    return bool(w.invoice_ids) and inv.invoice_id in w.invoice_ids and not w.awbs and not w.months


def _line_month(l, inv) -> str | None:
    if l.ref_period:
        return l.ref_period[:7]
    d = l.pickup_printed or inv.issue_date
    return month_of(d) if d else None


def _original_held(world: World, w) -> bool:
    name = " ".join(str(w.original.get("name") or "").split()).lower()
    addr = str(w.original.get("addr") or "").lower()
    for o in world.waivers:
        if o is w or not o.own_text:
            continue
        if (addr and o.sender_addr == addr) or (name and " ".join(o.sender_name.split()).lower() == name):
            if set(o.awbs) & set(w.awbs) or set(o.months) & set(w.months) or set(o.invoice_ids) & set(w.invoice_ids):
                return True
    return False


def _cannot(world: World, w, inv, c, lines) -> Outcome:
    name = str(w.original.get("name") or "").strip()
    addr = str(w.original.get("addr") or "").lower()
    person = next((p for p in c.persons if (addr and p.address == addr) or
                   (name and " ".join(p.name.split()).lower() == " ".join(name.split()).lower())), None)
    if person is not None and "waivers" in person.categories:
        holder = {"party": person.party, "person": person.name, "role": person.title}
    else:
        kam = c.kam("carrier")
        holder = {"party": kam.party, "person": kam.name, "role": kam.title} if kam else holder_for(c, "notices")
    cited = w.original.get("cited_as") or "original email"
    target = ", ".join(w.awbs or w.months or w.invoice_ids) or "-"
    nm = f"{cited} from {name or 'the original sender'}"
    if w.original.get("date"):
        nm += f" dated {w.original['date']}"
    if config.ASSUME_DESCRIPTIVE_MISSING_DOC_NAMES:
        nm += f" waiving the {w.label} on {target} (invoice {inv.printed_id or inv.invoice_id})"
    o = Outcome("waived_but_billed", "cannot_determine", invoice_id=inv.invoice_id, contract=c,
                missing_doc={"name": nm, "holder": holder}, remedy="request_document", fact_levels=[3])
    o.evidence = [s for s in [w.src] + [l.src for l in lines] if s]
    return o


__all__ = ["evaluate", "date"]
