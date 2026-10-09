"""Tests never touch the developer's shared extraction cache, spend ledger or spend cap (set by .nova_dev.env)."""
from __future__ import annotations

import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "harness"))

import config  # noqa: E402


@pytest.fixture(autouse=True)
def _no_dev_cache_or_ledger(monkeypatch):
    monkeypatch.setattr(config, "CACHE_DIR", None)
    monkeypatch.setattr(config, "SPEND_LEDGER", None)
    monkeypatch.setattr(config, "SPEND_LIMIT_USD", None)
