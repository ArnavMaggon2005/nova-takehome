"""Cashback and credits (GLOSSARY: Cashback and credits).

For every credit the contract promises (rebate per quarter, promised credit per contract year), for every period
that has closed by as_of: qualifying spend = base freight, fuel, security and the contract's listed accessorials on
invoices dated in the period, net of credit notes dated in the period (rebate/improvement credits excepted), foreign
currency converted per invoice at that month's exchange rate when the contract says so; earned = tier rate x QS;
owed = earned - every credit note for that contract, period and credit type. Due -> claim, not yet due -> track.
"""
from __future__ import annotations

from datetime import date, timedelta
from decimal import Decimal

import config

from ..money import ZERO, add_years, month_of, pct, quarter_bounds, quarter_of, round2, to_usd
from ..outcome import Outcome
from ..world import World, norm_id

QS_KINDS = {"freight", "fuel", "security"}
ACCESSORIAL_KINDS = {"dg", "dry_ice", "storage", "delivery", "customs", "peak", "account_fee", "programme_fee",
                     "handling"}
CREDIT_TYPE_WORDS = {"rebate": ("rebate",), "promised_credit": ("improvement", "promised", "annual"),
                     "margin_step_down": ("margin",)}


def evaluate(world: World) -> list[Outcome]:
    out = []
    for c in world.contracts.values():
        for term in c.credits:
            if not term.applicable:
                continue
            if term.credit_type == "rebate" and term.basis == "quarter":
                for period, start, end in _quarters(c, world):
                    o = _period(world, c, term, period, start, end)
                    if o:
                        out.append(o)
            elif term.credit_type == "promised_credit" and c.effective:
                n = 1
                while True:
                    start = add_years(c.effective, n - 1)
                    end = add_years(c.effective, n) - timedelta(days=1)
                    if end >= world.as_of:
                        break
                    o = _period(world, c, term, f"CY{n}", start, end)
                    if o:
                        out.append(o)
                    n += 1
    return out


def _quarters(c, world: World):
    start = c.effective or min((i.issue_date for i in world.invoices if i.issue_date), default=None)
    if start is None:
        return []
    q = quarter_of(start)
    out = []
    while True:
        s, e = quarter_bounds(q)
        if e >= world.as_of:
            break
        out.append((q, s, e))
        y, n = int(q[:4]), int(q[-1])
        q = f"{y + (n == 4)}-Q{1 if n == 4 else n + 1}"
    return out


def qualifying_spend(world: World, c, start: date, end: date) -> tuple[Decimal | None, int, list]:
    """-> (QS in USD, invoices counted, evidence). None when a needed exchange rate is missing."""
    total = ZERO
    counted = 0
    seen = set()
    srcs = []
    for inv in sorted(world.invoices, key=lambda i: i.received):
        if world.contract_for(inv) is not c or inv.issue_date is None or not start <= inv.issue_date <= end:
            continue
        if config.ASSUME_RESENT_INVOICE_COUNTS_ONCE_IN_QS and inv.invoice_id in seen:
            continue
        seen.add(inv.invoice_id)
        amt = sum((l.amount for l in inv.lines if _qualifies(c, l)), ZERO)
        usd = _usd(world, c, inv, amt)
        if usd is None:
            return None, counted, srcs
        total += usd
        counted += 1
        if inv.total_src:
            srcs.append(inv.total_src)
    if c.qs_net_of_credits:
        for cn in world.credit_notes:
            ctype = str((cn.credit or {}).get("credit_type") or "")
            if ctype in ("rebate", "improvement", "margin"):
                continue
            if world.contract_for(cn) is not c or cn.issue_date is None or not start <= cn.issue_date <= end:
                continue
            usd = _usd(world, c, cn, cn.total or ZERO)
            if usd is not None:
                total -= usd
    return total, counted, srcs


def _qualifies(c, l) -> bool:
    if l.kind in QS_KINDS:
        return True
    if c.qs_includes_accessorials and l.kind in ACCESSORIAL_KINDS:
        return (l.code in c.accessorials) or not config.ASSUME_QS_UNKNOWN_CODES_EXCLUDED or \
            any(a["kind"] == l.kind for a in c.accessorials.values())
    return False


def _usd(world: World, c, inv, amount: Decimal) -> Decimal | None:
    if inv.currency == "USD":
        return amount
    fx = world.fx_rate(c, month_of(inv.issue_date)) if inv.issue_date else None
    if fx is None:
        return None
    return round2(amount / fx[0]) if c.qs_per_invoice_fx else amount / fx[0]


def _period(world: World, c, term, period: str, start: date, end: date) -> Outcome | None:
    qs, n, srcs = qualifying_spend(world, c, start, end)
    if qs is None or qs <= 0:
        return None
    rate = None
    for threshold, r in term.tiers:
        if qs >= threshold:
            rate = r
    if rate is None:
        rate = term.flat_pct
    if rate is None:
        return None
    earned = pct(rate, qs)
    credited = ZERO
    for cn in world.credit_notes:
        cr = cn.credit or {}
        if world.contract_for(cn) is not c:
            continue
        ctype = str(cr.get("credit_type") or "")
        if not any(w in ctype for w in CREDIT_TYPE_WORDS.get(term.credit_type, ())):
            continue
        if str(cr.get("period") or "").replace(" ", "").upper() != period.upper():
            continue
        credited += _usd(world, c, cn, cn.total or ZERO) or ZERO
    owed = earned - credited
    if owed <= 0:
        return None
    due = end + timedelta(days=int(term.due_days or 0)) if term.due_days is not None else end
    remedy = "claim_credit" if world.as_of >= due else "track_credit"
    o = Outcome("cashback", "finding", contract_id=c.id, period=period, credit_type=term.credit_type,
                amount_usd=round2(owed), contract=c, remedy=remedy, term_levels=[1], fact_levels=[3])
    o.evidence = [s for s in (term.src, c.spans.get("qs")) if s] + srcs[:3]
    o.features["aggregate_n"] = n
    o.features["boundary"] = any(abs(qs - t) <= Decimal("50") for t, _ in term.tiers)
    o.notes.append(f"QS {qs} over {n} invoices; rate {rate}%; earned {earned}; credited {credited}")
    return o


__all__ = ["evaluate", "qualifying_spend", "norm_id"]
