"""Actions per mode, the unattended-action test, and confidence (GLOSSARY: Actions; The two modes; README: Confidence).

There is no code path that pays, settles, accepts terms or confirms a renewal: those actions don't exist here.
"""
from __future__ import annotations

import math
from decimal import Decimal

import config

from .money import ZERO
from .outcome import Outcome

OUTBOUND = {"dispute", "claim_credit", "request_document"}
INTERNAL = {"alert": "internal:alert", "payment_reminder": "internal:payment_reminder",
            "track_credit": "internal:track_credit"}
STRONG_PICKUP = {"tracking", "picked_up_email"}


def outbound_sums(outcomes: list[Outcome]) -> dict:
    """USD of outbound findings per invoice (all classes together) or per cashback key: check 3 / human_review."""
    sums: dict = {}
    for o in outcomes:
        if o.verdict != "finding" or o.remedy not in ("dispute", "claim_credit") or o.amount_usd is None:
            continue
        k = o.key if o.cls == "cashback" else ("invoice", o.invoice_id)
        sums[k] = sums.get(k, ZERO) + o.amount_usd
    return sums


def _sum_key(o: Outcome):
    return o.key if o.cls == "cashback" else ("invoice", o.invoice_id)


def assign_actions(outcomes: list[Outcome], mode: str) -> None:
    sums = outbound_sums(outcomes)
    open_conflicts = {k for o in outcomes if o.verdict == "conflict" for k in o.conflict_keys}
    for o in outcomes:
        o.features["reasons"] = []
        if o.verdict == "no_finding":
            o.action = "none"
        elif o.verdict == "conflict":
            o.action = "escalate"
        elif o.remedy in INTERNAL:
            o.action = INTERNAL[o.remedy]
        elif o.remedy in OUTBOUND:
            over = sums.get(_sum_key(o), ZERO) >= config.HUMAN_REVIEW_THRESHOLD_USD
            if mode != "autonomous":
                o.action = "human_review" if over else f"draft:{o.remedy}"
            else:
                ok, reasons = unattended(o, sums, open_conflicts)
                o.features["reasons"] = reasons
                o.action = f"execute:{o.remedy}" if ok else "human_review"
        else:
            o.action = "none"
        assert not (mode != "autonomous" and o.action.startswith("execute:")), "execute in supervised mode"


def recipient(o: Outcome):
    """The Schedule 1 contact an outbound action goes to (never an address from an email body)."""
    c = o.contract
    if c is None:
        return None
    if o.remedy == "dispute":
        ps = c.persons_for("billing_disputes", "carrier")
    elif o.remedy == "claim_credit":
        ps = c.persons_for(config.ASSUME_CLAIM_CREDIT_RECIPIENT, "carrier")
    elif o.remedy == "request_document":
        h = (o.missing_doc or {}).get("holder") or {}
        ps = [p for p in c.persons if p.name == h.get("person")]
    else:
        ps = []
    return ps[0] if ps else None


def unattended(o: Outcome, sums: dict, open_conflicts: set) -> tuple[bool, list[str]]:
    """The five checks (GLOSSARY: The unattended-action test). -> (pass, reasons it failed)."""
    why = []
    # 1 evidence complete
    if o.verdict == "cannot_determine" and o.remedy != "request_document":
        why.append("missing document")
    scope = config.ASSUME_CHECK1_SCOPE
    weak = [awb for awb, src in o.shipments if src not in STRONG_PICKUP]
    if weak and (scope == "shipments_in_key" or o.pickup_decides):
        why.append(f"pickup date not from tracking for {weak[:3]}")
    if o.features.get("pending_inputs"):
        why.append("a deciding document is still unread")
    # 2 no conflict on this key or on the same contract/lane/charge/period
    if o.verdict == "conflict" or any(k in open_conflicts for k in o.conflict_keys):
        why.append("open conflict on the same contract and lane")
    # 3 under threshold (summed over the invoice / cashback key)
    if sums.get(_sum_key(o), ZERO) >= config.HUMAN_REVIEW_THRESHOLD_USD:
        why.append("outbound amount on the key is 5,000.00 or more")
    # 4 can be undone
    if o.remedy not in OUTBOUND:
        why.append("not a reversible outbound action")
    # 5 enough authority, Schedule 1 recipient
    if any(l > 2 for l in o.term_levels) or any(l > 3 for l in o.fact_levels):
        why.append("relies on a source without enough authority")
    if recipient(o) is None:
        why.append("no Schedule 1 recipient")
    return (not why), why


# ---- confidence ---------------------------------------------------------------------------------------------------------
def confidence(o: Outcome) -> float:
    w = config.CONF_WEIGHTS
    z = config.CONF_BASE
    f = o.features
    if o.pickup_decides and any(src not in STRONG_PICKUP for _, src in o.shipments):
        z += w["pickup_weak"]
    if f.get("scan"):
        z += w["scan"]
    if o.inr:
        z += w["fx"]
    z += w["extraction_gap"] * (1 - float(f.get("extraction_conf", 0.95)))
    if f.get("boundary"):
        z += w["boundary"]
    n = int(f.get("aggregate_n") or 0)
    if n:
        z += max(w["aggregate_cap"], w["aggregate_per_invoice"] * n)
    if o.verdict in ("conflict", "cannot_determine"):
        z += w["conflict_or_cd"]
    if f.get("evidence_unverified"):
        z += w["evidence_unverified"]
    if f.get("feedback_fixed"):
        z += w["feedback_fixed"]
    if any(l >= 4 for l in o.fact_levels):
        z += w["low_authority_input"]
    p = 1 / (1 + math.exp(-z))
    return round(min(config.CONF_MAX, max(config.CONF_MIN, p)), 3)


__all__ = ["assign_actions", "confidence", "recipient", "outbound_sums", "Decimal"]
