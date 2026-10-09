"""Overcharge: a line billed above what the contract allowed on the pickup date (GLOSSARY: Amounts).

Each line is repriced from the contract's own terms: freight from the resolved rate (band containing the printed
quantity, period containing the pickup date, minimum charge), fuel from the pickup month's percentage on the repriced
freight, security per kg, accessorials from Annex D with their conditions (dry ice vs dangerous goods from the
declaration, storage days from tracking, delivery only if the carrier delivered, customs only if the carrier didn't
cause the hold, peak months). A line whose correct value can't be established is accepted (ASSUME_UNVERIFIABLE...).
"""
from __future__ import annotations

from datetime import timedelta
from decimal import Decimal

import config

from ..money import ZERO, line_amount, month_of, pct, to_usd
from ..outcome import Outcome
from ..terms import resolve_rate
from ..world import Src, World

SHIPMENT_KINDS = {"freight", "fuel", "security", "dg", "dry_ice", "storage", "delivery", "customs", "peak"}


def evaluate(world: World, skip_lines: set) -> list[Outcome]:
    out = []
    seen = set()
    for inv in sorted(world.invoices, key=lambda i: i.received):
        if inv.invoice_id in seen:                     # later copies of the same number are the duplicate rule's
            continue
        seen.add(inv.invoice_id)
        c = world.contract_for(inv)
        if c is None:
            continue
        o = _invoice(world, inv, c, skip_lines)
        if o is not None:
            out.append(o)
    return out


def _invoice(world: World, inv, c, skip_lines: set) -> Outcome | None:
    # per line: list of (expected under option 0, expected under option 1 ...) or a single expected value
    by_awb: dict = {}
    for l in inv.lines:
        if (inv.doc_id, l.idx) in skip_lines or l.kind in ("late_fee", "duty", "tax", "margin", "cost"):
            continue
        by_awb.setdefault(l.awb or f"~{l.ref_period or l.idx}", []).append(l)
    diffs = []            # (line, [diff per option]) ; options count 1 unless a conflict
    evidence: list[Src] = []
    missing = None
    conflict = None
    shipments, conflict_keys, term_levels, feats = [], [], [], {"boundary": False}
    pickup_decides = False
    for awb, lines in by_awb.items():
        pickup, psource, psrc = world.pickup(lines[0].awb, next((l.pickup_printed for l in lines if l.pickup_printed),
                                                                None))
        freight_exp = None                 # list per option
        res = None
        for l in [x for x in lines if x.kind == "freight"]:
            if pickup is None or l.qty is None or not (l.lane or _lane(lines)):
                continue
            res = resolve_rate(world, c, l.lane or _lane(lines), l.qty, pickup)
            if res.status == "missing":
                missing = (res, l, inv)
                continue
            if res.status == "none":
                continue
            exps = [max(line_amount(o.rate, l.qty), o.minimum or ZERO) for o in res.options]
            freight_exp = [(freight_exp[i] if freight_exp else ZERO) + e for i, e in enumerate(exps)]
            diffs.append((l, [l.amount - e for e in exps], res))
            if res.status == "conflict":
                conflict = res
            term_levels += [o.level for o in res.options]
            conflict_keys.append((c.id, l.lane or _lane(lines), "freight", res.period))
            _boundary(feats, l.qty, l.lane or _lane(lines), pickup, c)
        for l in lines:
            if l.kind == "freight":
                continue
            exp = _expected_other(world, c, l, lines, pickup, freight_exp, evidence)
            if exp is None:
                continue
            diffs.append((l, [l.amount - e for e in exp] if isinstance(exp, list) else [l.amount - exp], None))
        if any(l.kind in ("freight", "fuel", "peak") for l in lines):
            pickup_decides = True
        if lines[0].awb:
            shipments.append((lines[0].awb, psource))
        if psrc is not None:
            evidence.append(psrc)
        feats.setdefault("pickup_sources", []).append(psource)
    n_opt = max((len(d) for _, d, _ in diffs), default=1)
    totals = []
    for i in range(n_opt):
        t = ZERO
        for _, d, _ in diffs:
            v = d[i] if i < len(d) else d[0]
            if v > 0 or not config.ASSUME_OVERCHARGE_POSITIVE_LINES_ONLY:
                t += v
        totals.append(t)
    wrong_lines = [l for l, d, _ in diffs if max(d) > 0]
    line_srcs = [l.src for l in wrong_lines if l.src]
    o = Outcome("overcharge", "no_finding", invoice_id=inv.invoice_id, contract=c, shipments=shipments,
                pickup_decides=pickup_decides, conflict_keys=conflict_keys, term_levels=term_levels,
                fact_levels=[3], inr=inv.currency != "USD")
    o.features.update(feats)
    o.features["scan"] = inv.is_scan
    o.features["extraction_conf"] = inv.conf
    if missing is not None:
        res, l, _ = missing
        if (l.amount > 0):
            m = res.missing
            o.verdict = "cannot_determine"
            o.remedy = "request_document"
            o.missing_doc = {"name": _missing_name(m, inv, l), "holder": m["holder"]}
            o.evidence = [s for s in [m["src"], l.src] if s] + res.clause_srcs
            return o
    fx = None
    if inv.currency != "USD":
        fx = world.fx_rate(c, month_of(inv.issue_date)) if inv.issue_date else None
    if conflict is not None and len(set(totals)) > 1:
        hi, lo = max(totals), min(totals)
        if hi <= 0:
            return None
        rng = [to_usd(max(ZERO, lo), inv.currency, fx[0] if fx else None),
               to_usd(hi, inv.currency, fx[0] if fx else None)]
        if None in rng:
            return _fx_missing(o, c, inv, line_srcs)
        o.verdict, o.amount_range, o.remedy = "conflict", tuple(rng), "escalate"
        opt_srcs = [s for opt in conflict.options for s in opt.srcs[:1]]
        o.evidence = opt_srcs + line_srcs + conflict.clause_srcs
        o.feedback_used += conflict.feedback_used
        return o
    total = totals[0]
    if total <= 0:
        return None if not wrong_lines else o
    usd = to_usd(total, inv.currency, fx[0] if fx else None)
    if usd is None:
        return _fx_missing(o, c, inv, line_srcs)
    o.verdict, o.amount_usd = "finding", usd
    o.features["native_amount"] = total
    rate_srcs = []
    for l, d, res in diffs:
        if res is not None and max(d) > 0:
            rate_srcs += [s for opt in res.options for s in opt.srcs[:1]] + res.clause_srcs
            o.feedback_used += res.feedback_used
    o.evidence = line_srcs + rate_srcs + evidence + ([fx[1]] if fx and fx[1] else [])
    return o


def _lane(lines) -> str | None:
    for l in lines:
        if l.lane:
            return l.lane
    return None


def _expected_other(world: World, c, l, lines, pickup, freight_exp, evidence):
    """Expected amount for a non-freight line: Decimal, list per rate option (fuel), or None if unverifiable."""
    if l.kind == "fuel":
        if pickup is None or freight_exp is None:
            return None
        f = world.fuel_pct(c, month_of(pickup))
        if f is None:
            return None
        if f[1]:
            evidence.append(f[1])
        return [pct(f[0], base) for base in freight_exp]
    acc = c.accessorial(l.kind)
    if l.kind == "security":
        if acc is None or l.qty is None:
            return None
        return line_amount(acc["fee"], l.qty)
    if l.kind in ("dg", "dry_ice"):
        items = world.dg.get(l.awb or "", [])
        if not items or acc is None:
            return None
        dry = [i for i in items if i.get("is_dry_ice") or str(i.get("un_number") or "").upper().endswith("1845")]
        other = [i for i in items if i not in dry]
        evidence += [i["src"] for i in items if i.get("src")]
        for k in ("dry_ice", "dg", "mixed_dg"):
            if k in c.spans:
                evidence.append(c.spans[k])
        qty = l.qty or Decimal(1)
        if l.kind == "dg":
            return ZERO if (dry and not other and all(i.get("refrigerant_only") for i in dry)) else acc["fee"] * qty
        return ZERO if other else acc["fee"] * qty
    if l.kind == "storage":
        free = c.storage_free_days
        evs = world.events.get(l.awb or "", [])
        rel = [e for e in evs if e.event in ("DELIVERED", "COLLECTED_BY_CONSIGNEE") and e.when]
        if free is None or acc is None or not rel:
            return None
        release = min(e.when for e in rel)
        arr = [e for e in evs if e.event == "ARRIVED_FACILITY" and e.when and e.when <= release]
        if not arr:
            return None
        arrival = max(e.when for e in arr)
        days = max(0, (release - arrival).days - int(free))
        evidence += [e.src for e in (arr[-1], rel[0]) if e.src]
        if "storage" in c.spans:
            evidence.append(c.spans["storage"])
        return line_amount(acc["fee"], Decimal(days))
    if l.kind == "delivery":
        if acc is None:
            return None
        evs = world.events.get(l.awb or "", [])
        collected = any(e.event == "COLLECTED_BY_CONSIGNEE" for e in evs)
        delivered = any(e.event == "DELIVERED" for e in evs)
        if c.delivery_only_if_delivered and collected and not delivered:
            evidence += [e.src for e in evs if e.event == "COLLECTED_BY_CONSIGNEE" and e.src]
            return ZERO
        return acc["fee"] * (l.qty or Decimal(1))
    if l.kind == "customs":
        if acc is None:
            return None
        notes = world.customs.get(l.awb or "", [])
        if c.customs_shipper_unless_carrier and any(n.get("caused_by") == "carrier" for n in notes):
            evidence += [n["src"] for n in notes if n.get("src")]
            return ZERO
        return acc["fee"] * (l.qty or Decimal(1))
    if l.kind == "peak":
        if acc is None or pickup is None or l.qty is None:
            return None
        if acc["months"] and pickup.month not in acc["months"]:
            if acc.get("src"):
                evidence.append(acc["src"])
            return ZERO
        return line_amount(acc["fee"], l.qty)
    if l.kind in ("account_fee", "programme_fee"):
        acc = c.accessorials.get(l.code or "") or acc
        if acc is None:
            return None
        return line_amount(acc["fee"], l.qty or Decimal(1))
    return None


def _boundary(feats, qty, lane, pickup, c):
    """Near a weight-band edge of this lane (within 1 kg) or a rate-period / fuel-month edge (within 1 day): a
    misread quantity or date would change the answer, so confidence is lowered."""
    for r in c.rate_rows:
        if r.lane == lane and r.band != "minimum" and any(e is not None and abs(qty - e) <= 1 for e in (r.lo, r.hi)):
            feats["boundary"] = True
    for name, st, en, _ in c.periods:
        if abs((pickup - st).days) <= 1 or abs((pickup - en).days) <= 1:
            feats["boundary"] = True
    month_end = (pickup.replace(day=28) + timedelta(days=4)).replace(day=1) - timedelta(days=1)
    if pickup.day == 1 or pickup == month_end:
        feats["boundary"] = True


def _fx_missing(o: Outcome, c, inv, line_srcs) -> Outcome:
    from ..terms import holder_for
    note = c.fx_note
    name = note[0] if note else "exchange-rate annex update"
    o.verdict, o.remedy = "cannot_determine", "request_document"
    month = month_of(inv.issue_date) if inv.issue_date else "the invoice month"
    o.missing_doc = {"name": f"{name} (exchange rate for {month}, needed to convert invoice {inv.printed_id or inv.invoice_id})"
                     if config.ASSUME_DESCRIPTIVE_MISSING_DOC_NAMES else name,
                     "holder": holder_for(c, "treasury")}
    o.evidence = ([note[2]] if note and note[2] else []) + line_srcs
    return o


def _missing_name(m: dict, inv, l) -> str:
    if not config.ASSUME_DESCRIPTIVE_MISSING_DOC_NAMES:
        return m["name"]
    lanes = ", ".join(m.get("lanes") or [])
    frm = m["from"].isoformat() if m.get("from") else ""
    return (f"{m['name']} (cited in {m.get('cited_in') or 'the amendment'} for lane {lanes} from {frm}; "
            f"needed for invoice {inv.printed_id or inv.invoice_id}, AWB {l.awb or '-'})")
