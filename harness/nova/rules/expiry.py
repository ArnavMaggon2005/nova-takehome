"""Expiry (GLOSSARY: Expiry): report a contract when its operative date is 0..60 days after as_of.

Operative date = the end date (moved by the latest signed extension), or for a contract that renews itself the
non-renewal notice deadline (end date minus the notice period). Action internal:alert; no money.
"""
from __future__ import annotations

from datetime import timedelta

import config

from ..outcome import Outcome
from ..world import World


def evaluate(world: World) -> list[Outcome]:
    out = []
    for c in world.contracts.values():
        end, ev = c.end, [c.spans.get("term")]
        for a in sorted(world.amendments, key=lambda a: a.received):
            if a.contract_id == c.id and a.signed and a.new_end:
                end, ev = a.new_end[0], [a.new_end[1], c.spans.get("term")]
        if end is None:
            continue
        op = end
        if c.auto_renews and c.renewal_notice_days:
            op = end - timedelta(days=int(c.renewal_notice_days))
            ev.append(c.spans.get("renewal"))
        gap = (op - world.as_of).days
        if not 0 <= gap <= config.EXPIRY_WINDOW_DAYS:
            continue
        o = Outcome("expiry", "finding", contract_id=c.id, deadline=op, contract=c, remedy="alert",
                    term_levels=[1], fact_levels=[1])
        o.evidence = [s for s in ev if s]
        o.features["boundary"] = gap in (0, config.EXPIRY_WINDOW_DAYS)
        out.append(o)
    return out
