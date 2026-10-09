"""Every tunable setting and every interpretive assumption, in one place.

Each ASSUME_* constant has an entry in docs/ASSUMPTIONS.md: the question, the reading chosen, the evidence, and the
one-line change if the reading turns out wrong. Nothing in here names a company, person, contract, lane or invoice.

Models and the step budget can be overridden through environment variables. Note that grader/run_grader.py passes
only PATH, HOME, TMPDIR and ANTHROPIC_* to the harness, so under `make grade` the defaults below are what runs.
"""
from __future__ import annotations

import os
from decimal import Decimal
from pathlib import Path


def _dev_overrides() -> None:
    """Developer-only settings. grader/run_grader.py strips the environment (only PATH, HOME, TMPDIR, ANTHROPIC_*
    reach the harness), so during development NOVA_* values can also come from <repo>/.nova_dev.env (gitignored).
    The file never exists in a grading checkout; real environment variables always win; only NOVA_* keys are read."""
    f = Path(__file__).resolve().parent.parent / ".nova_dev.env"
    if not f.is_file():
        return
    for line in f.read_text().splitlines():
        line = line.strip()
        if line and not line.startswith("#") and "=" in line:
            k, v = (x.strip() for x in line.split("=", 1))
            if k.startswith("NOVA_"):
                os.environ.setdefault(k, v)


_dev_overrides()

# ---- dev-only switches (unset in grading) ------------------------------------------------------------------------------
CACHE_DIR = os.environ.get("NOVA_CACHE_DIR") or None          # shared extraction cache across runs, modes, states
SPEND_LEDGER = os.environ.get("NOVA_SPEND_LEDGER") or None    # cumulative cost ledger
SPEND_LIMIT_USD = float(os.environ.get("NOVA_SPEND_LIMIT") or 0) or None
PRICES = {   # USD per million tokens (input, output, cache read); cache writes are 1.25 x input
    "claude-opus-5-5": {"in": 4.0, "out": 20.0, "read": 0.20},
    "claude-sonnet-5-5": {"in": 2.0, "out": 10.0, "read": 0.20},
    "claude-haiku-4-5": {"in": 1.0, "out": 5.0, "read": 0.10},
    "default": {"in": 5.0, "out": 25.0, "read": 0.50},
}

# ---- models ----------------------------------------------------------------------------------------------------------
# Contracts, amendments, annexes, rate notices and Schedule 1 need the strongest reader; everything else is routine.
MODEL_CONTRACT = os.environ.get("NOVA_MODEL_CONTRACT", "claude-opus-5-5")
MODEL_DOC = os.environ.get("NOVA_MODEL_DOC", "claude-sonnet-5-5")
EFFORT_CLASSIFY = "low"
EFFORT_DOC = "low"
EFFORT_CONTRACT = "medium"
MAX_TOKENS_CLASSIFY = 4000
MAX_TOKENS_EXTRACT = 16000
# Extraction is copying, not reasoning: on models that allow it, thinking is switched off to save output tokens.
THINKING_OFF_MODELS = ("claude-sonnet-5-5",)

# ---- time and concurrency ----------------------------------------------------------------------------------------------
STEP_BUDGET_S = float(os.environ.get("NOVA_STEP_BUDGET_S", "300"))
INGEST_LAUNCH_FRACTION = 0.72      # ingest stops starting new LLM work after this share of the budget
REPORT_EXTRACT_FRACTION = 0.60     # report may spend this share of its budget finishing pending documents
LLM_THREADS = int(os.environ.get("NOVA_LLM_THREADS", "12"))
LLM_MAX_ATTEMPTS = 6               # per request, across 429 / overloaded / 5xx / connection errors
LLM_BACKOFF_BASE_S = 2.0
LLM_BACKOFF_MAX_S = 30.0
LLM_REQUEST_TIMEOUT_S = 180.0
OCR_RENDER_DPI = 150

# ---- grader-facing constants (GLOSSARY) ----------------------------------------------------------------------------
HUMAN_REVIEW_THRESHOLD_USD = Decimal("5000.00")   # G: Conflict, cannot_determine and human_review
EXPIRY_WINDOW_DAYS = 60                           # G: Expiry, 0 <= deadline - as_of <= 60
RISK_WINDOW_DAYS = 14                             # G: Late fees, 0 < due - as_of <= 14
MIN_QUOTE_CHARS = 12                              # G: Evidence, non-space characters
ESCALATION_WARN_SHARE = 0.40                      # log a warning well below the 60% hard gate

# ---- assumptions (each one is documented in docs/ASSUMPTIONS.md) -----------------------------------------------------
# A1. A paid invoice re-sent under the same number counts ONCE in qualifying spend (it is one invoice, one date).
ASSUME_RESENT_INVOICE_COUNTS_ONCE_IN_QS = True
# A2. Unattended check 1 ("pickup date came from tracking or a carrier picked-up email") applies to every shipment
#     whose lines are in the finding; keys with no shipment (late fees, cashback, monthly fees) pass it.
#     Alternative reading: "pickup_decides_amount" (only when the pickup date chose a rate, period or fuel month).
ASSUME_CHECK1_SCOPE = "shipments_in_key"
# A3. Recipient of an outbound credit claim: the carrier's Schedule 1 billing_disputes contact.
ASSUME_CLAIM_CREDIT_RECIPIENT = "billing_disputes"
# A4. missing_doc.name = the document as cited, then sender, date and the invoice/AWB it covers (grader matching is
#     "our name contains theirs"), e.g. "Annex A rev 2 (cited in ..., for lane ..., needed for invoice ...)".
ASSUME_DESCRIPTIVE_MISSING_DOC_NAMES = True
# A5. Quantities are taken as printed on the invoice; a different weight on the AWB is not disputed.
ASSUME_QUANTITY_AS_PRINTED = True
# A6. A resend is a duplicate only if the ledger shows the invoice paid (or scheduled) on or before the resend date.
ASSUME_RESEND_NEEDS_PAYMENT_BEFORE_RESEND = True
# A7. Cross-invoice duplicate lines must match on AWB (house suffix included), charge code and quantity.
ASSUME_DUPLICATE_LINE_NEEDS_SAME_QTY = True
# A8. Late fee not owed: the fee base is the printed/ledger principal; our own open disputes are NOT removed from it
#     (removing them would raise the disputed amount; when in doubt, don't dispute).
ASSUME_NOT_OWED_BASE_EXCLUDES_OUR_DISPUTES = False
# A9. Late-fee risk: the principal is the open amount less what we dispute on that invoice (GLOSSARY says so).
ASSUME_RISK_PRINCIPAL_EXCLUDES_OUR_DISPUTES = True
# A10. A late fee charged on an invoice that the ledger does not show as paid is not assessed (no paid date).
ASSUME_SKIP_LATE_FEE_WHEN_UNPAID = True
# A11. Tax/GST lines are not re-computed (the domestic/export split is not reliably derivable): never disputed.
ASSUME_CHECK_TAX_LINES = False
# A12. An overcharge sums only positive line differences; an undercharged line on the same invoice does not net off.
ASSUME_OVERCHARGE_POSITIVE_LINES_ONLY = True
# A13. A line whose expected value can't be computed (no tracking for storage, no DG declaration ...) is accepted.
ASSUME_UNVERIFIABLE_LINE_IS_CORRECT = True
# A14. A customs broker's notice (outside both companies) is a level-3 record for the facts it states.
ASSUME_BROKER_NOTICE_IS_RECORD = True
# A15. Each house AWB is its own shipment for band rating; a house split is not a duplicate.
ASSUME_HOUSE_AWB_IS_SHIPMENT = True
# A16. The issuing side of a document cited as missing (Annex A rev N, Annex F update, rate notice) is the carrier.
ASSUME_MISSING_DOC_ISSUER_SIDE = "carrier"
# A17. Qualifying spend includes base freight, fuel, security and every code listed in the contract's Annex D;
#      unknown codes are left out (a smaller spend never over-claims).
ASSUME_QS_UNKNOWN_CODES_EXCLUDED = True
# A18. A rate notice and a signed amendment that both cover the pickup are a conflict only when the contract says
#      they are unranked; with no precedence clause extracted, the GLOSSARY ladder (amendment wins) applies.
ASSUME_DEFAULT_NOTICE_VS_AMENDMENT = "amendment_wins"
# A19. Feedback applies to reports whose as_of is on or after the date of decided_at.
ASSUME_FEEDBACK_FROM_DECIDED_DATE = True
# A20. learned_at.batch is the feedback file's after_batch.
ASSUME_LEARNED_AT_BATCH_FIELD = "after_batch"

# ---- confidence (section 9 of docs/PLAN.md) ----------------------------------------------------------------------------
CONF_BASE = 3.2
CONF_WEIGHTS = {
    "pickup_weak": -1.2,
    "scan": -0.9,
    "scan_disagree": -0.4,
    "fx": -0.4,
    "extraction_gap": -2.0,       # times (1 - lowest field confidence)
    "boundary": -0.6,
    "aggregate_per_invoice": -0.12,
    "aggregate_cap": -1.4,
    "disagreement": -0.8,
    "conflict_or_cd": -0.7,
    "evidence_unverified": -1.0,
    "feedback_fixed": 0.8,
    "low_authority_input": -0.8,
}
CONF_MIN, CONF_MAX = 0.05, 0.98
