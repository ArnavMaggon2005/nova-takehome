"""Read one batch folder: every .eml and its attachments become document rows in the grader's `doc` format."""
from __future__ import annotations

import hashlib
import json
from datetime import timezone
from email.utils import getaddresses, parseaddr, parsedate_to_datetime
from pathlib import Path

from . import textlayer as T


def _received_at(msg) -> str:
    try:
        dt = parsedate_to_datetime(str(msg["Date"]))
        if dt.tzinfo is None:
            dt = dt.replace(tzinfo=timezone.utc)
        return dt.astimezone(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    except (TypeError, ValueError):
        return ""


def read_batch(batch_dir: Path) -> list[dict]:
    """-> document rows (email bodies and attachments), in file order. Pages are the grader's text layer."""
    batch_dir = Path(batch_dir)
    batch = batch_dir.name
    rows: list[dict] = []
    for f in sorted(batch_dir.glob("*.eml")):
        data = f.read_bytes()
        msg = T.parse_eml(data)
        name, addr = parseaddr(str(msg["From"]))
        to = [a.lower() for _, a in getaddresses([str(msg.get("To") or ""), str(msg.get("Cc") or "")]) if a]
        common = {"batch": batch, "eml": f.name, "received_at": _received_at(msg), "sender_name": name,
                  "sender_addr": (addr or "").lower(), "to_addrs": json.dumps(to), "subject": str(msg["Subject"] or "")}
        email_doc = f"{batch}/{f.name}"
        rows.append({**common, "doc_id": email_doc, "attachment": None, "ext": "eml",
                     "sha256": hashlib.sha256(data).hexdigest(), "is_scan": 0,
                     "pages_json": json.dumps(["\n".join(T.email_lines(msg))])})
        for att_name, att in T.attachments(data):
            ext = att_name.rsplit(".", 1)[-1].lower() if "." in att_name else ""
            row = {**common, "doc_id": f"{email_doc}#{att_name}", "attachment": att_name, "ext": ext,
                   "sha256": hashlib.sha256(att).hexdigest(), "is_scan": 0, "pages_json": json.dumps([])}
            try:
                if ext == "pdf":
                    row["is_scan"] = int(T.pdf_is_image_only(att))
                    row["pages_json"] = json.dumps(T.pdf_pages(att))
                elif ext == "xlsx":
                    row["pages_json"] = json.dumps(T.xlsx_pages(att))
                else:
                    row["status"] = "failed"
                    row["errors"] = f"unsupported attachment type .{ext}"
            except Exception as e:                       # noqa: BLE001 - one bad file must not stop the batch
                row["status"] = "failed"
                row["errors"] = f"unreadable: {type(e).__name__}: {e}"
            row["_bytes"] = att
            rows.append(row)
    return rows
