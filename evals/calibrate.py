"""Calibration check: label every printed item we have ground truth for, then Brier, AUROC and reliability bins.

    python evals/calibrate.py

Ground truth (dev tool only; the harness never reads it):
  - practice mailbox: data/scenarios/answers, after each batch (grader/score.py matching, verdict and amount);
  - worked examples: data/examples/*/expected_finding.json;
  - own eval set: evals/cases/*.yaml (the case key only).
Reports come from the harness run in fresh state folders; extractions come from the dev cache when it is enabled.
"""
from __future__ import annotations

import json
import math
import subprocess
import sys
import tempfile
from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "grader"))
sys.path.insert(0, str(ROOT / "tools"))
import score as S  # noqa: E402

PY = sys.executable
H = str(ROOT / "harness" / "harness.py")


def sh(args):
    return subprocess.run([PY, H] + args, capture_output=True, text=True)


def replay(mailbox: Path, reports: dict, feedback: dict | None = None, mode="supervised") -> dict:
    """Ingest every batch, report after the batches named in `reports` ({batch: as_of}). -> {batch: report}"""
    out = {}
    with tempfile.TemporaryDirectory() as t:
        st = str(Path(t) / "s")
        for b in sorted(p for p in mailbox.glob("batch_*") if p.is_dir()):
            sh(["ingest", str(b), "--state-dir", st])
            if b.name in reports:
                r = sh(["report", "--as-of", reports[b.name], "--mode", mode, "--state-dir", st])
                out[b.name] = json.loads(r.stdout)
            if feedback and b.name in feedback:
                sh(["feedback", str(feedback[b.name]), "--state-dir", st])
    return out


def labelled() -> list[tuple[float, int, str]]:
    rows = []
    # practice
    key = S.load_key(str(ROOT / "data" / "scenarios" / "answers"))
    batches = dict(key["worlds"]["W1"])
    reps = replay(ROOT / "data" / "scenarios", batches,
                  {"batch_01": ROOT / "data" / "scenarios" / "feedback" / "W1_batch_01.json"})
    known = {s["k"]: s for s in key["scenarios"]}
    for b, rep in reps.items():
        for it in S.report_items(rep):
            if it.get("verdict") not in S.PRESENT:
                continue
            s = known.get(S.key_tuple(it))
            e = s["by_batch"].get(b) if s else None
            rows.append((float(it["confidence"]), int(e is not None and S._matches(it, e)), f"practice {b} {it['id']}"))
    # worked examples
    for ex in sorted((ROOT / "data" / "examples").iterdir()):
        f = ex / "expected_finding.json"
        if not f.is_file():
            continue
        expd = json.loads(f.read_text())
        rep = replay(ex / "docs", {sorted(p.name for p in (ex / "docs").glob("batch_*"))[-1]: expd["as_of"]})
        exp = {S.key_tuple(i): i for i in S.report_items(expd)}
        for it in S.report_items(next(iter(rep.values()))):
            if it.get("verdict") in S.PRESENT:
                e = exp.get(S.key_tuple(it))
                rows.append((float(it["confidence"]), int(e is not None and S._matches(it, e)), f"example {it['id']}"))
    # own eval cases (the case key only)
    for cf in sorted((ROOT / "evals" / "cases").glob("*.yaml")):
        c = yaml.safe_load(cf.read_text())
        mb = ROOT / c["mailbox"]
        last = sorted(p.name for p in mb.glob("batch_*"))[-1]
        fb = {k: ROOT / v for k, v in (c.get("feedback") or {}).items()}
        rep = replay(mb, {last: str(c["as_of"])}, fb, c.get("mode", "supervised"))[last]
        want = S.key_tuple(c["expect"]["key"])
        exp = {k: v for k, v in c["expect"].items() if k != "key"}
        for it in S.report_items(rep):
            if S.key_tuple(it) == want and it.get("verdict") in S.PRESENT:
                e = None if exp.get("verdict") == "no_finding" else {"verdict": exp["verdict"],
                                                                     "amount_usd": exp.get("amount_usd"),
                                                                     "amount_range": exp.get("amount_range")}
                rows.append((float(it["confidence"]), int(e is not None and S._matches(it, e)), f"eval {cf.stem}"))
    return rows


def main() -> int:
    rows = labelled()
    conf = [r[0] for r in rows]
    lab = [r[1] for r in rows]
    br = S.brier(conf, lab)
    au = S.auroc(conf, lab)
    print(f"items {len(rows)}, right {sum(lab)}, wrong {len(lab) - sum(lab)}")
    print(f"Brier {br:.4f} (card points {2.5 * max(0, 1 - br / 0.25):.2f}/2.5); "
          f"AUROC {'not measurable (no wrong item)' if au is None else f'{au:.3f}'}")
    print("reliability (confidence bin -> n, observed accuracy):")
    for lo in (0.0, 0.5, 0.7, 0.85, 0.95):
        hi = {0.0: 0.5, 0.5: 0.7, 0.7: 0.85, 0.85: 0.95, 0.95: 1.01}[lo]
        b = [l for c, l in zip(conf, lab) if lo <= c < hi]
        if b:
            print(f"  [{lo:.2f}, {hi:.2f})  n={len(b):3}  accuracy {sum(b) / len(b):.2f}")
    for c, l, name in rows:
        if not l:
            print(f"  WRONG  {c:.3f}  {name}")
    (ROOT / "evals" / "calibration.json").write_text(json.dumps(
        {"items": len(rows), "brier": br, "auroc": au, "rows": [{"confidence": c, "right": l, "item": n}
                                                                for c, l, n in rows]}, indent=1))
    _ = math
    return 0


if __name__ == "__main__":
    sys.exit(main())
