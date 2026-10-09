"""Developer spend ledger: cumulative API cost from each response's token counts (dev only).

Active only when NOVA_SPEND_LEDGER names a file; the grading container never sets it. NOVA_SPEND_LIMIT (USD) makes
the client refuse to start a call once the ledger total has reached the limit. The key is never written anywhere.
"""
from __future__ import annotations

import fcntl
import json
import time
from pathlib import Path

import config


def cost_usd(model: str, usage: dict) -> float:
    p = config.PRICES.get(model) or next((v for k, v in config.PRICES.items() if model.startswith(k)),
                                         config.PRICES["default"])
    return (usage.get("input", 0) * p["in"] + usage.get("cache_write", 0) * p["in"] * 1.25 +
            usage.get("cache_read", 0) * p["read"] + usage.get("output", 0) * p["out"]) / 1_000_000


def _path() -> Path | None:
    return Path(config.SPEND_LEDGER) if config.SPEND_LEDGER else None


def record(model: str, usage: dict, purpose: str) -> float:
    """Add one call to the ledger; returns the new cumulative total (0 when no ledger is configured)."""
    p = _path()
    if p is None:
        return 0.0
    p.parent.mkdir(parents=True, exist_ok=True)
    c = cost_usd(model, usage)
    with open(p.with_suffix(".lock"), "w") as lock:
        fcntl.flock(lock, fcntl.LOCK_EX)
        try:
            data = json.loads(p.read_text()) if p.is_file() else {}
        except json.JSONDecodeError:
            data = {}
        data["total_usd"] = round(data.get("total_usd", 0.0) + c, 6)
        data["calls"] = data.get("calls", 0) + 1
        for k, v in usage.items():
            data.setdefault("tokens", {})[k] = data.get("tokens", {}).get(k, 0) + v
        bm = data.setdefault("by_model", {})
        bm[model] = round(bm.get(model, 0.0) + c, 6)
        bp = data.setdefault("by_purpose", {})
        bp[purpose] = round(bp.get(purpose, 0.0) + c, 6)
        data["updated"] = time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())
        tmp = p.with_suffix(".tmp")
        tmp.write_text(json.dumps(data, indent=1))
        tmp.replace(p)
        fcntl.flock(lock, fcntl.LOCK_UN)
    return data["total_usd"]


def total() -> float:
    p = _path()
    if p is None or not p.is_file():
        return 0.0
    try:
        return float(json.loads(p.read_text()).get("total_usd", 0.0))
    except (json.JSONDecodeError, ValueError):
        return 0.0


def over_limit() -> bool:
    return bool(config.SPEND_LIMIT_USD) and total() >= config.SPEND_LIMIT_USD


def summary_line() -> str | None:
    if _path() is None:
        return None
    return f"API spend so far: ${total():.4f}" + (f" (stop at ${config.SPEND_LIMIT_USD:.2f})"
                                                  if config.SPEND_LIMIT_USD else "")
