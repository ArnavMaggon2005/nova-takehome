"""Which rate applies to a shipment (GLOSSARY: Which document wins; Conflict, cannot_determine).

Candidates in force on the pickup date: the agreement's rates annex (level 1), signed amendments and the revised annexes
they incorporate (level 1, a later effective date wins for the lanes it changes), rate notices from the contract's
Schedule 1 *rates* contact (level 2; anyone else's notice has no authority), and notices a person accepted in
feedback (level 2, inside the feedback scope). Notice vs amendment follows the precedence clause the agreement states;
when it leaves them unranked and they differ, the result is a conflict. An amendment that incorporates a document we
don't hold, for this lane and date, makes the rate unknowable: missing.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date
from decimal import Decimal

import config

from .world import Contract, Notice, RateRow, Src, World, norm_id, norm_lane, period_of


@dataclass
class RateOption:
    source: str                    # agreement | amendment | annex | notice | accepted_notice
    rate: Decimal
    minimum: Decimal | None
    level: int
    srcs: list
    label: str
    doc_id: str
    feedback: object = None


@dataclass
class Resolution:
    status: str                    # value | conflict | missing | none
    options: list = field(default_factory=list)
    missing: dict | None = None
    clause_srcs: list = field(default_factory=list)
    feedback_used: list = field(default_factory=list)
    period: str | None = None
    unauthorised_notices: list = field(default_factory=list)


def _pick(rows: list[RateRow], lane: str, qty: Decimal, period: str) -> tuple[Decimal | None, Decimal | None, list]:
    rate = minimum = None
    srcs = []
    for r in rows:
        if r.lane != lane:
            continue
        val = r.rates.get(period, r.rates.get("*"))
        if val is None and len(r.rates) == 1:
            val = next(iter(r.rates.values()))
        if val is None:
            continue
        if r.band == "minimum":
            minimum = val
        elif rate is None and r.contains(qty):
            rate = val
            if r.src:
                srcs.insert(0, r.src)
    return rate, minimum, srcs


def _held_annex(world: World, name: str, contract: Contract, lane: str):
    """A held document (revised annex / amendment) that is the one cited by `name` and has rows for the lane."""
    key = " ".join(name.lower().split())
    for a in world.amendments:
        if a.contract_id not in (contract.id, "") :
            continue
        title = " ".join(f"{a.title} {a.reference or ''}".lower().split())
        if key and key in title and any(r.lane == lane for r in a.rows):
            return a
    return None


def resolve_rate(world: World, c: Contract, lane: str, qty: Decimal, when: date) -> Resolution:
    lane = norm_lane(lane)
    res = Resolution("none", period=period_of(c, when))
    for k in ("pricing_date",):
        if k in c.spans:
            res.clause_srcs.append(c.spans[k])
    # agreement annex
    msa = None
    if res.period:
        rate, minimum, srcs = _pick(c.rate_rows, lane, qty, res.period)
        if rate is not None:
            msa = RateOption("agreement", rate, minimum, 1, srcs, f"{c.id} rates annex", c.doc_id)
    # signed amendments in force (later effective date wins); their incorporated documents
    amd = None
    amd_start = None
    for a in sorted(world.amendments, key=lambda a: (a.effective or date.min, a.received)):
        if a.contract_id != c.id or not a.signed or a.effective is None or a.effective > when:
            continue
        rate, minimum, srcs = _pick(a.rows, lane, qty, res.period or "*")
        if rate is not None and (amd_start is None or a.effective >= amd_start):
            amd = RateOption("amendment", rate, minimum, 1, srcs, a.reference or a.title, a.doc_id)
            amd_start = a.effective
        for ref in a.referenced:
            if lane in ref["lanes"] and (ref["from"] or a.effective) <= when:
                start = ref["from"] or a.effective
                if amd_start is not None and start < amd_start:
                    continue
                held = _held_annex(world, ref["name"], c, lane)
                if held is not None:
                    rate, minimum, srcs = _pick(held.rows, lane, qty, res.period or "*")
                    if rate is not None:
                        amd = RateOption("annex", rate, minimum, 1, srcs, ref["name"], held.doc_id)
                        amd_start = start
                        continue
                amd = {"missing": True, "name": ref["name"], "src": ref["src"], "lanes": ref["lanes"],
                       "from": start, "amendment": a}
                amd_start = start
    # notices: authorised (Schedule 1 rates, own text) and feedback-accepted ones
    ntc = None
    for n in sorted(world.notices, key=lambda n: n.received):
        if not _notice_covers(n, c, lane, when):
            continue
        rate, minimum, srcs = _pick(n.rows, lane, qty, "*")
        if rate is None:
            continue
        ok, person, fb = world.authorised(c, n.sender_addr, n.sender_name, "rates",
                                          world.received_date(n.doc_id) or when)
        accepted = _accepted(world, c, lane, when, n)
        if accepted is not None:
            ntc = RateOption("accepted_notice", rate, minimum, 2, srcs, f"rate notice from {n.sender_name}",
                             n.doc_id, accepted)
            res.feedback_used.append(accepted)
        elif ok and n.own_text:
            ntc = RateOption("notice", rate, minimum, 2, srcs, f"rate notice from {n.sender_name}", n.doc_id, fb)
            if fb is not None:
                res.feedback_used.append(fb)
        else:
            res.unauthorised_notices.append(n)
    if ntc is not None and "rate_notice" in c.spans:
        res.clause_srcs.append(c.spans["rate_notice"])
    # combine
    if amd is not None and ntc is not None:
        choice = _feedback_precedence(world, c, lane, when)
        if choice is not None:
            fb, use = choice
            res.feedback_used.append(fb)
            if use == "notice":
                return _value(res, ntc)
            if isinstance(amd, dict):
                return _missing(res, amd, c)
            return _value(res, amd)
        policy = c.notice_vs_amendment
        if policy == "not_stated":
            policy = config.ASSUME_DEFAULT_NOTICE_VS_AMENDMENT
        if isinstance(amd, dict):
            return _missing(res, amd, c) if policy != "notice_wins" else _value(res, ntc)
        if policy == "unranked":
            if "unranked" in c.spans:
                res.clause_srcs.append(c.spans["unranked"])
            res.status, res.options = "conflict", [amd, ntc]
            return res
        return _value(res, ntc if policy == "notice_wins" else amd)
    if amd is not None:
        return _missing(res, amd, c) if isinstance(amd, dict) else _value(res, amd)
    if ntc is not None:
        return _value(res, ntc)
    if msa is not None:
        return _value(res, msa)
    return res


def _value(res: Resolution, opt: RateOption) -> Resolution:
    res.status, res.options = "value", [opt]
    return res


def _missing(res: Resolution, amd: dict, c: Contract) -> Resolution:
    res.status = "missing"
    holder = holder_for(c, "rates")
    res.missing = {"name": amd["name"], "src": amd["src"], "lanes": amd["lanes"], "from": amd["from"],
                   "holder": holder, "cited_in": amd["amendment"].reference or amd["amendment"].title}
    return res


def _notice_covers(n: Notice, c: Contract, lane: str, when: date) -> bool:
    if n.contract_id and n.contract_id != c.id:
        return False
    if not n.contract_id and not any(p.address == n.sender_addr for p in c.persons):
        return False
    if n.start and when < n.start:
        return False
    if n.end and when > n.end:
        return False
    return any(r.lane == lane for r in n.rows)


def _accepted(world: World, c: Contract, lane: str, when: date, n: Notice):
    """A rate_accepted feedback fact naming this notice, in scope for (contract, lane, pickup date)."""
    for fb in world.feedback:
        if fb.fact_type != "rate_accepted" or fb.scope_kind != "standing":
            continue
        subj, val = fb.subject or {}, fb.value or {}
        if norm_id(subj.get("contract_id")) != c.id or norm_lane(subj.get("lane")) != lane:
            continue
        if not fb.matches(contract_id=c.id, lane=lane) or not fb.in_dates(when):
            continue
        if val.get("sent_by") and " ".join(str(val["sent_by"]).split()).lower() != \
                " ".join(n.sender_name.split()).lower():
            continue
        return fb
    return None


def _feedback_precedence(world: World, c: Contract, lane: str, when: date):
    for fb in world.feedback:
        if fb.fact_type != "precedence":
            continue
        subj, val = fb.subject or {}, fb.value or {}
        if norm_id(subj.get("contract_id")) != c.id or (subj.get("lane") and norm_lane(subj.get("lane")) != lane):
            continue
        if fb.valid_from and when < fb.valid_from:
            continue
        if not fb.matches(contract_id=c.id, lane=lane):
            continue
        use = str(val.get("use") or "").lower()
        later_signed = [a for a in world.amendments if a.contract_id == c.id and a.signed and fb.decided_on and
                        (world.received_date(a.doc_id) or date.min) > fb.decided_on and
                        any(r.lane == lane for r in a.rows)]
        if later_signed:
            return fb, "amendment"
        return fb, ("notice" if "notice" in use else "amendment")
    return None


def holder_for(c: Contract, category: str, side: str | None = None) -> dict:
    """Who holds a missing document: the issuing party's Schedule 1 contact for that category (else its KAM)."""
    side = side or config.ASSUME_MISSING_DOC_ISSUER_SIDE
    ps = c.persons_for(category, side) or ([c.kam(side)] if c.kam(side) else [])
    if not ps:
        return {"party": c.carrier_party or (c.carrier or {}).get("name") or ""}
    p = ps[0]
    return {"party": p.party, "person": p.name, "role": p.title}
