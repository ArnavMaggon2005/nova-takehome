"""Scanned PDFs (no text layer): render each page, read it with local OCR, rebuild text lines from box positions.

rapidocr returns boxes with positions and drops most spaces inside a box; boxes are grouped into lines by vertical
centre and joined left to right with two spaces. The result becomes the document's text layer (method "ocr").
extract.py checks that the line items add up to the printed total and, when they don't, re-reads the page with
Claude vision (method "vision"). The grader checks only the page number of a scan's citation, never its text.
"""
from __future__ import annotations

import threading

import config

_engine = None
_lock = threading.Lock()


def render_pages(pdf: bytes, dpi: int = config.OCR_RENDER_DPI) -> list[bytes]:
    import pymupdf
    with pymupdf.open(stream=pdf, filetype="pdf") as doc:
        return [p.get_pixmap(dpi=dpi).tobytes("png") for p in doc]


def _ocr_engine():
    global _engine
    if _engine is None:
        from rapidocr_onnxruntime import RapidOCR
        _engine = RapidOCR()
    return _engine


def ocr_png(png: bytes) -> tuple[str, float]:
    """-> (text with one OCR line per row, mean box confidence)."""
    with _lock:
        result, _ = _ocr_engine()(png)
    boxes = []
    for box, text, conf in result or []:
        ys = [p[1] for p in box]
        xs = [p[0] for p in box]
        boxes.append(((min(ys) + max(ys)) / 2, min(xs), max(ys) - min(ys), str(text), float(conf)))
    boxes.sort()
    lines: list[list] = []
    for y, x, h, t, c in boxes:
        if lines and abs(lines[-1][0] - y) <= max(6.0, 0.45 * h):
            lines[-1][1].append((x, t, c))
        else:
            lines.append([y, [(x, t, c)]])
    text = "\n".join("  ".join(t for _, t, _ in sorted(ws)) for _, ws in lines)
    confs = [c for *_, c in boxes]
    return text, (sum(confs) / len(confs) if confs else 0.0)


def ocr_pdf(pdf: bytes) -> tuple[list[str], list[bytes], float]:
    """-> (pages of text, page PNGs, mean confidence)."""
    pngs = render_pages(pdf)
    pages, confs = [], []
    for png in pngs:
        t, c = ocr_png(png)
        pages.append(t)
        confs.append(c)
    return pages, pngs, (sum(confs) / len(confs) if confs else 0.0)
