"""One report: rules -> feedback -> actions -> confidence -> evidence -> ids (docs/PLAN.md sequence 2b)."""
from __future__ import annotations

import json
import sys
from decimal import Decimal
from pathlib import Path

import config

from . import policy
from .feedback import feedback_view
from .ingest import extract_pending
from .llm import Budget
from .money import ZERO, money_str, parse_date
from .outcome import Outcome
from .rules import cashback, duplicate, expiry, late_fees, overcharge, waiver
from .state import State
from .textlayer import quote_for
from .world import World

PORTFOLIO = {"cashback": "cashback", "expiry": "expiry", "late_fee_risk": "late_fee_risk"}
TERM_DOC_TYPES = {"msa", "amendment", "annex_update", "contract_extension", "rate_notice"}


def evaluate_all(world: World) -> list[Outcome]:
    dup, dup_lines = duplicate.evaluate(world)
    wb, wb_lines = waiver.evaluate(world, dup_lines)
    oc = overcharge.evaluate(world, dup_lines | wb_lines)
    lf = late_fees.evaluate_not_owed(world)
    disputed: dict = {}
    for o in dup + wb + oc + lf:
        if o.verdict == "finding" and o.amount_usd is not None:
            native = o.features.get("native_amount", o.amount_usd)
            disputed[o.invoice_id] = disputed.get(o.invoice_id, ZERO) + native
    risk = late_fees.evaluate_risk(world, disputed)
    cb = cashback.evaluate(world)
    ex = expiry.evaluate(world)
    merged: dict = {}
    for o in dup + wb + oc + lf + risk + cb + ex:
        if o is None or o.verdict == "no_finding":
            continue
        merged.setdefault(o.key, o)
    if world.pending:
        for o in merged.values():
            o.features["pending_inputs"] = True
    return list(merged.values())


def build_report(as_of: str, mode: str, state_dir: str) -> dict:
    budget = Budget(config.STEP_BUDGET_S)
    state = State(state_dir)
    if state.pending_docs():
        s = extract_pending(state, budget, config.REPORT_EXTRACT_FRACTION)
        print(f"report: finished pending extraction first: {s}", file=sys.stderr)
    day = parse_date(as_of)
    docs = state.docs()
    fbs = feedback_view(state, day)
    world = World(docs, day, fbs)
    if world.pending:
        print(f"report: WARNING {len(world.pending)} document(s) still unread: {world.pending[:5]}", file=sys.stderr)
    with_fb = evaluate_all(world)
    without = {o.key: o for o in evaluate_all(World(docs, day, []))} if fbs else {}
    outcomes = _directives(with_fb, fbs, world)
    policy.assign_actions(outcomes, mode)
    if fbs:
        base_actions = list(without.values())
        policy.assign_actions(base_actions, mode)
        _learned(outcomes, without)
    items = [_item(o, world, mode) for o in outcomes]
    items = [it for it in items if it is not None]
    _ids(items, state, mode, as_of, world)
    report = {"schema_version": "1.0", "as_of": as_of, "mode": mode, "findings": [],
              "portfolio": {"cashback": [], "expiry": [], "late_fee_risk": []}}
    for it in sorted(items, key=lambda x: (x["class"], x["id"])):
        bucket = PORTFOLIO.get(it["class"])
        (report["portfolio"][bucket] if bucket else report["findings"]).append(it)
    _outbox(state, mode, outcomes, items)
    esc = sum(1 for it in items if it["action"] in ("escalate", "human_review"))
    if items and esc / len(items) > config.ESCALATION_WARN_SHARE:
        print(f"report: WARNING {esc}/{len(items)} items escalated ({mode})", file=sys.stderr)
    state.save_snapshot(mode, as_of, report)              # keeps _key/_sig for supersedes and retro next time
    state.log("steps.jsonl", {"step": "report", "as_of": as_of, "mode": mode, "items": len(items),
                              "secs": round(budget.elapsed(), 1)})
    printed = json.loads(json.dumps(report))
    for bucket in [printed["findings"]] + list(printed["portfolio"].values()):
        for it in bucket:
            it.pop("_key", None)
            it.pop("_sig", None)
    return printed


# ---- feedback directives and learned_at ------------------------------------------------------------------------------
def _directives(outcomes: list[Outcome], fbs: list, world: World) -> list[Outcome]:
    by_key = {o.key: o for o in outcomes}
    for fb in fbs:
        if fb.key not in by_key and fb.decision not in ("override_amount",):
            continue
        if fb.decision in ("close", "reject"):
            by_key.pop(fb.key, None)
        elif fb.decision == "override_amount" and fb.amount is not None and fb.key in by_key:
            o = by_key[fb.key]
            o.verdict, o.amount_usd, o.amount_range = "finding", fb.amount, None
            o.feedback_used.append(fb)
            o.features["feedback_fixed"] = True
    return list(by_key.values())


def _learned(outcomes: list[Outcome], without: dict) -> None:
    for o in outcomes:
        base = without.get(o.key)
        changed = base is None or base.signature != o.signature or getattr(base, "action", None) != o.action
        if changed and o.feedback_used:
            fb = o.feedback_used[0]
            o.learned_at = fb.learned
            o.features["feedback_fixed"] = True


# ---- items, evidence, ids --------------------------------------------------------------------------------------------
def _quote(world: World, src) -> dict | None:
    pages = world.pages.get(src.doc_id)
    if not pages:
        return None
    q = quote_for(pages, src.page, src.line_from, src.line_to)
    lt = src.line_to
    while len("".join(q.split())) < config.MIN_QUOTE_CHARS and lt < src.line_from + 3:
        lt += 1
        q = quote_for(pages, src.page, src.line_from, lt)
    if len("".join(q.split())) < config.MIN_QUOTE_CHARS:
        if world.docs.get(src.doc_id, {}).get("is_scan"):
            q = q or "scanned page"
        else:
            return None
    return {"doc": src.doc_id, "page": src.page, "quote": q}


def _evidence(o: Outcome, world: World) -> list[dict]:
    out, seen = [], set()
    for s in o.evidence:
        if s is None or (s.doc_id, s.page, s.line_from) in seen:
            continue
        seen.add((s.doc_id, s.page, s.line_from))
        e = _quote(world, s)
        if e:
            out.append(e)
        if len(out) >= 8:
            break
    return out


def _item(o: Outcome, world: World, mode: str) -> dict | None:
    ev = _evidence(o, world)
    if not ev:
        o.features["evidence_unverified"] = True
        return None
    it = {"id": "", "class": o.cls, "verdict": o.verdict,
          "amount_usd": money_str(o.amount_usd) if (o.verdict == "finding" and o.amount_usd is not None) else None,
          "amount_range": [money_str(x) for x in o.amount_range] if o.amount_range else None,
          "deadline": o.deadline.isoformat() if o.deadline else None,
          "action": o.action, "confidence": policy.confidence(o), "evidence": ev,
          "missing_doc": o.missing_doc if o.verdict == "cannot_determine" else None,
          "supersedes": [], "learned_at": getattr(o, "learned_at", None)}
    if o.cls == "cashback":
        it.update(contract_id=o.contract_id, period=o.period, credit_type=o.credit_type)
    elif o.cls == "expiry":
        it["contract_id"] = o.contract_id
    else:
        it["invoice_id"] = o.invoice_id
    if o.verdict == "finding" and o.cls != "expiry" and it["amount_usd"] is None:
        return None
    it["_key"] = "|".join(str(x) for x in o.key)
    it["_sig"] = list(o.signature)
    it["_srcs"] = sorted({s.doc_id for s in o.evidence if s})
    return it


def _ids(items: list[dict], state: State, mode: str, as_of: str, world: World) -> None:
    prev = state.previous_snapshot(mode, as_of) or {}
    prev_items = {}
    for k in ("findings",):
        for x in prev.get(k) or []:
            prev_items[x.get("_key")] = x
    for k in ("cashback", "expiry", "late_fee_risk"):
        for x in (prev.get("portfolio") or {}).get(k) or []:
            prev_items[x.get("_key")] = x
    prev_as_of = parse_date(prev.get("as_of")) if prev else None
    used = set()
    for it in items:
        base = f"{it['class']}:{it['_key'].split('|', 1)[1]}"
        p = prev_items.get(it["_key"])
        if p is None:
            it["id"] = base
            if prev_as_of and _is_retro(it, world, prev_as_of):
                it["retro"] = True
        elif p.get("_sig") == it["_sig"]:
            it["id"] = p["id"]
        else:
            n = int(p["id"].rsplit("@v", 1)[1]) + 1 if "@v" in p["id"] else 2
            it["id"] = f"{base}@v{n}"
            it["supersedes"] = [p["id"]]
        while it["id"] in used:
            it["id"] += "+"
        used.add(it["id"])


def _is_retro(it: dict, world: World, prev_as_of) -> bool:
    """New key whose invoice was already held at the previous report, made a key by a term document received since."""
    if "invoice_id" not in it:
        return False
    inv_docs = [i for i in world.invoices if i.invoice_id == it["invoice_id"]]
    if not inv_docs or min(i.received for i in inv_docs)[:10] > prev_as_of.isoformat():
        return False
    for doc_id in it["_srcs"]:
        d = world.docs.get(doc_id) or {}
        typ = d.get("doc_type")
        if (d.get("received_at") or "")[:10] > prev_as_of.isoformat() and (typ in TERM_DOC_TYPES or (
                typ == "email" and "rate_notice" in (d.get("extract_json") or ""))):
            return True
    return False


def _outbox(state: State, mode: str, outcomes: list[Outcome], items: list[dict]) -> None:
    """Drafts and (autonomous) executed records go to the outbox, addressed to the Schedule 1 contact only.
    Nothing is sent anywhere: 'execute' records what an unattended system would send. Never part of report items."""
    d = Path(state.dir) / "outbox" / mode
    d.mkdir(parents=True, exist_ok=True)
    by_key = {"|".join(str(x) for x in o.key): o for o in outcomes}
    for it in items:
        o = by_key.get(it["_key"])
        if o is None or not (it["action"].startswith(("draft:", "execute:")) or it["action"] == "human_review"):
            continue
        p = policy.recipient(o)
        rec = {"item_id": it["id"], "action": it["action"], "remedy": o.remedy,
               "to": {"name": p.name, "address": p.address, "party": p.party} if p else None,
               "amount_usd": it.get("amount_usd"), "evidence": it["evidence"],
               "status": "executed (recorded only)" if it["action"].startswith("execute:") else "awaiting approval",
               "why_held": o.features.get("reasons")}
        (d / f"{it['id'].replace('/', '_').replace(':', '_')}.json").write_text(json.dumps(rec, indent=1))
    for it in items:
        for k in ("_srcs",):
            it.pop(k, None)


__all__ = ["build_report", "evaluate_all", "Decimal"]
