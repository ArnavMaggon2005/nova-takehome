"""What a rule module concludes about one finding key, before actions, confidence and ids are attached."""
from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date
from decimal import Decimal


@dataclass
class Outcome:
    cls: str                                   # overcharge | duplicate | waived_but_billed | late_fee_not_owed |
    #                                            late_fee_risk | cashback | expiry
    verdict: str                               # finding | no_finding | conflict | cannot_determine
    invoice_id: str | None = None
    contract_id: str | None = None
    period: str | None = None
    credit_type: str | None = None
    amount_usd: Decimal | None = None
    amount_range: tuple | None = None
    deadline: date | None = None
    missing_doc: dict | None = None
    evidence: list = field(default_factory=list)          # Src, most important first
    remedy: str = "dispute"                    # dispute | claim_credit | track_credit | request_document | alert |
    #                                            payment_reminder | escalate | none
    contract: object = None                    # Contract, for recipients and conflict index
    shipments: list = field(default_factory=list)          # (awb, pickup source)
    pickup_decides: bool = False               # the pickup date chose a rate, period or fuel month
    conflict_keys: list = field(default_factory=list)      # (contract, lane, kind, period) this key's rates depend on
    term_levels: list = field(default_factory=list)
    fact_levels: list = field(default_factory=list)
    feedback_used: list = field(default_factory=list)      # FeedbackItem objects that shaped this outcome
    features: dict = field(default_factory=dict)
    sources_received: list = field(default_factory=list)   # received_at of every deciding source
    notes: list = field(default_factory=list)
    inr: bool = False

    @property
    def key(self) -> tuple:
        if self.cls == "cashback":
            return ("cashback", self.contract_id, self.period, self.credit_type)
        if self.cls == "expiry":
            return ("expiry", self.contract_id)
        return (self.cls, self.invoice_id)

    @property
    def signature(self) -> tuple:
        amt = f"{self.amount_usd:.2f}" if self.amount_usd is not None else None
        rng = tuple(f"{x:.2f}" for x in self.amount_range) if self.amount_range else None
        return (self.verdict, amt, rng, self.deadline.isoformat() if self.deadline else None)
