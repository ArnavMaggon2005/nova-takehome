"""Every feedback kind in GLOSSARY "feedback.json", on the synthetic world of test_rules.py (invented values).

Each test checks both that the feedback changes the key it names (with learned_at) and that it does NOT spread:
another person, another lane, another month, another invoice keep their own answer.
"""
from __future__ import annotations

import sys
from datetime import date
from decimal import Decimal as D
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "harness"))

from test_rules import CID, LANE, LANE2, R, amendment, email, invoice, msa, notice, tracking, world  # noqa: E402

from nova import policy  # noqa: E402
from nova.evaluate import _directives, _learned, evaluate_all  # noqa: E402
from nova.feedback import FeedbackItem  # noqa: E402


def fb(item_id, decision, fact_type, key, subject, value, kind, applies_to, vfrom, vto=None, decided=date(2041, 8, 1)):
    return FeedbackItem(item_id, decision, fact_type, key, subject, value, kind, applies_to, vfrom, vto, decided,
                        "batch_01")


def run(docs, fbs, as_of="2041-09-30", mode="supervised"):
    """The report pipeline minus I/O: rules with and without feedback, directives, actions, learned_at."""
    w = world(docs, as_of, fbs)
    outs = _directives(evaluate_all(w), fbs, w)
    policy.assign_actions(outs, mode)
    base = evaluate_all(world(docs, as_of, []))
    policy.assign_actions(base, mode)
    _learned(outs, {o.key: o for o in base})
    return {o.key: o for o in outs}


def waiver_email(doc_id, sender, awbs=(), months=()):
    return email(doc_id, "2041-07-12T00:00:00Z", sender, {"kind": "waiver", "waivers": [{
        "charge_label": "Delivery fee", "awbs": list(awbs), "months": list(months), "invoice_ids": [],
        "conditional": False, "condition_text": None, "condition_met": "unknown", "in_senders_own_text": True,
        "original_sender_name": None, "original_sender_addr": None, "original_date": None, "original_cited_as": None,
        "ref": R(1, 8)}]})


def inv_dlv(doc_id, number, awb, day="2041-07-10"):
    return invoice(doc_id, "2041-07-20T00:00:00Z", number, "2041-07-20",
                   [(awb, "Delivery fee", "1", "40.00", "40.00", day, None)])


def test_confirm_sender_authority_applies_to_that_person_and_category_only():
    docs = [msa(), inv_dlv("b1/0101.eml#A.pdf", "INV-A1", "QA10000001"), inv_dlv("b1/0102.eml#B.pdf", "INV-A2", "QA10000002"),
            waiver_email("b1/0103.eml", ("Ny Kam", "ny@car.test"), awbs=["QA10000001"]),          # KAM: no waivers
            waiver_email("b1/0104.eml", ("Kai Rates", "kai.rates@car.test"), awbs=["QA10000002"])]  # rates only
    assert ("waived_but_billed", "INV-A1") not in run(docs, [])
    f = fb("fb-1", "confirm", "sender_authority", ("waived_but_billed", "INV-A1"),
           {"person": "Ny Kam", "party": "CAR-X"}, {"categories": ["waivers"]}, "standing",
           {"contract_id": CID, "person": "Ny Kam", "category": "waivers"}, date(2041, 7, 1))
    out = run(docs, [f])
    o = out[("waived_but_billed", "INV-A1")]
    assert o.verdict == "finding" and o.amount_usd == D("40.00") and o.learned_at["feedback_item_id"] == "fb-1"
    assert ("waived_but_billed", "INV-A2") not in out              # another person is not covered


def test_confirm_sender_authority_respects_valid_from():
    docs = [msa(), inv_dlv("b1/0101.eml#A.pdf", "INV-A1", "QA10000001"),
            waiver_email("b1/0103.eml", ("Ny Kam", "ny@car.test"), awbs=["QA10000001"])]
    f = fb("fb-1", "confirm", "sender_authority", ("waived_but_billed", "INV-A1"), {"person": "Ny Kam"},
           {"categories": ["waivers"]}, "standing", {"contract_id": CID, "person": "Ny Kam", "category": "waivers"},
           date(2041, 8, 1))                                       # waiver email dated 2041-07-12: before scope
    assert ("waived_but_billed", "INV-A1") not in run(docs, [f])


def overbilled(doc_id, number, awb, lane=LANE, rate="4.80"):
    amount = f"{D(rate) * 150:.2f}"
    d = invoice(doc_id, "2041-07-20T00:00:00Z", number, "2041-07-20",
                [(awb, "Air freight", "150", rate, amount, "2041-07-10", None)])
    if lane != LANE:
        import json
        ex = json.loads(d["extract_json"])
        for l in ex["data"]["lines"]:
            l["lane"] = lane
        d["extract_json"] = json.dumps(ex)
    return d


def test_close_dispute_closed_stops_only_that_key():
    docs = [msa(), overbilled("b1/0201.eml#A.pdf", "INV-B1", "QA20000001"),
            overbilled("b1/0202.eml#B.pdf", "INV-B2", "QA20000002"),
            tracking([("QA20000001", "PICKED_UP", "2041-07-10"), ("QA20000002", "PICKED_UP", "2041-07-10")])]
    f = fb("fb-2", "close", "dispute_closed", ("overcharge", "INV-B1"), {"invoice_id": "INV-B1"},
           {"status": "closed"}, "one_off", {"invoice_id": "INV-B1"}, date(2041, 8, 1))
    out = run(docs, [f])
    assert ("overcharge", "INV-B1") not in out
    assert out[("overcharge", "INV-B2")].amount_usd == D("60.00")   # same wrong rate, new invoice: still a finding


def test_reject_drops_only_that_key():
    docs = [msa(), overbilled("b1/0201.eml#A.pdf", "INV-B1", "QA20000001"),
            overbilled("b1/0202.eml#B.pdf", "INV-B2", "QA20000002"),
            tracking([("QA20000001", "PICKED_UP", "2041-07-10"), ("QA20000002", "PICKED_UP", "2041-07-10")])]
    f = fb("fb-5", "reject", "waiver_scope", ("overcharge", "INV-B2"), {}, {}, "one_off", {"invoice_id": "INV-B2"},
           date(2041, 8, 1))
    out = run(docs, [f])
    assert ("overcharge", "INV-B2") not in out and ("overcharge", "INV-B1") in out


def test_rate_accepted_measures_later_invoices_against_the_notice_on_that_lane_only():
    rn = notice(("Ny Kam", "ny@car.test"), rate="4.60")            # unauthorised notice, later accepted
    docs = [msa(), rn, overbilled("b1/0301.eml#A.pdf", "INV-C1", "QA30000001", rate="4.60"),
            overbilled("b1/0302.eml#B.pdf", "INV-C2", "QA30000002", rate="4.80"),
            overbilled("b1/0303.eml#C.pdf", "INV-C3", "QA30000003", lane=LANE2, rate="4.60"),
            tracking([(f"QA3000000{i}", "PICKED_UP", "2041-07-10") for i in (1, 2, 3)])]
    f = fb("fb-3", "close", "rate_accepted", ("overcharge", "INV-OLD"), {"contract_id": CID, "lane": LANE},
           {"source": "rate notice", "sent_by": "Ny Kam", "effective_from": "2041-06-01", "effective_to": "2041-12-31"},
           "standing", {"contract_id": CID, "lane": LANE}, date(2041, 6, 1), date(2041, 12, 31))
    out = run(docs, [f])
    assert ("overcharge", "INV-C1") not in out                       # billed at the accepted rate: fine
    o2 = out[("overcharge", "INV-C2")]
    assert o2.amount_usd == D("30.00") and o2.learned_at["feedback_item_id"] == "fb-3"   # (4.80-4.60) x 150
    o3 = out[("overcharge", "INV-C3")]
    assert o3.amount_usd == D("240.00") and getattr(o3, "learned_at", None) is None      # other lane: MSA 3.00


def statement_line_doc(doc_id, number, month):
    import json
    d = invoice(doc_id, f"{month}-28T00:00:00Z", number, f"{month}-28",
                [(None, "Delivery fee", "1", "40.00", "40.00", None, None)])
    ex = json.loads(d["extract_json"])
    ex["data"]["lines"][0]["ref_period"] = month
    ex["data"]["document_kind"] = "statement"
    d["extract_json"] = json.dumps(ex)
    return d


def test_one_off_approval_covers_named_month_on_that_key_only():
    oct_ = statement_line_doc("b1/0401.eml#S10.xlsx", "ST-4110", "2041-10")
    nov_ = statement_line_doc("b1/0402.eml#S11.xlsx", "ST-4111", "2041-11")
    w = waiver_email("b1/0403.eml", ("Ny Kam", "ny@car.test"), months=["2041-10", "2041-11"])  # no authority
    f = fb("fb-4", "one_off_approval", "waiver_scope", ("waived_but_billed", "ST-4110"),
           {"person": "Ny Kam", "party": "CAR-X"}, {"months": ["2041-10"]}, "one_off", {"invoice_id": "ST-4110"},
           date(2041, 11, 30))
    out = run([msa(), oct_, nov_, w], [f], as_of="2041-12-15")
    o = out[("waived_but_billed", "ST-4110")]
    assert o.amount_usd == D("40.00") and o.learned_at["feedback_item_id"] == "fb-4"
    assert ("waived_but_billed", "ST-4111") not in out               # November is not covered (cap-at-40 guard)


def test_resolve_conflict_uses_named_source_from_valid_from():
    amd = amendment(rows=[(LANE, "range", "100", "299.5", "4.00")])
    rn = notice(("Kai Rates", "kai.rates@car.test"), rate="4.30")
    inv = invoice("b1/0501.eml#A.pdf", "2041-07-20T00:00:00Z", "INV-E1", "2041-07-20",
                  [("QA50000001", "Air freight", "100", "4.30", "430.00", "2041-07-10", None)])
    docs = [msa(), amd, rn, inv, tracking([("QA50000001", "PICKED_UP", "2041-07-10")])]
    assert run(docs, [])[("overcharge", "INV-E1")].verdict == "conflict"
    f = fb("fb-6", "resolve_conflict", "precedence", ("overcharge", "INV-E1"), {"contract_id": CID, "lane": LANE},
           {"use": "amendment"}, "standing", {"contract_id": CID, "lane": LANE}, date(2041, 6, 1))
    o = run(docs, [f])[("overcharge", "INV-E1")]
    assert o.verdict == "finding" and o.amount_usd == D("30.00") and o.learned_at["feedback_item_id"] == "fb-6"


def test_override_amount():
    docs = [msa(), overbilled("b1/0601.eml#A.pdf", "INV-F1", "QA60000001"),
            tracking([("QA60000001", "PICKED_UP", "2041-07-10")])]
    f = fb("fb-7", "override_amount", "dispute_closed", ("overcharge", "INV-F1"), {"invoice_id": "INV-F1"},
           {"status": "settled", "amount_usd": "21.50"}, "one_off", {"invoice_id": "INV-F1"}, date(2041, 8, 1))
    o = run(docs, [f])[("overcharge", "INV-F1")]
    assert o.amount_usd == D("21.50") and o.learned_at["feedback_item_id"] == "fb-7"


def test_unknown_feedback_kind_changes_nothing():
    docs = [msa(), overbilled("b1/0201.eml#A.pdf", "INV-B1", "QA20000001"),
            tracking([("QA20000001", "PICKED_UP", "2041-07-10")])]
    f = fb("fb-9", "annotate", "something_new", ("overcharge", "INV-B1"), {}, {}, "standing", {"contract_id": CID},
           date(2041, 1, 1))
    assert run(docs, [f])[("overcharge", "INV-B1")].amount_usd == D("60.00")
