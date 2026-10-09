"""Run your eval cases (evals/cases/*.yaml) through your harness and score them. Behind `make eval`.

    python evals/run_evals.py [--harness harness/harness.py] [--cases evals/cases] [--out evals/results.json] [-k name]

Each case gets a fresh state folder: every batch_* of its mailbox is ingested in order (with a feedback file after
the batch it names, if the case has one), then one report on the case's date and mode. The item with the case's key
is compared with `expect`, using the grader's own matching (grader/score.py): verdict, amount within USD 0.01, the
range for a conflict, the action, and the missing document's name for cannot_determine. `verdict: no_finding` passes
when the key is missing or listed as no_finding. Exit code 0 when every case passes.
"""
from __future__ import annotations

import argparse
import json
import sys
import tempfile
from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "grader"))
sys.path.insert(0, str(ROOT / "tools"))
import score as S  # noqa: E402
from run_mailbox import run  # noqa: E402


def find_item(report: dict, key: dict) -> dict | None:
    want = S.key_tuple(key)
    for it in S.report_items(report):
        if S.key_tuple(it) == want:
            return it
    return None


def check(case: dict, item: dict | None) -> list[str]:
    """-> what differs (empty when the case passes)."""
    exp = case["expect"]
    v = exp.get("verdict", "finding")
    if v == "no_finding":
        return [] if item is None or item.get("verdict") == "no_finding" else \
            [f"expected no finding, got {item.get('verdict')} {item.get('amount_usd') or ''}".strip()]
    if item is None:
        return ["key missing from the report"]
    bad = []
    if item.get("verdict") != v:
        bad.append(f"verdict {item.get('verdict')}, expected {v}")
    if "amount_usd" in exp and exp["amount_usd"] is not None and not S.amount_ok(item.get("amount_usd"), exp["amount_usd"]):
        bad.append(f"amount {item.get('amount_usd')}, expected {exp['amount_usd']}")
    if exp.get("amount_range") and not S.range_ok(item.get("amount_range"), exp["amount_range"]):
        bad.append(f"range {item.get('amount_range')}, expected {exp['amount_range']}")
    if exp.get("action") and str(item.get("action")) != exp["action"]:
        bad.append(f"action {item.get('action')}, expected {exp['action']}")
    if exp.get("deadline") and str(item.get("deadline")) != str(exp["deadline"]):
        bad.append(f"deadline {item.get('deadline')}, expected {exp['deadline']}")
    want_doc = (exp.get("missing_doc") or {}).get("name") if isinstance(exp.get("missing_doc"), dict) else exp.get("missing_doc")
    if want_doc:
        got = ((item.get("missing_doc") or {}).get("name") or "").lower()
        if not all(w in got for w in str(want_doc).lower().split()):
            bad.append(f"missing_doc {got or 'none'}, expected {want_doc}")
    # optional checks added for this eval set (absent in the shipped samples, so they are unaffected)
    if exp.get("retro") and item.get("retro") is not True:
        bad.append("expected retro: true")
    if exp.get("supersedes") and not item.get("supersedes"):
        bad.append("expected a non-empty supersedes")
    if exp.get("learned_at") and not (item.get("learned_at") or {}).get("feedback_item_id"):
        bad.append("expected learned_at with a feedback_item_id")
    return bad


def check_report(case: dict, report: dict) -> list[str]:
    """Whole-report checks: strings that must not appear anywhere (e.g. an address an injected email asked for)."""
    blob = json.dumps(report).lower()
    return [f"report contains {s!r}" for s in case["expect"].get("report_must_not_contain") or [] if s.lower() in blob]


def run_with_interim(harness: str, mailbox: Path, case: dict, state: Path, timeout: float, fb: dict):
    """Like tools/run_mailbox.run, plus a report after each batch named in `interim_reports` (so a later batch can
    produce supersedes / retro). Same fresh-process-per-step behaviour."""
    from run_mailbox import harness_cmd, step
    cmd = harness_cmd(harness)
    state.mkdir(parents=True, exist_ok=True)
    interim = {str(k): str(v) for k, v in (case.get("interim_reports") or {}).items()}
    errors = []
    for b in sorted(p for p in mailbox.glob("batch_*") if p.is_dir()):
        rc, _, err = step(cmd, ["ingest", str(b), "--state-dir", str(state)], timeout)
        if rc:
            errors.append(f"ingest {b.name} exited {rc}: {err.strip()[-300:]}")
        if b.name in interim:
            step(cmd, ["report", "--as-of", interim[b.name], "--mode", case.get("mode", "supervised"), "--state-dir",
                       str(state)], timeout)
        if b.name in fb:
            step(cmd, ["feedback", str(fb[b.name]), "--state-dir", str(state)], timeout)
    rc, out, err = step(cmd, ["report", "--as-of", str(case["as_of"]), "--mode", case.get("mode", "supervised"),
                              "--state-dir", str(state)], timeout)
    if rc:
        return None, errors + [f"report exited {rc}: {err.strip()[-300:]}"]
    return json.loads(out), errors


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(prog="run_evals.py", description="score your eval cases")
    ap.add_argument("--harness", default="harness/harness.py")
    ap.add_argument("--cases", default=str(ROOT / "evals" / "cases"))
    ap.add_argument("--out", default=str(ROOT / "evals" / "results.json"))
    ap.add_argument("-k", help="only cases whose file name contains this")
    ap.add_argument("--timeout", type=float, default=600.0)
    a = ap.parse_args(argv)
    files = sorted(Path(a.cases).glob("*.yaml"))
    if a.k:
        files = [f for f in files if a.k in f.name]
    if not files:
        print(f"no cases in {a.cases}", file=sys.stderr)
        return 2
    results = []
    for f in files:
        case = yaml.safe_load(f.read_text())
        mailbox = (ROOT / case["mailbox"]) if not Path(case["mailbox"]).is_absolute() else Path(case["mailbox"])
        fb = {k: (ROOT / v) for k, v in (case.get("feedback") or {}).items()}   # {batch_02: path/to/feedback.json}
        with tempfile.TemporaryDirectory(prefix="eval-") as tmp:
            if case.get("interim_reports"):
                report, errors = run_with_interim(a.harness, mailbox, case, Path(tmp) / "state", a.timeout, fb)
            else:
                report, errors = run(a.harness, mailbox, str(case["as_of"]), case.get("mode", "supervised"),
                                     Path(tmp) / "state", a.timeout, fb, log=lambda *_: None)
        diff = errors if report is None else \
            check(case, find_item(report, case["expect"]["key"])) + check_report(case, report)
        ok = not diff
        results.append({"case": f.name, "name": case.get("name"), "pass": ok, "diff": diff})
        print(f"{'PASS' if ok else 'FAIL'}  {f.name}: {case.get('name', '')}" + ("" if ok else f"\n      {'; '.join(diff)[:400]}"))
    n = sum(r["pass"] for r in results)
    ours = sum(1 for r in results if r["case"].startswith("sample_"))
    summary = {"harness": a.harness, "passed": n, "total": len(results), "your_cases": len(results) - ours,
               "score": round(n / len(results), 4), "cases": results}
    if not a.k:                                  # a filtered run never overwrites the full results
        Path(a.out).write_text(json.dumps(summary, indent=1) + "\n")
    print(f"\n{n} of {len(results)} cases pass ({len(results) - ours} of them yours)" + ("" if a.k else f"; wrote {a.out}"))
    return 0 if n == len(results) else 1


if __name__ == "__main__":
    sys.exit(main())
