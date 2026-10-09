"""Rules engine on a synthetic world (invented contract, people and numbers; no model calls).

Each test builds documents the way the extractor stores them (doc rows with pages + extract_json) and runs the
deterministic rules. This pins the GLOSSARY arithmetic and windows independently of extraction.
"""
from __future__ import annotations

import json
import sys
from datetime import date
from decimal import Decimal as D
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "harness"))

from nova import policy  # noqa: E402
from nova.evaluate import evaluate_all  # noqa: E402
from nova.feedback import FeedbackItem  # noqa: E402
from nova.terms import resolve_rate  # noqa: E402
from nova.world import World  # noqa: E402

CID = "ZZQ-T-01"
LANE = "QQA1-QQB2"
LANE2 = "QQA1-QQC3"


def R(page, line):
    return {"page": page, "line": line}


def doc(doc_id, received, typ, data, pages, sender=("", ""), **kw):
    return {"doc_id": doc_id, "received_at": received, "status": "extracted", "doc_type": typ,
            "pages_json": json.dumps(pages), "extract_json": json.dumps({"type": typ, "data": data, "conf": 1.0}),
            "sender_name": sender[0], "sender_addr": sender[1], "is_scan": 0, "seq": 0, **kw}


PAGES = ["\n".join(f"line {i} with enough text to quote here" for i in range(1, 80))] * 11


def msa(notice_vs_amendment="unranked", grace=5, compounding=True):
    terms = {
        "contract_id": CID, "shipper": {"name": "Shipper", "code": "SHP"}, "carrier": {"name": "Carrier", "code": "CAR"},
        "dated": "2041-01-01", "effective_date": "2041-01-01", "end_date": "2041-12-31",
        "term_span": {"page": 3, "line_from": 5, "line_to": 5}, "auto_renews": False, "renewal_notice_days": None,
        "renewal_span": None, "signed": True, "currency": "USD", "payment_terms_days": 30,
        "late_fee": {"rate_pct": "2.00", "grace_days": grace, "compounding": compounding,
                     "paid_fees_leave_base": True, "span": {"page": 4, "line_from": 1, "line_to": 2}},
        "extension_span": {"page": 4, "line_from": 3, "line_to": 3}, "storage": {"free_days": 3, "span": None},
        "chargeable_weight": {"divisor": 6000, "round_up_to": "0.5", "span": None}, "minimum_charge_applies": True,
        "pricing_date_span": {"page": 3, "line_from": 9, "line_to": 9}, "rate_notice_span": None,
        "fuel_on_base_freight_only": True, "fuel_span": None, "dry_ice_span": None, "dg_span": None,
        "mixed_dg_span": None, "delivery_fee_only_if_carrier_delivers": True, "delivery_span": None,
        "customs_fee_shipper_unless_carrier_error": True, "customs_span": None, "waiver_authority_span": None,
        "waiver_scope_span": None,
        "precedence": {"amendment_over_agreement": True, "later_amendment_wins": True,
                       "notice_vs_amendment": notice_vs_amendment, "quoted_text_is_not_notice": True,
                       "span": None, "unranked_span": {"page": 5, "line_from": 1, "line_to": 1}},
        "last_period_continues": True, "continuation_span": None,
        "qualifying_spend": {"includes_base_fuel_security": True, "includes_listed_accessorials": True,
                             "excludes": ["tax", "duty", "late fees"], "net_of_credit_notes": True,
                             "foreign_currency_converted_per_invoice": True, "span": None},
        "credits": [{"credit_type": "rebate", "basis": "quarter", "tiers": [
            {"threshold_usd": "1000.00", "rate_pct": "5"}, {"threshold_usd": "5000.00", "rate_pct": "10"}],
            "rate_applies_to_all_spend": True, "flat_rate_pct": None, "due_days_after_period_end": 45,
            "step_down": None, "applicable": True, "span": {"page": 4, "line_from": 7, "line_to": 7}}],
    }
    rates = {"currency": "USD", "periods": [{"name": "P1", "start": "2041-01-01", "end": "2041-06-30", "ref": R(8, 2)},
                                            {"name": "P2", "start": "2041-07-01", "end": "2041-12-31", "ref": R(8, 3)}],
             "rows": [{"lane": LANE, "band": "minimum", "low_kg": None, "high_kg": None,
                       "rates": [{"period": "P1", "rate": "50.00"}, {"period": "P2", "rate": "50.00"}], "ref": R(8, 5)},
                      {"lane": LANE, "band": "range", "low_kg": "0", "high_kg": "99.5",
                       "rates": [{"period": "P1", "rate": "5.00"}, {"period": "P2", "rate": "5.50"}], "ref": R(8, 6)},
                      {"lane": LANE, "band": "range", "low_kg": "100", "high_kg": "299.5",
                       "rates": [{"period": "P1", "rate": "4.00"}, {"period": "P2", "rate": "4.40"}], "ref": R(8, 7)},
                      {"lane": LANE2, "band": "range", "low_kg": "0", "high_kg": None,
                       "rates": [{"period": "P1", "rate": "3.00"}, {"period": "P2", "rate": "3.00"}], "ref": R(8, 9)}]}
    annexes = {"fuel": [{"month": f"2041-{m:02d}", "pct": "20.00", "ref": R(9, m)} for m in range(1, 13)],
               "accessorials": [{"code": "DLV", "label": "Delivery fee", "fee": "40.00", "basis": "per_shipment",
                                 "only_in_months": [], "ref": R(10, 2)},
                                {"code": "SEC", "label": "Security surcharge", "fee": "0.10", "basis": "per_kg",
                                 "only_in_months": [], "ref": R(10, 3)}],
               "aliases": [{"code": "FRT", "labels": ["Air freight", "Freight charge"], "ref": R(10, 10)},
                           {"code": "FUEL", "labels": ["Fuel surcharge", "FSC"], "ref": R(10, 11)},
                           {"code": "SEC", "labels": ["Security surcharge", "Screening fee"], "ref": R(10, 12)},
                           {"code": "DLV", "labels": ["Delivery fee", "Door delivery"], "ref": R(10, 13)},
                           {"code": "LATE", "labels": ["Late payment fee", "Late fee"], "ref": R(10, 14)}],
               "fx": [], "fx_note": None, "tax_note": None}
    sched = {"persons": [
        {"name": "Kai Rates", "title": "Pricing Manager", "party_code": "CAR-X", "side": "carrier",
         "categories": ["rates"], "address": "kai.rates@car.test", "ref": R(11, 3)},
        {"name": "Lu Waive", "title": "Finance Lead", "party_code": "CAR-X", "side": "carrier",
         "categories": ["waivers", "payment_terms"], "address": "lu.waive@car.test", "ref": R(11, 4)},
        {"name": "Mo Disputes", "title": "Billing Disputes Lead", "party_code": "CAR-X", "side": "carrier",
         "categories": ["billing_disputes"], "address": "mo@car.test", "ref": R(11, 5)},
        {"name": "Ny Kam", "title": "Key Account Manager", "party_code": "CAR-X", "side": "carrier",
         "categories": ["notices"], "address": "ny@car.test", "ref": R(11, 2)}], "span": None}
    d = doc("b1/0001.eml#MSA.pdf", "2041-01-02T10:00:00Z", "msa",
            {"terms": terms, "rates": rates, "annexes": annexes, "schedule1": sched}, PAGES)
    return d


def invoice(doc_id, received, number, issue, lines, total=None, due=None):
    ls = []
    for i, (awb, label, qty, rate, amount, pickup, extra) in enumerate(lines, 1):
        ls.append({"awb": awb, "charge_label": label, "lane": LANE if awb else None, "pickup_date": pickup,
                   "pickup_raw": pickup, "qty": qty, "qty_unit": "kg", "rate": rate,
                   "rate_is_percent": label.startswith("Fuel"), "amount": amount, "ref_period": None,
                   "late_fee": extra, "ref": R(1, i + 5)})
    data = {"document_kind": "invoice", "printed_id": number, "id_ref": R(1, 2), "contract_ref": CID,
            "issue_date": issue, "issue_date_raw": issue, "due_date": due, "due_date_raw": due, "date_ref": R(1, 3),
            "date_order": "iso", "currency": "USD", "lines": ls, "subtotal": total, "tax_amount": "0.00",
            "tax_label": None, "total": total, "total_ref": R(1, 30), "credit": None, "directives_to_automation": []}
    return doc(doc_id, received, "invoice", data, [PAGES[0]])


def tracking(rows, received="2041-09-30T17:00:00Z"):
    table = {"table_kind": "tracking_export", "sheet": 1, "header_line": 1, "columns": {}, "status_values": [],
             "event_values": [], "directives_to_automation": [],
             "rows": [{"awb": a, "event": e, "date": d, "station": "X", "reason": None, "ref": R(1, i + 2)}
                      for i, (a, e, d) in enumerate(rows)]}
    return doc("b1/0090.eml#tracking.xlsx", received, "tracking_export", table, [PAGES[0]])


def email(doc_id, received, sender, data):
    base = {"kind": "other", "contract_ids": [], "invoice_refs": [], "waivers": [], "due_date_extensions": [],
            "status_events": [], "customs": [], "contract_effective": [], "directives_to_automation": []}
    base.update(data)
    return doc(doc_id, received, "email", base, [PAGES[0]], sender=sender)


def ledger(rows, received="2041-09-30T18:00:00Z"):
    table = {"table_kind": "ap_register", "sheet": 1, "header_line": 1, "columns": {}, "status_values": [],
             "event_values": [], "directives_to_automation": [],
             "rows": [{"invoice_id": i, "invoice_date": idate, "due_date": due, "amount": amt, "currency": "USD",
                       "status": st, "paid_date": paid, "ref": R(1, n + 2)}
                      for n, (i, idate, due, amt, st, paid) in enumerate(rows)]}
    return doc("b1/0091.eml#ap.xlsx", received, "ap_register", table, [PAGES[0]])


def amendment(rows=(), referenced=(), effective="2041-03-01", received="2041-02-20T00:00:00Z"):
    data = {"contract_id": CID, "reference": f"{CID}/AMD-1", "title": "Amendment No. 1", "effective_from": effective,
            "signed": True, "span": None,
            "rate_changes": [{"applies_to_periods": "every period", "rows": [
                {"lane": l, "band": b, "low_kg": lo, "high_kg": hi, "rate": r, "currency": "USD", "ref": R(1, 9)}
                for (l, b, lo, hi, r) in rows]}],
            "referenced_documents": [{"name_as_cited": n, "lanes": ls, "effective_from": f,
                                      "attached_or_incorporated": True, "ref": R(1, 12)} for (n, ls, f) in referenced],
            "fuel": [], "fx": [], "term_changes": []}
    return doc("b1/0005.eml#AMD-1.pdf", received, "amendment", data, [PAGES[0]])


def notice(sender, start="2041-06-01", end="2041-12-31", rate="4.30", received="2041-05-25T00:00:00Z"):
    rn = {"contract_id": CID, "reference": "RN-1", "effective_from": start, "effective_to": end,
          "rows": [{"lane": LANE, "band": "range", "low_kg": "100", "high_kg": "299.5", "rate": rate,
                    "currency": "USD", "ref": R(1, 9)}], "in_senders_own_text": True, "directives_to_automation": []}
    d = email("b1/0006.eml", received, sender, {"kind": "rate_notice"})
    ex = json.loads(d["extract_json"])
    ex["rate_notice"] = {"data": rn}
    d["extract_json"] = json.dumps(ex)
    return d


def world(docs, as_of="2041-09-30", feedback=None):
    return World(docs, date.fromisoformat(as_of), feedback or [])


def keyed(outcomes):
    return {o.key: o for o in outcomes}


# ---- tests -------------------------------------------------------------------------------------------------------------
def test_overcharge_band_period_and_fuel():
    # 150 kg on P2 (pickup 2041-07-10): rate 4.40; billed 4.80 -> freight diff 60.00, fuel 20% diff 12.00
    inv = invoice("b1/0010.eml#INV-1.pdf", "2041-07-20T00:00:00Z", "INV 0001", "2041-07-20",
                  [("QA00000001", "Air freight", "150", "4.80", "720.00", "2041-07-10", None),
                   ("QA00000001", "Fuel surcharge", "720.00", "20.00", "144.00", "2041-07-10", None),
                   ("QA00000001", "Delivery fee", "1", "40.00", "40.00", "2041-07-10", None)])
    w = world([msa(), inv, tracking([("QA00000001", "PICKED_UP", "2041-07-10")])])
    o = keyed(evaluate_all(w))[("overcharge", "INV0001")]
    assert o.verdict == "finding" and o.amount_usd == D("72.00")
    assert ("QA00000001", "tracking") in o.shipments


def test_band_edge_decoy_is_clean():
    inv = invoice("b1/0010.eml#INV-2.pdf", "2041-07-20T00:00:00Z", "INV-0002", "2041-07-20",
                  [("QA00000002", "Freight charge", "99", "5.50", "544.50", "2041-07-10", None)])
    w = world([msa(), inv, tracking([("QA00000002", "PICKED_UP", "2041-07-10")])])
    assert ("overcharge", "INV-0002") not in keyed(evaluate_all(w))


def test_conflict_amendment_vs_authorised_notice_unranked():
    amd = amendment(rows=[(LANE, "range", "100", "299.5", "4.00")])
    rn = notice(("Kai Rates", "kai.rates@car.test"), rate="4.30")
    inv = invoice("b1/0011.eml#INV-3.pdf", "2041-07-20T00:00:00Z", "INV-0003", "2041-07-20",
                  [("QA00000003", "Air freight", "100", "4.30", "430.00", "2041-07-10", None),
                   ("QA00000003", "Fuel surcharge", "430.00", "20.00", "86.00", "2041-07-10", None)])
    w = world([msa(), amd, rn, inv, tracking([("QA00000003", "PICKED_UP", "2041-07-10")])])
    o = keyed(evaluate_all(w))[("overcharge", "INV-0003")]
    assert o.verdict == "conflict" and o.amount_range == (D("0.00"), D("36.00"))


def test_unauthorised_notice_is_ignored_plain_overcharge():
    amd = amendment(rows=[(LANE, "range", "100", "299.5", "4.00")])
    rn = notice(("Ny Kam", "ny@car.test"), rate="4.30")                 # KAM has no rates authority
    inv = invoice("b1/0011.eml#INV-4.pdf", "2041-07-20T00:00:00Z", "INV-0004", "2041-07-20",
                  [("QA00000004", "Air freight", "100", "4.30", "430.00", "2041-07-10", None)])
    w = world([msa(), amd, rn, inv, tracking([("QA00000004", "PICKED_UP", "2041-07-10")])])
    o = keyed(evaluate_all(w))[("overcharge", "INV-0004")]
    assert o.verdict == "finding" and o.amount_usd == D("30.00")


def test_missing_incorporated_annex_is_cannot_determine():
    amd = amendment(referenced=[("Annex Q rev 9", [LANE], "2041-06-01")])
    inv = invoice("b1/0012.eml#INV-5.pdf", "2041-07-20T00:00:00Z", "INV-0005", "2041-07-20",
                  [("QA00000005", "Air freight", "150", "4.80", "720.00", "2041-07-10", None)])
    w = world([msa(), amd, inv, tracking([("QA00000005", "PICKED_UP", "2041-07-10")])])
    o = keyed(evaluate_all(w))[("overcharge", "INV-0005")]
    assert o.verdict == "cannot_determine"
    assert "Annex Q rev 9" in o.missing_doc["name"] and o.missing_doc["holder"]["person"] == "Kai Rates"


def test_waiver_from_waivers_contact_counts_rates_contact_does_not():
    inv = invoice("b1/0013.eml#INV-6.pdf", "2041-07-20T00:00:00Z", "INV-0006", "2041-07-20",
                  [("QA00000006", "Door delivery", "1", "40.00", "40.00", "2041-07-10", None),
                   ("QA00000007", "Delivery fee", "1", "40.00", "40.00", "2041-07-11", None)])
    w1 = email("b1/0014.eml", "2041-07-12T00:00:00Z", ("Lu Waive", "lu.waive@car.test"),
               {"kind": "waiver", "waivers": [{"charge_label": "Delivery fee", "awbs": ["QA00000006"], "months": [],
                                               "invoice_ids": [], "conditional": False, "condition_text": None,
                                               "condition_met": "unknown", "in_senders_own_text": True,
                                               "original_sender_name": None, "original_sender_addr": None,
                                               "original_date": None, "original_cited_as": None, "ref": R(1, 8)}]})
    w2 = email("b1/0015.eml", "2041-07-12T00:00:00Z", ("Kai Rates", "kai.rates@car.test"),
               {"kind": "waiver", "waivers": [{"charge_label": "Delivery fee", "awbs": ["QA00000007"], "months": [],
                                               "invoice_ids": [], "conditional": False, "condition_text": None,
                                               "condition_met": "unknown", "in_senders_own_text": True,
                                               "original_sender_name": None, "original_sender_addr": None,
                                               "original_date": None, "original_cited_as": None, "ref": R(1, 8)}]})
    out = keyed(evaluate_all(world([msa(), inv, w1, w2])))
    o = out[("waived_but_billed", "INV-0006")]
    assert o.verdict == "finding" and o.amount_usd == D("40.00")


def test_resend_of_paid_invoice_is_duplicate_unpaid_is_not():
    a = invoice("b1/0020.eml#INV-7.pdf", "2041-07-01T00:00:00Z", "INV-0007", "2041-07-01",
                [("QA00000008", "Delivery fee", "1", "40.00", "40.00", "2041-06-20", None)], total="40.00")
    b = invoice("b1/0021.eml#INV-7.pdf", "2041-07-25T00:00:00Z", "INV-0007", "2041-07-01",
                [("QA00000008", "Delivery fee", "1", "40.00", "40.00", "2041-06-20", None)], total="40.00")
    e = email("b1/0021.eml", "2041-07-25T00:00:00Z", ("Billing", "billing@car.test"),
              {"kind": "invoice_resend", "invoice_refs": [{"invoice_id": "INV-0007", "asks_for_payment": True,
                                                           "marking": "none", "ref": R(1, 7)}]})
    paid = ledger([("INV-0007", "2041-07-01", "2041-07-31", "40.00", "paid", "2041-07-10")])
    o = keyed(evaluate_all(world([msa(), a, b, e, paid])))[("duplicate", "INV-0007")]
    assert o.amount_usd == D("40.00")
    unpaid = ledger([("INV-0007", "2041-07-01", "2041-07-31", "40.00", "open", None)])
    assert ("duplicate", "INV-0007") not in keyed(evaluate_all(world([msa(), a, b, e, unpaid])))


def test_late_fee_not_owed_after_extension_and_owed_after_grace():
    fee = {"invoice_id": "INV-0008", "principal": "1000.00", "month_index": 1, "rate_pct": "2.00"}
    inv = invoice("b1/0030.eml#INV-9.pdf", "2041-08-20T00:00:00Z", "INV-0009", "2041-08-20",
                  [(None, "Late fee on INV-0008", None, "2.00", "20.00", None, fee)])
    ext = email("b1/0031.eml", "2041-07-25T00:00:00Z", ("Lu Waive", "lu.waive@car.test"),
                {"kind": "due_date_extension", "due_date_extensions": [
                    {"invoice_id": "INV-0008", "new_due_date": "2041-08-15", "in_senders_own_text": True,
                     "ref": R(1, 7)}]})
    reg = ledger([("INV-0008", "2041-07-01", "2041-07-31", "1000.00", "paid", "2041-08-10")])
    o = keyed(evaluate_all(world([msa(), inv, ext, reg])))[("late_fee_not_owed", "INV-0009")]
    assert o.amount_usd == D("20.00")
    # without the extension: 10 days late > 5 grace -> one month owed = 20.00, billed 20.00 -> clean
    assert ("late_fee_not_owed", "INV-0009") not in keyed(evaluate_all(world([msa(), inv, reg])))


def test_late_fee_risk_window():
    reg = ledger([("INV-0010", "2041-09-01", "2041-10-14", "500.00", "open", None),
                  ("INV-0011", "2041-09-01", "2041-10-15", "500.00", "open", None),
                  ("INV-0012", "2041-09-01", "2041-09-30", "500.00", "open", None)])
    i10 = invoice("b1/0040.eml#INV-10.pdf", "2041-09-02T00:00:00Z", "INV-0010", "2041-09-01", [])
    out = keyed(evaluate_all(world([msa(), reg, i10], as_of="2041-09-30")))
    assert out[("late_fee_risk", "INV-0010")].amount_usd == D("10.00")
    assert ("late_fee_risk", "INV-0011") not in out and ("late_fee_risk", "INV-0012") not in out


def test_expiry_window_edges():
    assert ("expiry", CID) in keyed(evaluate_all(world([msa()], as_of="2041-11-01")))     # 60 days
    assert ("expiry", CID) not in keyed(evaluate_all(world([msa()], as_of="2041-10-31")))  # 61 days
    assert ("expiry", CID) not in keyed(evaluate_all(world([msa()], as_of="2042-01-01")))  # lapsed


def test_rate_accepted_feedback_scope_lane_only():
    rn = notice(("Ny Kam", "ny@car.test"), rate="4.30")                 # unauthorised sender
    fb = FeedbackItem("fb-x", "close", "rate_accepted", ("overcharge", "INV-OLD"), {"contract_id": CID, "lane": LANE},
                      {"source": "rate notice", "sent_by": "Ny Kam"}, "standing", {"contract_id": CID, "lane": LANE},
                      date(2041, 6, 1), date(2041, 12, 31), date(2041, 8, 1), "batch_01")
    w = world([msa(), rn], feedback=[fb])
    res = resolve_rate(w, w.contracts[CID], LANE, D("150"), date(2041, 7, 10))
    assert res.status == "value" and res.options[0].rate == D("4.30") and res.feedback_used == [fb]
    res2 = resolve_rate(w, w.contracts[CID], LANE2, D("150"), date(2041, 7, 10))
    assert res2.options[0].rate == D("3.00") and not res2.feedback_used


def test_supervised_never_executes_and_threshold_is_summed():
    inv = invoice("b1/0050.eml#INV-13.pdf", "2041-07-20T00:00:00Z", "INV-0013", "2041-07-20",
                  [("QA00000013", "Air freight", "250", "24.40", "6100.00", "2041-07-10", None)])
    w = world([msa(), inv, tracking([("QA00000013", "PICKED_UP", "2041-07-10")])])
    outs = evaluate_all(w)
    policy.assign_actions(outs, "supervised")
    o = keyed(outs)[("overcharge", "INV-0013")]
    assert o.amount_usd == D("5000.00") and o.action == "human_review"
    policy.assign_actions(outs, "autonomous")
    assert o.action == "human_review"


def test_autonomous_executes_clean_small_dispute_and_holds_weak_pickup():
    inv = invoice("b1/0051.eml#INV-14.pdf", "2041-07-20T00:00:00Z", "INV-0014", "2041-07-20",
                  [("QA00000014", "Air freight", "150", "4.80", "720.00", "2041-07-10", None)])
    strong = evaluate_all(world([msa(), inv, tracking([("QA00000014", "PICKED_UP", "2041-07-10")])]))
    policy.assign_actions(strong, "autonomous")
    assert keyed(strong)[("overcharge", "INV-0014")].action == "execute:dispute"
    weak = evaluate_all(world([msa(), inv]))                             # pickup from the invoice only
    policy.assign_actions(weak, "autonomous")
    assert keyed(weak)[("overcharge", "INV-0014")].action == "human_review"
