"""Run every worked example (data/examples/<name>/docs) through the harness and diff against expected_finding.json.

    python tools/check_examples.py [-k name] [--mode supervised|autonomous] [--keep]

Each example gets a fresh state folder under out/state_examples/<name>; every batch is ingested, then one report on
the expected file's as_of. For each expected item: verdict, amount (within $0.01) or range, action, and whether a
quote on a cited page resolves. Expected no_finding items must be absent or no_finding; any other present item is
reported as extra. This tool reads the expected files; the harness never does.
"""
from __future__ import annotations

import argparse
import json
import shutil
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "grader"))
import score as S  # noqa: E402
from extract import Mailbox  # noqa: E402


def run_example(ex: Path, mode: str, keep: bool) -> tuple[dict | None, str]:
    state = ROOT / "out" / "state_examples" / ex.name
    if state.exists() and not keep:
        shutil.rmtree(state)
    expected = json.loads((ex / "expected_finding.json").read_text())
    log = []
    for b in sorted((ex / "docs").glob("batch_*")):
        r = subprocess.run([sys.executable, str(ROOT / "harness" / "harness.py"), "ingest", str(b), "--state-dir",
                            str(state)], capture_output=True, text=True)
        log.append(r.stderr.strip().splitlines()[-2:] if r.stderr else [])
        if r.returncode:
            return None, f"ingest {b.name} failed: {r.stderr[-400:]}"
    r = subprocess.run([sys.executable, str(ROOT / "harness" / "harness.py"), "report", "--as-of", expected["as_of"],
                        "--mode", mode, "--state-dir", str(state)], capture_output=True, text=True)
    if r.returncode:
        return None, f"report failed: {r.stderr[-400:]}"
    tail = [l for l in r.stderr.splitlines() if "spend" in l or "WARNING" in l or "Error" in l]
    return json.loads(r.stdout), "; ".join(tail[-3:])


def compare(ex: Path, report: dict, mode: str) -> list[str]:
    expected = json.loads((ex / "expected_finding.json").read_text())
    exp = {S.key_tuple(it): it for it in S.report_items(expected)}
    got = {S.key_tuple(it): it for it in S.report_items(report)}
    mb = Mailbox(ex / "docs")
    out = []
    for k, e in exp.items():
        g = got.get(k)
        if e["verdict"] == "no_finding":
            if g is not None and g.get("verdict") != "no_finding":
                out.append(f"DECOY FLAGGED {S.key_str(k)}: {g.get('verdict')} {g.get('amount_usd')}")
            continue
        if g is None:
            out.append(f"MISSED {S.key_str(k)}: expected {e['verdict']} {e.get('amount_usd') or e.get('amount_range')}")
            continue
        if g.get("verdict") != e["verdict"]:
            out.append(f"VERDICT {S.key_str(k)}: {g.get('verdict')} (expected {e['verdict']})")
        if e.get("amount_usd") and not S.amount_ok(g.get("amount_usd"), e["amount_usd"]):
            out.append(f"AMOUNT {S.key_str(k)}: {g.get('amount_usd')} (expected {e['amount_usd']})")
        if e.get("amount_range") and not S.range_ok(g.get("amount_range"), e["amount_range"]):
            out.append(f"RANGE {S.key_str(k)}: {g.get('amount_range')} (expected {e['amount_range']})")
        want_action = e.get("action") if mode == "supervised" else None
        if want_action and g.get("action") != want_action:
            out.append(f"ACTION {S.key_str(k)}: {g.get('action')} (expected {want_action})")
        req = [x["doc"] for x in e.get("evidence") or []]
        good = [ev for ev in g.get("evidence") or [] if mb.check(ev["doc"], ev["page"], ev["quote"]) is None
                and any(S.same_doc(r, ev["doc"]) for r in req)]
        if not good:
            out.append(f"EVIDENCE {S.key_str(k)}: no quote on a required document resolves")
    for k, g in got.items():
        if k not in exp and g.get("verdict") in S.PRESENT:
            out.append(f"EXTRA {S.key_str(k)}: {g.get('verdict')} {g.get('amount_usd') or g.get('amount_range')}")
    return out


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(prog="check_examples.py")
    ap.add_argument("-k", help="only examples whose name contains this")
    ap.add_argument("--mode", default="supervised", choices=["supervised", "autonomous"])
    ap.add_argument("--keep", action="store_true", help="reuse existing state folders (no re-ingest of done docs)")
    a = ap.parse_args(argv)
    exs = sorted(p for p in (ROOT / "data" / "examples").iterdir() if (p / "expected_finding.json").is_file())
    if a.k:
        exs = [e for e in exs if a.k in e.name]
    bad = 0
    for ex in exs:
        report, note = run_example(ex, a.mode, a.keep)
        diffs = [note] if report is None else compare(ex, report, a.mode)
        bad += bool(diffs)
        print(f"{'PASS' if not diffs else 'FAIL'}  {ex.name}" + (f"   [{note}]" if note and report else ""))
        for d in diffs:
            print(f"      - {d}")
    print(f"\n{len(exs) - bad} of {len(exs)} examples match")
    return 1 if bad else 0


if __name__ == "__main__":
    sys.exit(main())
