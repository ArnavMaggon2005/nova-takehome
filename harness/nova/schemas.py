"""JSON schemas for every extraction (structured outputs). Layout-free: they describe meaning, never a format.

Conventions: every property is required (nullable where it may be absent); numbers are strings copied exactly as
printed (Python converts them to Decimal and checks they occur in the cited line); dates are ISO YYYY-MM-DD with the
raw text alongside; every row carries a reference to the page and line(s) it was read from, which become the evidence
quotes. No example value in this file comes from the practice or exam mailboxes.
"""
from __future__ import annotations


def S(t: str) -> dict:
    return {"type": t}


def N(t: str) -> dict:
    return {"type": [t, "null"]}


def O(**props) -> dict:
    return {"type": "object", "properties": props, "required": list(props), "additionalProperties": False}


def NO(**props) -> dict:
    return {"anyOf": [O(**props), {"type": "null"}]}


def A(item: dict) -> dict:
    return {"type": "array", "items": item}


def E(*vals: str, null: bool = False) -> dict:
    return {"type": ["string", "null"] if null else "string", "enum": list(vals) + ([None] if null else [])}


REF = O(page=S("integer"), line=S("integer"))
SPAN = O(page=S("integer"), line_from=S("integer"), line_to=S("integer"))
NSPAN = NO(page=S("integer"), line_from=S("integer"), line_to=S("integer"))
DIRECTIVES = A(O(text=S("string"), addressed_to=S("string"), ref=REF))

ATTACHMENT_TYPES = ("msa", "amendment", "annex_update", "contract_extension", "rate_notice", "invoice", "statement",
                    "credit_note", "ap_register", "tracking_export", "awb", "dg_declaration", "customs_document",
                    "other")

CLASSIFY = O(
    doc_type=E(*ATTACHMENT_TYPES),
    contract_ids=A(S("string")),
    printed_document_number=N("string"),
    is_signed_instrument=S("boolean"),
    summary=S("string"),
)

# ---- emails ---------------------------------------------------------------------------------------------------------
EMAIL_KINDS = ("invoice_cover", "invoice_resend", "rate_notice", "waiver", "waiver_request", "due_date_extension",
               "status_update", "customs_notice", "contract_cover", "dispute_or_query", "forward", "report_cover",
               "other")
EVENTS = ("PICKED_UP", "DEPARTED", "ARRIVED_FACILITY", "OUT_FOR_DELIVERY", "DELIVERED", "COLLECTED_BY_CONSIGNEE",
          "CUSTOMS_HOLD", "CUSTOMS_RELEASED", "OTHER")

EMAIL = O(
    kind=E(*EMAIL_KINDS),
    contract_ids=A(S("string")),
    invoice_refs=A(O(invoice_id=S("string"), asks_for_payment=S("boolean"),
                     marking=E("none", "copy", "reminder", "for_your_records", "duplicate", "other"),
                     ref=REF)),
    waivers=A(O(charge_label=S("string"), awbs=A(S("string")), months=A(S("string")), invoice_ids=A(S("string")),
                conditional=S("boolean"), condition_text=N("string"), condition_met=E("yes", "no", "unknown"),
                in_senders_own_text=S("boolean"),
                original_sender_name=N("string"), original_sender_addr=N("string"), original_date=N("string"),
                original_cited_as=N("string"), ref=REF)),
    due_date_extensions=A(O(invoice_id=S("string"), new_due_date=S("string"), in_senders_own_text=S("boolean"),
                            ref=REF)),
    status_events=A(O(awb=S("string"), event=E(*EVENTS), date=S("string"), station=N("string"), ref=REF)),
    customs=A(O(awb=S("string"), hold_date=N("string"), release_date=N("string"), reason_code=N("string"),
                caused_by=E("shipper", "carrier", "unknown"), ref=REF)),
    contract_effective=A(O(contract_id=S("string"), effective_date=S("string"), ref=REF)),
    directives_to_automation=DIRECTIVES,
)

# ---- invoices, statements, credit notes -----------------------------------------------------------------------------
LINE = O(
    awb=N("string"), charge_label=S("string"), lane=N("string"),
    pickup_date=N("string"), pickup_raw=N("string"),
    qty=N("string"), qty_unit=E("kg", "shipment", "day", "month", "fee", "base", "other", null=True),
    rate=N("string"), rate_is_percent=S("boolean"), amount=S("string"),
    ref_period=N("string"),
    late_fee=NO(invoice_id=S("string"), principal=N("string"), month_index=N("integer"), rate_pct=N("string")),
    ref=REF,
)
INVOICE = O(
    document_kind=E("invoice", "statement", "credit_note", "other"),
    printed_id=S("string"), id_ref=REF,
    contract_ref=N("string"),
    issue_date=N("string"), issue_date_raw=N("string"), due_date=N("string"), due_date_raw=N("string"),
    date_ref=NO(page=S("integer"), line=S("integer")),
    date_order=E("day_first", "month_first", "iso", "text_month", "unknown"),
    currency=S("string"),
    lines=A(LINE),
    subtotal=N("string"), tax_amount=N("string"), tax_label=N("string"), total=N("string"),
    total_ref=NO(page=S("integer"), line=S("integer")),
    credit=NO(credit_type=E("rebate", "improvement", "margin", "billing", "other"), period=N("string"),
              stated_basis=N("string"), invoice_ids=A(S("string")), amount=S("string"), ref=REF),
    directives_to_automation=DIRECTIVES,
)

# ---- tabular exports (AP register, tracking): the model maps columns, Python reads every row ------------------------
TABLE = O(
    table_kind=E("ap_register", "tracking_export", "other"),
    sheet=S("integer"),
    header_line=S("integer"),
    columns=O(invoice_id=N("integer"), invoice_date=N("integer"), due_date=N("integer"), amount=N("integer"),
              currency=N("integer"), status=N("integer"), paid_date=N("integer"), awb=N("integer"),
              event=N("integer"), event_date=N("integer"), station=N("integer"), reason=N("integer")),
    status_values=A(O(printed=S("string"), meaning=E("paid", "open", "scheduled", "disputed", "credited", "other"))),
    event_values=A(O(printed=S("string"), meaning=E(*EVENTS))),
    directives_to_automation=DIRECTIVES,
)

# ---- shipping documents ------------------------------------------------------------------------------------------------
SHIPPING = O(
    kind=E("awb", "master_awb", "dg_declaration", "customs_document", "other"),
    awb=N("string"), executed_on=N("string"), origin=N("string"), destination=N("string"),
    pieces=N("string"), actual_weight=N("string"), chargeable_weight=N("string"),
    houses=A(O(awb=S("string"), pieces=N("string"), weight=N("string"), ref=REF)),
    dg_items=A(O(un_number=N("string"), description=S("string"), quantity=N("string"),
                 refrigerant_only=S("boolean"), is_dry_ice=S("boolean"), ref=REF)),
    customs=NO(hold_date=N("string"), release_date=N("string"), reason_code=N("string"),
               caused_by=E("shipper", "carrier", "unknown"), ref=REF),
    ref=REF,
    directives_to_automation=DIRECTIVES,
)

# ---- contracts (strong model, sectional calls over one cached copy of the text) ----------------------------------------
PARTY = O(name=S("string"), code=N("string"))
CREDIT = O(
    credit_type=E("rebate", "margin_step_down", "promised_credit"),
    basis=E("quarter", "contract_year"),
    tiers=A(O(threshold_usd=S("string"), rate_pct=S("string"))),
    rate_applies_to_all_spend=S("boolean"),
    flat_rate_pct=N("string"),
    due_days_after_period_end=N("integer"),
    step_down=NO(volume_threshold=N("string"), from_pct=N("string"), to_pct=N("string")),
    applicable=S("boolean"),
    span=SPAN,
)
CONTRACT_TERMS = O(
    contract_id=S("string"), shipper=PARTY, carrier=PARTY, dated=N("string"),
    effective_date=N("string"), end_date=N("string"), term_span=NSPAN,
    auto_renews=S("boolean"), renewal_notice_days=N("integer"), renewal_span=NSPAN,
    signed=S("boolean"), currency=S("string"),
    payment_terms_days=N("integer"),
    late_fee=O(rate_pct=N("string"), grace_days=N("integer"), compounding=S("boolean"),
               paid_fees_leave_base=S("boolean"), span=NSPAN),
    extension_span=NSPAN,
    storage=O(free_days=N("integer"), span=NSPAN),
    chargeable_weight=O(divisor=N("integer"), round_up_to=N("string"), span=NSPAN),
    minimum_charge_applies=S("boolean"),
    pricing_date_span=NSPAN,
    rate_notice_span=NSPAN,
    fuel_on_base_freight_only=S("boolean"), fuel_span=NSPAN,
    dry_ice_span=NSPAN, dg_span=NSPAN, mixed_dg_span=NSPAN,
    delivery_fee_only_if_carrier_delivers=S("boolean"), delivery_span=NSPAN,
    customs_fee_shipper_unless_carrier_error=S("boolean"), customs_span=NSPAN,
    waiver_authority_span=NSPAN, waiver_scope_span=NSPAN,
    precedence=O(amendment_over_agreement=S("boolean"), later_amendment_wins=S("boolean"),
                 notice_vs_amendment=E("unranked", "notice_wins", "amendment_wins", "not_stated"),
                 quoted_text_is_not_notice=S("boolean"), span=NSPAN, unranked_span=NSPAN),
    last_period_continues=S("boolean"), continuation_span=NSPAN,
    qualifying_spend=O(includes_base_fuel_security=S("boolean"), includes_listed_accessorials=S("boolean"),
                       excludes=A(S("string")), net_of_credit_notes=S("boolean"),
                       foreign_currency_converted_per_invoice=S("boolean"), span=NSPAN),
    credits=A(CREDIT),
)
RATES = O(
    currency=S("string"),
    periods=A(O(name=S("string"), start=S("string"), end=S("string"), ref=REF)),
    rows=A(O(lane=S("string"), band=E("minimum", "range", "open_ended"), low_kg=N("string"), high_kg=N("string"),
             rates=A(O(period=S("string"), rate=S("string"))), ref=REF)),
)
ANNEXES = O(
    fuel=A(O(month=S("string"), pct=S("string"), ref=REF)),
    accessorials=A(O(code=S("string"), label=S("string"), fee=S("string"),
                     basis=E("per_shipment", "per_kg", "per_day", "per_month", "other"),
                     only_in_months=A(S("integer")), ref=REF)),
    aliases=A(O(code=S("string"), labels=A(S("string")), ref=REF)),
    fx=A(O(month=S("string"), inr_per_usd=S("string"), ref=REF)),
    fx_note=NO(later_rows_document=S("string"), issued_by=N("string"), ref=REF),
    tax_note=NO(rate_pct=N("string"), applies_when=S("string"), ref=REF),
)
SCHEDULE1 = O(
    persons=A(O(name=S("string"), title=N("string"), party_code=S("string"), side=E("carrier", "shipper"),
                categories=A(S("string")), address=S("string"), ref=REF)),
    span=NSPAN,
)

RATE_ROW = O(lane=S("string"), band=E("minimum", "range", "open_ended"), low_kg=N("string"), high_kg=N("string"),
             rate=S("string"), currency=N("string"), ref=REF)
AMENDMENT = O(
    contract_id=S("string"), reference=N("string"), title=S("string"),
    effective_from=N("string"), signed=S("boolean"), span=NSPAN,
    rate_changes=A(O(applies_to_periods=S("string"), rows=A(RATE_ROW))),
    referenced_documents=A(O(name_as_cited=S("string"), lanes=A(S("string")), effective_from=N("string"),
                             attached_or_incorporated=S("boolean"), ref=REF)),
    fuel=A(O(month=S("string"), pct=S("string"), ref=REF)),
    fx=A(O(month=S("string"), inr_per_usd=S("string"), ref=REF)),
    term_changes=A(O(kind=E("new_end_date", "auto_renewal", "payment_terms", "other"), new_end_date=N("string"),
                     text=S("string"), ref=REF)),
)
RATE_NOTICE = O(
    contract_id=N("string"), reference=N("string"), effective_from=N("string"), effective_to=N("string"),
    rows=A(RATE_ROW),
    in_senders_own_text=S("boolean"),
    directives_to_automation=DIRECTIVES,
)
