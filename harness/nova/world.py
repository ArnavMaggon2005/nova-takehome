"""The fact view for one report: typed facts rebuilt from every extraction received by as_of (docs/PLAN.md s.4).

Nothing here is stored back; each report rebuilds the world from the documents, so arrival order can't matter.
Charge lines are mapped to the contract's own Annex E codes, and codes to generic charge *kinds* (freight, fuel,
security, ...) from their canonical labels, so the rules never depend on one carrier's code names.
"""
from __future__ import annotations

import json
import re
from dataclasses import dataclass, field
from datetime import date, datetime, timedelta
from decimal import Decimal

import config

from .money import dec, month_of, parse_date

# ---- provenance ------------------------------------------------------------------------------------------------------


@dataclass(frozen=True)
class Src:
    doc_id: str
    page: int
    line_from: int
    line_to: int
    received: str = ""

    @staticmethod
    def of(doc, ref: dict | None) -> "Src | None":
        if not isinstance(ref, dict):
            return None
        page = int(ref.get("page") or 1)
        lf = int(ref.get("line") or ref.get("line_from") or 0)
        lt = int(ref.get("line_to") or lf)
        if lf <= 0:
            return None
        return Src(doc["doc_id"], page, lf, max(lf, lt), doc["received_at"])


# ---- charge kinds (generic freight vocabulary, not tied to any carrier) ----------------------------------------------
KIND_WORDS = [
    ("fuel", ("fuel", "fsc")),
    ("programme_fee", ("programme", "program")),
    ("account_fee", ("account fee", "account maintenance")),
    ("security", ("security", "screening")),
    ("dry_ice", ("dry ice",)),
    ("dg", ("dangerous", "hazmat", "dg ")),
    ("storage", ("storage", "warehouse", "demurrage")),
    ("customs", ("customs", "hold handling", "examination")),
    ("delivery", ("delivery",)),
    ("peak", ("peak",)),
    ("duty", ("duty", "disbursement")),
    ("tax", ("tax", "gst", "vat")),
    ("late_fee", ("late", "overdue interest")),
    ("margin", ("margin",)),
    ("cost", ("carrier cost", "pass-through", "linehaul cost")),
    ("handling", ("special handling", "supplementary handling")),
    ("freight", ("freight",)),
]


def kind_of_label(label: str) -> str:
    s = " " + _label(label) + " "
    if s.strip().startswith("dg ") or s.strip() == "dg":
        return "dg"
    for kind, words in KIND_WORDS:
        if any(w in s for w in words):
            return kind
    return "other"


def _label(s: str) -> str:
    s = re.sub(r"\([^)]*\)", " ", str(s or "").lower())
    s = re.sub(r"[^a-z0-9 .\-/]", " ", s)
    return " ".join(s.split())


def norm_id(s) -> str:
    return re.sub(r"[\s#:]", "", str(s or "")).upper()


def norm_awb(s) -> str:
    return re.sub(r"\s", "", str(s or "")).upper()


def norm_lane(s) -> str:
    s = str(s or "")
    for sep in ("–", "—", "→", "->", "⇒", " to ", " TO ", "/"):
        s = s.replace(sep, "-")
    return re.sub(r"\s", "", s).upper()


# Schedule 1 decision categories, canonical name <- words a contract may print instead
CATEGORY_WORDS = [
    ("billing_disputes", ("billing dispute", "billing_disputes", "disputes", "billing resolution")),
    ("payment_terms", ("payment term", "payment_terms", "due date", "credit terms")),
    ("waivers", ("waiver", "waive")),
    ("rates", ("rate", "pricing", "tariff")),
    ("treasury", ("treasury", "exchange", "fx", "currency")),
    ("notices", ("notice", "key account", "account management")),
]


def norm_categories(printed) -> set:
    out = set()
    for raw in printed or []:
        s = " ".join(str(raw).lower().replace("_", " ").split())
        for canon, words in CATEGORY_WORDS:
            if any(w.replace("_", " ") in s for w in words):
                out.add(canon)
                break
        else:
            out.add(s.replace(" ", "_"))
    return out


_CONFUSE = str.maketrans({"0": "O", "1": "I", "L": "I", "5": "S", "8": "B", "2": "Z", "6": "G"})


def skeleton(s: str) -> str:
    return norm_id(s).translate(_CONFUSE).replace("/", "-")


# ---- facts ---------------------------------------------------------------------------------------------------------


@dataclass
class Person:
    name: str
    title: str
    party: str
    side: str
    categories: set
    address: str
    src: Src | None


@dataclass
class RateRow:
    lane: str
    band: str                      # minimum | range | open_ended
    lo: Decimal | None
    hi: Decimal | None
    rates: dict                    # period name (or "*" for every period) -> Decimal
    src: Src | None

    def contains(self, qty: Decimal) -> bool:
        if self.band == "minimum":
            return False
        if self.lo is not None and qty < self.lo:
            return False
        return not (self.hi is not None and qty > self.hi)


@dataclass
class CreditTerm:
    credit_type: str
    basis: str
    tiers: list                    # [(threshold_usd, rate_pct)] ascending
    all_spend: bool
    flat_pct: Decimal | None
    due_days: int | None
    applicable: bool
    src: Src | None


@dataclass
class Contract:
    id: str
    doc_id: str
    received: str
    shipper: dict = field(default_factory=dict)
    carrier: dict = field(default_factory=dict)
    effective: date | None = None
    end: date | None = None
    auto_renews: bool = False
    renewal_notice_days: int | None = None
    signed: bool = True
    currency: str = "USD"
    late_rate: Decimal | None = None
    grace_days: int = 0
    compounding: bool = False
    storage_free_days: int | None = None
    delivery_only_if_delivered: bool = True
    customs_shipper_unless_carrier: bool = True
    notice_vs_amendment: str = "not_stated"
    continuation: bool = False
    qs_includes_accessorials: bool = True
    qs_net_of_credits: bool = True
    qs_per_invoice_fx: bool = True
    credits: list = field(default_factory=list)
    periods: list = field(default_factory=list)          # [(name, start, end, src)]
    rate_rows: list = field(default_factory=list)
    fuel: dict = field(default_factory=dict)             # month -> (pct, src)
    accessorials: dict = field(default_factory=dict)     # code -> dict(fee, basis, months, label, kind, src)
    aliases: dict = field(default_factory=dict)          # normalised label -> code
    code_kind: dict = field(default_factory=dict)        # code -> kind
    alias_src: dict = field(default_factory=dict)        # code -> Src of its Annex E line
    fx: dict = field(default_factory=dict)               # month -> (inr_per_usd, src)
    fx_note: tuple | None = None                         # (document name as cited, issuer text, src)
    persons: list = field(default_factory=list)
    spans: dict = field(default_factory=dict)            # clause name -> Src

    def code_for(self, label: str) -> tuple[str | None, str]:
        """(Annex E code or None, generic kind) for a printed charge label."""
        lab = _label(label)
        if lab in self.aliases:
            code = self.aliases[lab]
            return code, self.code_kind.get(code, kind_of_label(label))
        for alias, code in sorted(self.aliases.items(), key=lambda kv: -len(kv[0])):
            if alias and (lab.startswith(alias + " ") or lab == alias):
                return code, self.code_kind.get(code, kind_of_label(label))
        return None, kind_of_label(label)

    def accessorial(self, kind: str) -> dict | None:
        for a in self.accessorials.values():
            if a["kind"] == kind:
                return a
        return None

    def persons_for(self, category: str, side: str = "carrier") -> list:
        return [p for p in self.persons if category in p.categories and p.side == side]

    def kam(self, side: str = "carrier") -> Person | None:
        ps = self.persons_for("notices", side)
        return ps[0] if ps else None

    @property
    def carrier_party(self) -> str | None:
        ps = [p.party for p in self.persons if p.side == "carrier"]
        return ps[0] if ps else (self.carrier or {}).get("code")


@dataclass
class Line:
    idx: int
    awb: str | None
    label: str
    code: str | None
    kind: str
    lane: str | None
    pickup_printed: date | None
    qty: Decimal | None
    unit: str | None
    rate: Decimal | None
    rate_is_pct: bool
    amount: Decimal
    ref_period: str | None
    late_fee: dict | None
    src: Src | None


@dataclass
class Invoice:
    doc_id: str
    eml_id: str
    received: str
    printed_id: str
    invoice_id: str
    kind: str                      # invoice | statement | credit_note
    contract_id: str | None
    issue_date: date | None
    due_date: date | None
    currency: str
    lines: list
    subtotal: Decimal | None
    tax: Decimal | None
    total: Decimal | None
    total_src: Src | None
    id_src: Src | None
    is_scan: bool
    method: str
    conf: float
    credit: dict | None = None


@dataclass
class LedgerRow:
    invoice_id: str
    invoice_date: date | None
    due_date: date | None
    amount: Decimal | None
    currency: str | None
    status: str
    paid_date: date | None
    src: Src | None
    register_received: str


@dataclass
class Event:
    awb: str
    event: str
    when: date | None
    station: str | None
    source: str                    # export | email
    src: Src | None


@dataclass
class Waiver:
    doc_id: str
    received: str
    sender_name: str
    sender_addr: str
    label: str
    awbs: list
    months: list
    invoice_ids: list
    conditional: bool
    condition_met: str
    own_text: bool
    original: dict
    src: Src | None


@dataclass
class Notice:
    doc_id: str
    received: str
    sender_name: str
    sender_addr: str
    contract_id: str | None
    start: date | None
    end: date | None
    rows: list                     # RateRow with rates {"*": rate}
    own_text: bool
    src: Src | None


@dataclass
class Amendment:
    doc_id: str
    received: str
    contract_id: str
    reference: str | None
    title: str
    effective: date | None
    signed: bool
    rows: list                     # RateRow ("*" period)
    referenced: list               # dicts name_as_cited, lanes, effective_from, attached, src
    fuel: dict
    fx: dict
    new_end: tuple | None          # (date, src)
    src: Src | None
    doc_type: str = "amendment"


class World:
    """Everything the rules need, as of one report date."""

    def __init__(self, docs: list[dict], as_of: date, feedback: list | None = None):
        self.as_of = as_of
        cutoff = datetime(as_of.year, as_of.month, as_of.day, 23, 59, 59).strftime("%Y-%m-%dT%H:%M:%SZ")
        self.docs = {d["doc_id"]: d for d in docs if (d.get("received_at") or "") <= cutoff}
        self.pages = {k: json.loads(d.get("pages_json") or "[]") for k, d in self.docs.items()}
        self.feedback = feedback or []
        self.contracts: dict[str, Contract] = {}
        self.amendments: list[Amendment] = []
        self.notices: list[Notice] = []
        self.invoices: list[Invoice] = []
        self.credit_notes: list[Invoice] = []
        self.registers: list[tuple[str, list[LedgerRow]]] = []
        self.events: dict[str, list[Event]] = {}
        self.waybills: dict[str, dict] = {}
        self.dg: dict[str, list[dict]] = {}
        self.customs: dict[str, list[dict]] = {}
        self.waivers: list[Waiver] = []
        self.extensions: list[dict] = []
        self.emails: dict[str, dict] = {}
        self.directives: list[dict] = []
        self.pending = [k for k, d in self.docs.items() if d["status"] in ("new", "classified")]
        self.failed = [k for k, d in self.docs.items() if d["status"] == "failed"]
        self._build()

    # ---- build -------------------------------------------------------------------------------------------------------
    def _build(self):
        ex = {}
        for k, d in self.docs.items():
            if d.get("extract_json"):
                try:
                    ex[k] = json.loads(d["extract_json"])
                except json.JSONDecodeError:
                    continue
        for k, e in ex.items():
            if e.get("type") == "msa" and e.get("data"):
                self._contract(self.docs[k], e)
        for k, e in ex.items():
            d = self.docs[k]
            t = e.get("type")
            data = e.get("data")
            if not data:
                continue
            for dv in (data.get("directives_to_automation") or []) if isinstance(data, dict) else []:
                self.directives.append({"doc_id": k, **dv})
            if t == "email":
                self._email(d, data, e.get("rate_notice"))
            elif t in ("amendment", "annex_update", "contract_extension"):
                self._amendment(d, data, t)
            elif t == "rate_notice":
                self._notice(d, data)
            elif t in ("invoice", "statement", "credit_note"):
                self._invoice(d, data, e)
            elif t in ("ap_register", "tracking_export"):
                self._table(d, data)
            elif t in ("awb", "dg_declaration", "customs_document"):
                self._shipping(d, data)
        self._reconcile_ids()

    def _contract(self, d, e):
        parts = e["data"]
        terms = parts.get("terms") or {}
        cid = norm_id(terms.get("contract_id"))
        if not cid:
            return
        c = Contract(id=cid, doc_id=d["doc_id"], received=d["received_at"])
        c.shipper, c.carrier = terms.get("shipper") or {}, terms.get("carrier") or {}
        c.effective, c.end = parse_date(terms.get("effective_date")), parse_date(terms.get("end_date"))
        c.auto_renews = bool(terms.get("auto_renews"))
        c.renewal_notice_days = terms.get("renewal_notice_days")
        c.signed = bool(terms.get("signed", True))
        c.currency = (terms.get("currency") or "USD").upper()
        lf = terms.get("late_fee") or {}
        c.late_rate, c.grace_days = dec(lf.get("rate_pct")), int(lf.get("grace_days") or 0)
        c.compounding = bool(lf.get("compounding"))
        c.storage_free_days = (terms.get("storage") or {}).get("free_days")
        c.delivery_only_if_delivered = bool(terms.get("delivery_fee_only_if_carrier_delivers", True))
        c.customs_shipper_unless_carrier = bool(terms.get("customs_fee_shipper_unless_carrier_error", True))
        prec = terms.get("precedence") or {}
        c.notice_vs_amendment = prec.get("notice_vs_amendment") or "not_stated"
        c.continuation = bool(terms.get("last_period_continues"))
        qs = terms.get("qualifying_spend") or {}
        c.qs_includes_accessorials = bool(qs.get("includes_listed_accessorials", True))
        c.qs_net_of_credits = bool(qs.get("net_of_credit_notes", True))
        c.qs_per_invoice_fx = bool(qs.get("foreign_currency_converted_per_invoice", True))
        for name in ("term_span", "renewal_span", "extension_span", "pricing_date_span", "rate_notice_span",
                     "fuel_span", "dry_ice_span", "dg_span", "mixed_dg_span", "delivery_span", "customs_span",
                     "waiver_authority_span", "waiver_scope_span", "continuation_span"):
            s = Src.of(d, terms.get(name))
            if s:
                c.spans[name.replace("_span", "")] = s
        for name, obj in (("late_fee", lf), ("storage", terms.get("storage") or {}),
                          ("precedence", prec), ("qs", qs)):
            s = Src.of(d, (obj or {}).get("span"))
            if s:
                c.spans[name] = s
        s = Src.of(d, prec.get("unranked_span"))
        if s:
            c.spans["unranked"] = s
        for cr in terms.get("credits") or []:
            tiers = sorted(((dec(t.get("threshold_usd")), dec(t.get("rate_pct"))) for t in cr.get("tiers") or []
                            if dec(t.get("threshold_usd")) is not None and dec(t.get("rate_pct")) is not None),
                           key=lambda x: x[0])
            c.credits.append(CreditTerm(cr.get("credit_type"), cr.get("basis"), tiers,
                                        bool(cr.get("rate_applies_to_all_spend", True)), dec(cr.get("flat_rate_pct")),
                                        cr.get("due_days_after_period_end"), bool(cr.get("applicable", True)),
                                        Src.of(d, cr.get("span"))))
        rates = parts.get("rates") or {}
        for p in rates.get("periods") or []:
            st, en = parse_date(p.get("start")), parse_date(p.get("end"))
            if st and en:
                c.periods.append((str(p.get("name")), st, en, Src.of(d, p.get("ref"))))
        c.periods.sort(key=lambda x: x[1])
        for r in rates.get("rows") or []:
            row = _rate_row(d, r, {str(x.get("period")): dec(x.get("rate")) for x in r.get("rates") or []
                                   if dec(x.get("rate")) is not None})
            if row:
                c.rate_rows.append(row)
        ann = parts.get("annexes") or {}
        for f in ann.get("fuel") or []:
            if dec(f.get("pct")) is not None and re.match(r"\d{4}-\d{2}", str(f.get("month"))):
                c.fuel[str(f["month"])[:7]] = (dec(f["pct"]), Src.of(d, f.get("ref")))
        for a in ann.get("aliases") or []:
            code = str(a.get("code") or "").upper()
            labels = [x for x in a.get("labels") or []]
            if not code:
                continue
            c.code_kind[code] = kind_of_label(labels[0]) if labels else "other"
            c.alias_src[code] = Src.of(d, a.get("ref"))
            for lab in labels:
                c.aliases[_label(lab)] = code
        for a in ann.get("accessorials") or []:
            code = str(a.get("code") or "").upper()
            if not code or dec(a.get("fee")) is None:
                continue
            kind = c.code_kind.get(code) or kind_of_label(a.get("label"))
            c.code_kind.setdefault(code, kind)
            c.aliases.setdefault(_label(a.get("label")), code)
            c.accessorials[code] = {"fee": dec(a["fee"]), "basis": a.get("basis"), "label": a.get("label"),
                                    "months": [int(m) for m in a.get("only_in_months") or []], "kind": kind,
                                    "src": Src.of(d, a.get("ref"))}
        for f in ann.get("fx") or []:
            if dec(f.get("inr_per_usd")) is not None and re.match(r"\d{4}-\d{2}", str(f.get("month"))):
                c.fx[str(f["month"])[:7]] = (dec(f["inr_per_usd"]), Src.of(d, f.get("ref")))
        note = ann.get("fx_note")
        if note and note.get("later_rows_document"):
            c.fx_note = (note["later_rows_document"], note.get("issued_by") or "", Src.of(d, note.get("ref")))
        sch = parts.get("schedule1") or {}
        for p in sch.get("persons") or []:
            c.persons.append(Person(str(p.get("name") or "").strip(), str(p.get("title") or ""),
                                    str(p.get("party_code") or "").upper(), str(p.get("side") or "carrier"),
                                    norm_categories(p.get("categories")),
                                    str(p.get("address") or "").strip().lower(), Src.of(d, p.get("ref"))))
        if cid in self.contracts and self.contracts[cid].received <= c.received:
            return
        self.contracts[cid] = c

    def _email(self, d, data, rate_notice):
        self.emails[d["doc_id"]] = data
        for w in data.get("waivers") or []:
            self.waivers.append(Waiver(d["doc_id"], d["received_at"], d.get("sender_name") or "",
                                       d.get("sender_addr") or "", str(w.get("charge_label") or ""),
                                       [norm_awb(x) for x in w.get("awbs") or []],
                                       [str(x)[:7] for x in w.get("months") or []],
                                       [norm_id(x) for x in w.get("invoice_ids") or []],
                                       bool(w.get("conditional")), str(w.get("condition_met") or "unknown"),
                                       bool(w.get("in_senders_own_text", True)),
                                       {"name": w.get("original_sender_name"), "addr": w.get("original_sender_addr"),
                                        "date": w.get("original_date"), "cited_as": w.get("original_cited_as")},
                                       Src.of(d, w.get("ref"))))
        for x in data.get("due_date_extensions") or []:
            nd = parse_date(x.get("new_due_date"))
            if nd:
                self.extensions.append({"invoice_id": norm_id(x.get("invoice_id")), "new_due": nd,
                                        "own_text": bool(x.get("in_senders_own_text", True)),
                                        "sender_addr": d.get("sender_addr") or "", "sender_name": d.get("sender_name"),
                                        "received": d["received_at"], "src": Src.of(d, x.get("ref")),
                                        "doc_id": d["doc_id"]})
        for x in data.get("status_events") or []:
            self._event(norm_awb(x.get("awb")), x.get("event"), parse_date(x.get("date")), x.get("station"),
                        "email", Src.of(d, x.get("ref")), d)
        for x in data.get("customs") or []:
            self.customs.setdefault(norm_awb(x.get("awb")), []).append({**x, "src": Src.of(d, x.get("ref")),
                                                                        "doc_id": d["doc_id"]})
        if rate_notice and rate_notice.get("data"):
            self._notice(d, rate_notice["data"])

    def _event(self, awb, ev, when, station, source, src, d):
        if not awb:
            return
        self.events.setdefault(awb, []).append(Event(awb, str(ev or "OTHER").upper(), when, station, source, src))

    def _amendment(self, d, data, t):
        cid = norm_id(data.get("contract_id"))
        rows = []
        for ch in data.get("rate_changes") or []:
            for r in ch.get("rows") or []:
                row = _rate_row(d, r, {"*": dec(r.get("rate"))})
                if row and row.rates["*"] is not None:
                    rows.append(row)
        new_end = None
        for tc in data.get("term_changes") or []:
            if tc.get("kind") == "new_end_date" and parse_date(tc.get("new_end_date")):
                new_end = (parse_date(tc["new_end_date"]), Src.of(d, tc.get("ref")))
        self.amendments.append(Amendment(
            d["doc_id"], d["received_at"], cid, data.get("reference"), str(data.get("title") or ""),
            parse_date(data.get("effective_from")), bool(data.get("signed")), rows,
            [{"name": str(r.get("name_as_cited") or ""), "lanes": [norm_lane(x) for x in r.get("lanes") or []],
              "from": parse_date(r.get("effective_from")), "attached": bool(r.get("attached_or_incorporated")),
              "src": Src.of(d, r.get("ref"))} for r in data.get("referenced_documents") or []],
            {str(f["month"])[:7]: (dec(f["pct"]), Src.of(d, f.get("ref"))) for f in data.get("fuel") or []
             if dec(f.get("pct")) is not None},
            {str(f["month"])[:7]: (dec(f["inr_per_usd"]), Src.of(d, f.get("ref"))) for f in data.get("fx") or []
             if dec(f.get("inr_per_usd")) is not None},
            new_end, Src.of(d, data.get("span")), t))

    def _notice(self, d, data):
        rows = []
        for r in data.get("rows") or []:
            row = _rate_row(d, r, {"*": dec(r.get("rate"))})
            if row and row.rates["*"] is not None:
                rows.append(row)
        if not rows:
            return
        self.notices.append(Notice(d["doc_id"], d["received_at"], d.get("sender_name") or "",
                                   d.get("sender_addr") or "", norm_id(data.get("contract_id")) or None,
                                   parse_date(data.get("effective_from")), parse_date(data.get("effective_to")), rows,
                                   bool(data.get("in_senders_own_text", True)), rows[0].src))

    def _invoice(self, d, data, e):
        lines = []
        for i, l in enumerate(data.get("lines") or []):
            amt = dec(l.get("amount"))
            if amt is None:
                continue
            lines.append(Line(i, norm_awb(l.get("awb")) or None, str(l.get("charge_label") or ""), None,
                              kind_of_label(l.get("charge_label")), norm_lane(l.get("lane")) or None,
                              parse_date(l.get("pickup_date")), dec(l.get("qty")), l.get("qty_unit"),
                              dec(l.get("rate")), bool(l.get("rate_is_percent")), amt,
                              (str(l.get("ref_period"))[:7] if l.get("ref_period") else None),
                              l.get("late_fee"), Src.of(d, l.get("ref"))))
        eml_id = d["doc_id"].split("#")[0]
        kind = data.get("document_kind") or "invoice"
        inv = Invoice(d["doc_id"], eml_id, d["received_at"], str(data.get("printed_id") or ""),
                      norm_id(data.get("printed_id")), kind, norm_id(data.get("contract_ref")) or None,
                      parse_date(data.get("issue_date")), parse_date(data.get("due_date")),
                      str(data.get("currency") or "USD").upper()[:3], lines, dec(data.get("subtotal")),
                      dec(data.get("tax_amount")), dec(data.get("total")), Src.of(d, data.get("total_ref")),
                      Src.of(d, data.get("id_ref")), bool(d.get("is_scan")), d.get("method") or "text",
                      float(e.get("conf") or 0.9), data.get("credit"))
        if kind == "credit_note":
            self.credit_notes.append(inv)
        elif kind in ("invoice", "statement"):
            self.invoices.append(inv)

    def _table(self, d, data):
        rows = data.get("rows") or []
        if data.get("table_kind") == "ap_register":
            out = []
            for r in rows:
                out.append(LedgerRow(norm_id(r.get("invoice_id")), parse_date(r.get("invoice_date")),
                                     parse_date(r.get("due_date")), dec(r.get("amount")), r.get("currency"),
                                     str(r.get("status") or ""), parse_date(r.get("paid_date")),
                                     Src.of(d, r.get("ref")), d["received_at"]))
            self.registers.append((d["received_at"], out))
        elif data.get("table_kind") == "tracking_export":
            for r in rows:
                self._event(norm_awb(r.get("awb")), r.get("event"), parse_date(r.get("date")), r.get("station"),
                            "export", Src.of(d, r.get("ref")), d)

    def _shipping(self, d, data):
        awb = norm_awb(data.get("awb"))
        if not awb:
            return
        if data.get("kind") in ("awb", "master_awb"):
            self.waybills[awb] = {**data, "doc_id": d["doc_id"], "src": Src.of(d, data.get("ref")),
                                  "executed": parse_date(data.get("executed_on"))}
            for h in data.get("houses") or []:
                self.waybills.setdefault(norm_awb(h.get("awb")), {"master": awb, "doc_id": d["doc_id"],
                                                                  "executed": parse_date(data.get("executed_on")),
                                                                  "src": Src.of(d, h.get("ref"))})
        if data.get("dg_items"):
            self.dg.setdefault(awb, []).extend({**x, "src": Src.of(d, x.get("ref"))} for x in data["dg_items"])
        if data.get("customs"):
            self.customs.setdefault(awb, []).append({**data["customs"], "src": Src.of(d, data["customs"].get("ref")),
                                                    "doc_id": d["doc_id"]})

    def _reconcile_ids(self):
        """Scanned bills: if the read number is an OCR confusion of a number in the carrying email or the ledger,
        use that number (e.g. letter I read as digit 1)."""
        known = set()
        for e in self.emails.values():
            known.update(norm_id(r.get("invoice_id")) for r in e.get("invoice_refs") or [])
        for _, rows in self.registers:
            known.update(r.invoice_id for r in rows)
        by_skel = {}
        for k in known:
            by_skel.setdefault(skeleton(k), set()).add(k)
        for inv in self.invoices + self.credit_notes:
            if inv.invoice_id in known:
                continue
            cands = by_skel.get(skeleton(inv.invoice_id), set())
            if len(cands) == 1:
                inv.invoice_id = next(iter(cands))
        for inv in self.invoices:
            c = self.contract_for(inv)
            if c:
                for l in inv.lines:
                    l.code, l.kind = c.code_for(l.label)

    # ---- lookups -----------------------------------------------------------------------------------------------------
    def contract_for(self, inv) -> Contract | None:
        if inv.contract_id and inv.contract_id in self.contracts:
            return self.contracts[inv.contract_id]
        refs = [norm_id(x) for x in (self.emails.get(inv.eml_id) or {}).get("contract_ids") or []]
        for r in refs:
            if r in self.contracts:
                return self.contracts[r]
        same = [c for c in self.contracts.values() if c.currency == inv.currency]
        return same[0] if len(same) == 1 else None

    def ledger(self) -> dict[str, LedgerRow]:
        """The latest AP register held by as_of."""
        if not self.registers:
            return {}
        _, rows = max(self.registers, key=lambda x: x[0])
        return {r.invoice_id: r for r in rows}

    def pickup(self, awb: str | None, printed: date | None) -> tuple[date | None, str, Src | None]:
        """GLOSSARY ladder: tracking PICKED_UP > carrier picked-up email > AWB date > date printed on the invoice."""
        if awb:
            for source in ("export", "email"):
                evs = [e for e in self.events.get(awb, []) if e.event == "PICKED_UP" and e.source == source and e.when]
                if evs:
                    e = min(evs, key=lambda e: e.when)
                    return e.when, "tracking" if source == "export" else "picked_up_email", e.src
            wb = self.waybills.get(awb)
            if wb and wb.get("executed"):
                return wb["executed"], "awb", wb.get("src")
        if printed:
            return printed, "invoice", None
        return None, "none", None

    def fx_rate(self, contract: Contract, month: str):
        for a in sorted(self.amendments, key=lambda a: a.received):
            if a.contract_id == contract.id and month in a.fx and a.signed:
                return a.fx[month]
        return contract.fx.get(month)

    def fuel_pct(self, contract: Contract, month: str):
        for a in sorted(self.amendments, key=lambda a: a.received, reverse=True):
            if a.contract_id == contract.id and month in a.fuel and a.signed:
                return a.fuel[month]
        return contract.fuel.get(month)

    def person_by_addr(self, contract: Contract, addr: str) -> Person | None:
        addr = (addr or "").lower()
        for p in contract.persons:
            if p.address and p.address == addr:
                return p
        return None

    def authorised(self, contract: Contract, addr: str, name: str, category: str, on: date | None,
                   side: str = "carrier") -> tuple[bool, Person | None, object]:
        """(ok, Schedule 1 person, feedback item that granted it). Exact address match (MSA s.12)."""
        p = self.person_by_addr(contract, addr)
        if p and category in p.categories and p.side == side:
            return True, p, None
        for fb in self.feedback:
            if fb.decision == "confirm" and fb.fact_type == "sender_authority":
                cats = {str(x).lower() for x in (fb.value or {}).get("categories") or []}
                subj = fb.subject or {}
                if category in cats and _same(subj.get("person"), name) and \
                        fb.matches(contract_id=contract.id, person=name, category=category) and fb.in_dates(on):
                    return True, p, fb
        return False, p, None

    def received_date(self, doc_id: str) -> date | None:
        d = self.docs.get(doc_id)
        return parse_date((d or {}).get("received_at", "")[:10]) if d else None


def _same(a, b) -> bool:
    return " ".join(str(a or "").split()).lower() == " ".join(str(b or "").split()).lower() and bool(a)


def _rate_row(d, r: dict, rates: dict) -> RateRow | None:
    lane = norm_lane(r.get("lane"))
    if not lane:
        return None
    return RateRow(lane, str(r.get("band") or "range"), dec(r.get("low_kg")), dec(r.get("high_kg")), rates,
                   Src.of(d, r.get("ref")))


def period_of(contract: Contract, when: date) -> str | None:
    for name, st, en, _ in contract.periods:
        if st <= when <= en:
            return name
    if contract.periods and when > contract.periods[-1][2] and contract.continuation:
        return contract.periods[-1][0]
    return None


def days(a: date, b: date) -> int:
    return (a - b).days


__all__ = ["World", "Src", "Contract", "Invoice", "Line", "LedgerRow", "Event", "Waiver", "Notice", "Amendment",
           "RateRow", "CreditTerm", "Person", "period_of", "norm_id", "norm_awb", "norm_lane", "month_of", "config"]
