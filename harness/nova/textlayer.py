"""The grader's text layer, vendored so evidence quotes match what grader/extract.py checks.

The reading functions below are copied from grader/extract.py without behavioural change (tests/test_textlayer.py
asserts identical output on every mailbox document). The harness never imports from grader/ at runtime: the grading
container is free to lay files out differently, and the harness must depend only on its own folder.
"""
from __future__ import annotations

import io
import re
from datetime import date, datetime
from decimal import Decimal
from email import policy
from email.parser import BytesParser
from email.utils import parseaddr, parsedate_to_datetime

SEP = " | "


def norm(s: str) -> str:
    return " ".join(s.split())


# ---- PDF (copied from grader/extract.py) -----------------------------------------------------------------------------
def _reading_order(page) -> str:
    words = page.get_text("words")
    words.sort(key=lambda w: ((w[1] + w[3]) / 2, w[0]))
    lines: list[list] = []
    for w in words:
        mid = (w[1] + w[3]) / 2
        if lines and abs(lines[-1][0] - mid) <= 2.5:
            lines[-1][1].append(w)
        else:
            lines.append([mid, [w]])
    return "\n".join(" ".join(x[4] for x in sorted(ws, key=lambda w: w[0])) for _, ws in lines)


def pdf_pages(data: bytes) -> list[str]:
    import pymupdf
    with pymupdf.open(stream=data, filetype="pdf") as doc:
        return [_reading_order(p) for p in doc]


def pdf_is_image_only(data: bytes) -> bool:
    import pymupdf
    with pymupdf.open(stream=data, filetype="pdf") as doc:
        return all(not p.get_text().strip() for p in doc)


# ---- XLSX (copied from grader/extract.py) ----------------------------------------------------------------------------
def _cell_text(cell) -> str:
    v = cell.value
    if v is None:
        return ""
    fmt = cell.number_format or "General"
    prefix = ""
    m = re.match(r'^"([^"]*)"(.*)$', fmt)
    if m:
        prefix, fmt = m.group(1), m.group(2)
    if isinstance(v, datetime):
        return prefix + v.date().isoformat()
    if isinstance(v, date):
        return prefix + v.isoformat()
    if isinstance(v, (int, float, Decimal)) and not isinstance(v, bool):
        dp = len(fmt.split(".")[1]) if "." in fmt else 0
        return prefix + f"{Decimal(str(v)):.{dp}f}"
    return prefix + str(v)


def xlsx_pages(data: bytes) -> list[str]:
    import openpyxl
    wb = openpyxl.load_workbook(io.BytesIO(data), data_only=True)
    pages = []
    for ws in wb.worksheets:
        rows = []
        for row in ws.iter_rows():
            cells = [t for t in (_cell_text(c) for c in row) if t != ""]
            if cells:
                rows.append(SEP.join(cells))
        pages.append("\n".join(rows))
    return pages


# ---- email (copied from grader/extract.py) ---------------------------------------------------------------------------
def parse_eml(data: bytes):
    return BytesParser(policy=policy.default).parsebytes(data)


def email_lines(msg) -> list[str]:
    name, addr = parseaddr(str(msg["From"]))
    out = [f"From: {name} <{addr}>", f"To: {msg['To']}"]
    if msg["Cc"]:
        out.append(f"Cc: {msg['Cc']}")
    dt = parsedate_to_datetime(str(msg["Date"]))
    out += [f"Date: {dt.strftime('%Y-%m-%dT%H:%M:%SZ')}", f"Subject: {msg['Subject']}", ""]
    body = msg.get_body(preferencelist=("plain",))
    out += body.get_content().replace("\r\n", "\n").rstrip("\n").split("\n") if body else []
    names = [p.get_filename() for p in msg.iter_attachments()]
    if names:
        out.append("Attachments: " + ", ".join(names))
    return out


def attachments(data: bytes) -> list[tuple[str, bytes]]:
    return [(p.get_filename() or "", p.get_content()) for p in parse_eml(data).iter_attachments()]


def pages_of(data: bytes, ext: str) -> list[str]:
    ext = ext.lower().lstrip(".")
    if ext == "pdf":
        return pdf_pages(data)
    if ext == "xlsx":
        return xlsx_pages(data)
    if ext == "eml":
        return ["\n".join(email_lines(parse_eml(data)))]
    raise ValueError(f"can't read .{ext} files")


def found(pages: list[str], page: int, quote: str) -> bool:
    return 1 <= page <= len(pages) and norm(quote) in norm(pages[page - 1])


# ---- harness additions ------------------------------------------------------------------------------------------------
def page_lines(pages: list[str]) -> list[list[str]]:
    return [p.split("\n") for p in pages]


def render_numbered(pages: list[str], max_lines_per_page: int | None = None) -> str:
    """Pages with stable line references, e.g. "[p2 L14] 3.2 Pricing date ...". Lines count from 1 on each page."""
    out = []
    for pi, text in enumerate(pages, 1):
        lines = text.split("\n")
        out.append(f"=== page {pi} of {len(pages)} ({len(lines)} lines) ===")
        for li, line in enumerate(lines[:max_lines_per_page] if max_lines_per_page else lines, 1):
            out.append(f"[p{pi} L{li}] {line}")
        if max_lines_per_page and len(lines) > max_lines_per_page:
            out.append(f"... ({len(lines) - max_lines_per_page} more lines on this page not shown)")
    return "\n".join(out)


def quote_for(pages: list[str], page: int, line_from: int, line_to: int | None = None) -> str:
    """The exact text of lines [line_from, line_to] (1-based, inclusive) joined by spaces: passes `found()`."""
    if not (1 <= page <= len(pages)):
        return ""
    lines = pages[page - 1].split("\n")
    line_to = line_to or line_from
    lo, hi = max(1, line_from), min(len(lines), line_to)
    if lo > hi:
        return ""
    return " ".join(lines[lo - 1:hi]).strip()
