"""`harness.py report --as-of D --mode M`: recompute every finding key from the documents received by D."""
from __future__ import annotations

import sys
import traceback


def empty_report(as_of: str, mode: str) -> dict:
    return {"schema_version": "1.0", "as_of": as_of, "mode": mode, "findings": [],
            "portfolio": {"cashback": [], "expiry": [], "late_fee_risk": []}}


def run_report(as_of: str, mode: str, state_dir: str) -> dict:
    try:
        from .evaluate import build_report
        return build_report(as_of, mode, state_dir)
    except ImportError:
        return empty_report(as_of, mode)
    except Exception:                                   # noqa: BLE001 - a report must always be printed
        traceback.print_exc(file=sys.stderr)
        return empty_report(as_of, mode)
