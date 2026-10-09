"""The vendored text layer must give exactly the grader's text, page for page, for every mailbox document."""
from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "harness"))
sys.path.insert(0, str(ROOT / "grader"))

import extract as G  # noqa: E402  grader/extract.py
from nova import textlayer as T  # noqa: E402


def _emls():
    return sorted((ROOT / "data").rglob("*.eml"))


def test_parity_every_document():
    n = 0
    for f in _emls():
        raw = f.read_bytes()
        assert T.pages_of(raw, "eml") == G.pages_of(raw, "eml"), f
        for name, blob in G.attachments(raw):
            ext = name.rsplit(".", 1)[-1].lower()
            if ext in ("pdf", "xlsx"):
                assert T.pages_of(blob, ext) == G.pages_of(blob, ext), f"{f}#{name}"
                n += 1
    assert n > 100


def test_quote_for_is_found_by_grader():
    f = _emls()[0]
    pages = G.pages_of(f.read_bytes(), "eml")
    q = T.quote_for(pages, 1, 1, 3)
    assert q and G.found(pages, 1, q)
