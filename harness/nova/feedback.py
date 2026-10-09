"""`harness.py feedback <file>`: store a person's decisions; nothing is decided here (docs/PLAN.md section 7).

Items are kept verbatim with the file's after_batch and decided_at. At report time feedback_view() splits them into
scoped facts (sender_authority, rate_accepted, precedence: inputs to the resolvers, inside their applies_to filters
and dates) and key directives (close, reject, override_amount, one_off_approval: exactly one finding key each).
"""
from __future__ import annotations

import json
import shutil
import sys
from dataclasses import dataclass, field
from datetime import date
from pathlib import Path

import config

from .money import dec, parse_date
from .state import State


def run_feedback(feedback_file: str, state_dir: str) -> None:
    state = State(state_dir)
    src = Path(feedback_file)
    try:
        raw = json.loads(src.read_text())
    except (OSError, json.JSONDecodeError) as e:
        print(f"feedback: can't read {src}: {e}", file=sys.stderr)
        return
    shutil.copyfile(src, state.dir / "feedback" / src.name)
    items = [x for x in raw.get("items") or [] if isinstance(x, dict)]
    state.add_feedback(src.name, str(raw.get("after_batch") or ""), str(raw.get("decided_at") or ""), items)
    state.log("steps.jsonl", {"step": "feedback", "file": src.name, "items": len(items)})
    print(f"feedback {src.name}: stored {len(items)} item(s)", file=sys.stderr)
    from .ingest import _spend_line
    _spend_line()


def key_tuple(k: dict) -> tuple:
    """Same shape as grader/score.py key_tuple (class, id...); invoice ids normalised the grader's way."""
    import re
    cls = k.get("class") or ("cashback" if "period" in k else "expiry")
    if cls == "cashback":
        return ("cashback", str(k.get("contract_id")), str(k.get("period")), str(k.get("credit_type")))
    if cls == "expiry":
        return ("expiry", str(k.get("contract_id")))
    return (cls, re.sub(r"[\s#:]", "", str(k.get("invoice_id") or "")).upper())


@dataclass
class FeedbackItem:
    item_id: str
    decision: str
    fact_type: str
    key: tuple
    subject: dict
    value: dict
    scope_kind: str
    applies_to: dict
    valid_from: date | None
    valid_to: date | None
    decided_on: date | None
    after_batch: str
    raw: dict = field(repr=False, default_factory=dict)

    def in_dates(self, d: date | None) -> bool:
        if d is None:
            return False
        if self.valid_from and d < self.valid_from:
            return False
        return not (self.valid_to and d > self.valid_to)

    def matches(self, **attrs) -> bool:
        """Every applies_to filter must equal the candidate's attribute; a filter the candidate lacks is no match."""
        for k, v in (self.applies_to or {}).items():
            if k not in attrs or attrs[k] is None:
                return False
            if _norm(attrs[k]) != _norm(v):
                return False
        return True

    @property
    def learned(self) -> dict:
        return {"feedback_item_id": self.item_id,
                "batch": self.after_batch if config.ASSUME_LEARNED_AT_BATCH_FIELD == "after_batch" else ""}

    @property
    def amount(self):
        return dec((self.value or {}).get("amount_usd"))


def _norm(v) -> str:
    return " ".join(str(v).split()).upper()


def feedback_view(state: State, as_of: date) -> list[FeedbackItem]:
    out = []
    for row in state.feedback_items():
        it = row["item"]
        decided = parse_date(row.get("decided_at") or "")
        if config.ASSUME_FEEDBACK_FROM_DECIDED_DATE and decided and decided > as_of:
            continue
        fact = it.get("fact") or {}
        scope = it.get("scope") or {}
        try:
            key = key_tuple(it.get("finding_key") or {})
        except Exception:                                  # noqa: BLE001
            key = ("?",)
        out.append(FeedbackItem(
            item_id=str(it.get("item_id") or ""), decision=str(it.get("decision") or ""),
            fact_type=str(fact.get("type") or ""), key=key, subject=fact.get("subject") or {},
            value=fact.get("value") or {}, scope_kind=str(scope.get("kind") or "one_off"),
            applies_to=scope.get("applies_to") or {}, valid_from=parse_date(scope.get("valid_from")),
            valid_to=parse_date(scope.get("valid_to")), decided_on=decided, after_batch=row.get("after_batch") or "",
            raw=it))
    return out
