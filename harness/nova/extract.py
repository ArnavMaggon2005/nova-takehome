"""Turn each stored document into a typed extraction (docs/PLAN.md sections 3 and 11).

emails       -> EMAIL (doc model); rate-notice emails also -> RATE_NOTICE (contract model)
attachments  -> CLASSIFY (doc model), then by type:
   msa                         -> CONTRACT_TERMS, RATES, ANNEXES, SCHEDULE1 (contract model, one cached copy of text)
   amendment / annex / ext.    -> AMENDMENT (contract model)
   rate_notice                 -> RATE_NOTICE (contract model)
   invoice / statement / CN    -> INVOICE (doc model); scans: OCR text first, vision if lines don't add up
   ap_register / tracking      -> TABLE (doc model) column map, then Python reads every row
   awb / dg / customs          -> SHIPPING (doc model)
Every extraction is number-checked against its cited lines; if that check fails it is re-extracted once with the
errors fed back. A document that runs out of time stays pending and is finished by the next command.
"""
from __future__ import annotations

import json
import re
import time
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

import config

from . import ocr, prompts as P, schemas as SC, verify
from .llm import BudgetExceeded, LLMError, image_block, text_block
from .money import dec
from .textlayer import render_numbered

CONTRACT_TYPES = {"msa", "amendment", "annex_update", "contract_extension", "rate_notice"}


class Extractor:
    def __init__(self, state, llm, budget, launch_fraction: float):
        self.state = state
        self.llm = llm
        self.budget = budget
        self.launch_cutoff = budget.start + (budget.deadline - budget.start) * launch_fraction
        self.sections = ThreadPoolExecutor(max_workers=4)

    # ---- driver --------------------------------------------------------------------------------------------------------
    def run(self, docs: list[dict]) -> dict:
        todo = [d for d in docs if d["status"] in ("new", "classified")]
        todo.sort(key=lambda d: (-len(json.loads(d["pages_json"] or "[]")), d["seq"] or 0))   # long docs start first
        done = failed = skipped = 0
        with ThreadPoolExecutor(max_workers=config.LLM_THREADS) as pool:
            futures = [pool.submit(self._job, d) for d in todo]
            for f in futures:
                r = f.result()
                done += r == "extracted"
                failed += r == "failed"
                skipped += r == "pending"
        self.sections.shutdown(wait=True)
        return {"extracted": done, "failed": failed, "pending": skipped, "usage": dict(self.llm.usage)}

    def _job(self, doc: dict) -> str:
        if time.monotonic() > self.launch_cutoff:
            return "pending"
        try:
            upd = self.process(doc)
        except BudgetExceeded:
            return "pending"
        except (LLMError, Exception) as e:                    # noqa: BLE001 - one bad document never stops the batch
            attempts = (doc.get("attempts") or 0) + 1
            status = "failed" if attempts >= 2 else doc["status"]
            self.state.update_doc(doc["doc_id"], attempts=attempts, status=status,
                                  errors=f"{type(e).__name__}: {str(e)[:500]}")
            return "failed" if status == "failed" else "pending"
        self.state.update_doc(doc["doc_id"], **upd)
        return upd.get("status", "extracted")

    # ---- one document --------------------------------------------------------------------------------------------------
    def process(self, doc: dict) -> dict:
        pages = json.loads(doc["pages_json"] or "[]")
        if doc["ext"] == "eml":
            return self._email(doc, pages)
        method = "text"
        upd: dict = {}
        if doc["is_scan"]:
            pdf = (Path(self.state.dir) / "pages" / f"{doc['sha256']}.pdf").read_bytes()
            if not any(p.strip() for p in pages):
                pages, _pngs, ocr_conf = ocr.ocr_pdf(pdf)
                upd["pages_json"] = json.dumps(pages)
            method = "ocr"
        cls = json.loads(doc["classify_json"]) if doc.get("classify_json") else None
        if cls is None:
            cls = self.llm.json_call(model=config.MODEL_DOC, system=P.SYSTEM, schema=SC.CLASSIFY,
                                     effort=config.EFFORT_CLASSIFY, max_tokens=config.MAX_TOKENS_CLASSIFY,
                                     purpose="classify", blocks=[text_block(P.CLASSIFY + "\n\n" + _context(doc)),
                                                                 text_block(render_numbered(pages[:2], 70))])
            self.state.update_doc(doc["doc_id"], classify_json=json.dumps(cls), doc_type=cls["doc_type"],
                                  status="classified", **upd)
        t = cls["doc_type"]
        if t == "msa":
            data = self._contract(doc, pages)
        elif t in ("amendment", "annex_update", "contract_extension"):
            data = self._checked(config.MODEL_CONTRACT, P.AMENDMENT, SC.AMENDMENT, pages, config.EFFORT_CONTRACT,
                                 "amendment", doc)
        elif t == "rate_notice":
            data = self._checked(config.MODEL_CONTRACT, P.RATE_NOTICE, SC.RATE_NOTICE, pages, config.EFFORT_CONTRACT,
                                 "rate_notice", doc)
        elif t in ("invoice", "statement", "credit_note"):
            data = self._checked(config.MODEL_DOC, P.INVOICE, SC.INVOICE, pages, config.EFFORT_DOC, "invoice", doc)
            if doc["is_scan"] and not _adds_up(data["data"]):
                pdf = (Path(self.state.dir) / "pages" / f"{doc['sha256']}.pdf").read_bytes()
                data = self._vision(doc, pdf)
                method = "vision"
        elif t in ("ap_register", "tracking_export") and doc["ext"] == "xlsx":
            data = self._table(doc, pages)
        elif t in ("awb", "dg_declaration", "customs_document"):
            data = self._checked(config.MODEL_DOC, P.SHIPPING, SC.SHIPPING, pages, config.EFFORT_DOC, "shipping", doc)
        else:
            data = {"data": None, "errors": [], "stats": {}}
        out = {"type": t, **data}
        return {"status": "extracted", "doc_type": t, "extract_json": json.dumps(out), "method": method, **upd}

    # ---- kinds ---------------------------------------------------------------------------------------------------------
    def _email(self, doc: dict, pages: list[str]) -> dict:
        res = self._checked(config.MODEL_DOC, P.EMAIL, SC.EMAIL, pages, config.EFFORT_DOC, "email", doc)
        out = {"type": "email", **res}
        if (res["data"] or {}).get("kind") == "rate_notice":
            out["rate_notice"] = self._checked(config.MODEL_CONTRACT, P.RATE_NOTICE, SC.RATE_NOTICE, pages,
                                               config.EFFORT_CONTRACT, "rate_notice", doc)
        return {"status": "extracted", "doc_type": "email", "extract_json": json.dumps(out), "method": "text"}

    def _contract(self, doc: dict, pages: list[str]) -> dict:
        jobs = {name: self.sections.submit(self._checked, config.MODEL_CONTRACT, instr, schema, pages,
                                           config.EFFORT_CONTRACT, f"msa_{name}", doc, True)
                for name, instr, schema in (("terms", P.CONTRACT_TERMS, SC.CONTRACT_TERMS),
                                            ("rates", P.RATES, SC.RATES), ("annexes", P.ANNEXES, SC.ANNEXES),
                                            ("schedule1", P.SCHEDULE1, SC.SCHEDULE1))}
        parts = {k: f.result() for k, f in jobs.items()}
        return {"data": {k: v["data"] for k, v in parts.items()},
                "errors": [e for v in parts.values() for e in v["errors"]],
                "stats": {k: v["stats"] for k, v in parts.items()},
                "conf": min(v["conf"] for v in parts.values())}

    def _table(self, doc: dict, pages: list[str]) -> dict:
        head = [("\n".join(p.split("\n")[:25])) for p in pages]
        res = self._call(config.MODEL_DOC, P.TABLE, SC.TABLE, head, config.EFFORT_DOC, "table", doc)
        rows = parse_table(res, pages)
        return {"data": {**res, "rows": rows}, "errors": [] if rows else ["no rows parsed"],
                "stats": {"rows": len(rows)}, "conf": 0.95 if rows else 0.3}

    def _vision(self, doc: dict, pdf: bytes) -> dict:
        blocks = [text_block(P.INVOICE + "\n" + P.VISION + "\n\n" + _context(doc))]
        blocks += [image_block(png) for png in ocr.render_pages(pdf)]
        data = self.llm.json_call(model=config.MODEL_DOC, system=P.SYSTEM, blocks=blocks, schema=SC.INVOICE,
                                  effort=config.EFFORT_DOC, max_tokens=config.MAX_TOKENS_EXTRACT, purpose="vision")
        return {"data": data, "errors": [] if _adds_up(data) else ["vision lines do not add up to the total"],
                "stats": {}, "conf": 0.85 if _adds_up(data) else 0.5}

    # ---- calls with number checking --------------------------------------------------------------------------------
    def _call(self, model, instr, schema, pages, effort, purpose, doc, cache_doc=False, feedback=None):
        doc_block = text_block(render_numbered(pages))
        lead = text_block(instr + "\n\n" + _context(doc))
        blocks = [doc_block, lead] if cache_doc else [lead, doc_block]
        if feedback:
            blocks.append(text_block("Your previous answer for this document had these problems; re-read the "
                                     "document and return the complete corrected JSON:\n- " + "\n- ".join(feedback)))
        return self.llm.json_call(model=model, system=P.SYSTEM, blocks=blocks, schema=schema, effort=effort,
                                  max_tokens=config.MAX_TOKENS_EXTRACT, purpose=purpose, cache_doc_block=cache_doc)

    def _checked(self, model, instr, schema, pages, effort, purpose, doc, cache_doc=False) -> dict:
        data = self._call(model, instr, schema, pages, effort, purpose, doc, cache_doc)
        errors, stats = verify.check(data, pages)
        if errors:
            data2 = self._call(model, instr, schema, pages, effort, purpose + "_retry", doc, cache_doc,
                               feedback=errors[:40])
            errors2, stats2 = verify.check(data2, pages)
            if len(errors2) <= len(errors):
                data, errors, stats = data2, errors2, stats2
        return {"data": data, "errors": errors, "stats": stats, "conf": verify.confidence(stats)}


# ---- helpers ------------------------------------------------------------------------------------------------------------
def _context(doc: dict) -> str:
    who = f"{doc.get('sender_name') or ''} <{doc.get('sender_addr') or ''}>"
    if doc["ext"] == "eml":
        return f"(Email received {doc.get('received_at')}.)"
    return (f"(Attachment file name: {doc.get('attachment')}; carried by an email from {who} with subject "
            f"{doc.get('subject')!r}, received {doc.get('received_at')}.)")


def _adds_up(inv: dict | None) -> bool:
    """Scanned bill sanity: lines sum to the subtotal (or total less tax), and rate x qty = amount on kg lines."""
    if not inv or not inv.get("lines"):
        return False
    s = sum((dec(l.get("amount")) or 0) for l in inv["lines"])
    target = dec(inv.get("subtotal"))
    if target is None and dec(inv.get("total")) is not None:
        target = dec(inv["total"]) - (dec(inv.get("tax_amount")) or 0)
    if target is None or abs(s - target) > dec("0.01"):
        return False
    for l in inv["lines"]:
        q, r, a = dec(l.get("qty")), dec(l.get("rate")), dec(l.get("amount"))
        if None in (q, r, a):
            continue
        expect = (r * q / 100) if l.get("rate_is_percent") else (r * q)
        if abs(expect - a) > dec("0.011"):
            return False
    return True


_ISO = re.compile(r"(\d{4})-(\d{2})-(\d{2})")


def parse_table(spec: dict, pages: list[str]) -> list[dict]:
    """Read every data row of a mapped spreadsheet table. Cells are the ' | ' separated values of the text layer."""
    sheet = int(spec.get("sheet") or 1)
    if not 1 <= sheet <= len(pages):
        sheet = 1
    lines = pages[sheet - 1].split("\n")
    cols = spec.get("columns") or {}
    statuses = {str(x["printed"]).strip().lower(): x["meaning"] for x in spec.get("status_values") or []}
    events = {str(x["printed"]).strip().upper(): x["meaning"] for x in spec.get("event_values") or []}
    header = int(spec.get("header_line") or 1)
    out = []
    for i in range(header, len(lines)):           # 0-based index i == 1-based line i+1, so this starts after header
        cells = [c.strip() for c in lines[i].split(" | ")]

        def cell(name):
            j = cols.get(name)
            return cells[j] if j is not None and 0 <= j < len(cells) else None
        row = {"ref": {"page": sheet, "line": i + 1}, "cells": cells}
        if spec.get("table_kind") == "ap_register":
            inv = cell("invoice_id")
            if not inv:
                continue
            amt = cell("amount") or ""
            cur = cell("currency") or (re.search(r"\b([A-Z]{3})\b", amt).group(1) if re.search(r"\b[A-Z]{3}\b", amt) else None)
            row.update(invoice_id=inv, invoice_date=_date(cell("invoice_date")), due_date=_date(cell("due_date")),
                       amount=str(dec(amt)) if dec(amt) is not None else None, currency=cur,
                       status=statuses.get((cell("status") or "").strip().lower(), (cell("status") or "").lower()),
                       paid_date=_date(cell("paid_date")))
        elif spec.get("table_kind") == "tracking_export":
            awb = cell("awb")
            if not awb:
                continue
            ev = (cell("event") or "").strip()
            row.update(awb=awb, event=events.get(ev.upper(), ev.upper()), date=_date(cell("event_date")),
                       station=cell("station"), reason=cell("reason"))
        else:
            continue
        out.append(row)
    return out


def _date(s):
    if not s:
        return None
    m = _ISO.search(s)
    if m:
        return m.group(0)
    m = re.search(r"(\d{1,2})[/.](\d{1,2})[/.](\d{4})", s)
    if m:                                          # spreadsheets in these mailboxes are ISO; day-first otherwise
        return f"{m.group(3)}-{int(m.group(2)):02d}-{int(m.group(1)):02d}"
    return None
