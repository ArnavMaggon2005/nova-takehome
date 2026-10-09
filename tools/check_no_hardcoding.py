"""Fail if anything specific to the mailboxes in data/ appears in harness/ (run by `make eval`).

Collected from data/ (every email, attachment text layer, answer and feedback file): invoice/statement/credit-note
numbers, contract numbers, party codes, waybill numbers, lane codes, and person/company names (email display names,
Schedule 1 entries, signatories). Also fails if harness/ refers to the answer key, the worked examples' expected
output, or local/.

    python tools/check_no_hardcoding.py [--data data] [--harness harness] [--show-tokens]
"""
from __future__ import annotations

import argparse
import re
import sys
from email.utils import parseaddr
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "grader"))
from extract import attachments, email_lines, pages_of, parse_eml  # noqa: E402

ID_RE = re.compile(r"\b[A-Z]{2,5}(?:[-/][A-Z0-9]{1,6}){1,4}\b")          # CDU-3051254, TXI/35-36/0021, TBX-US-EXP-01
AWB_RE = re.compile(r"\b[A-Z]{2}\d{8}(?:-H\d+)?\b")
LANE_RE = re.compile(r"\b[A-Z]{3}\d-[A-Z]{3}\d\b")
SCHED_RE = re.compile(r"^([A-Z][a-z]+(?: [A-Z][a-z'\-]+)+), [^,]+, ([A-Z]{2,5}-[A-Z]{2,3}):", re.M)
SIGN_RE = re.compile(r"^Name: ([A-Z][a-z]+(?: [A-Z][a-z'\-]+)+)\s*$", re.M)
SIGNOFF_RE = re.compile(r"^([A-Z][a-z]+ [A-Z][a-z'\-]+) \| ", re.M)
COMPANY_RE = re.compile(r"\b([A-Z][a-z]{3,}) (?:Express|Pharma|Air Logistics|Life Sciences|Clearing)\b")
FORBIDDEN_PATHS = ["data/scenarios/answers", "/answers/", "expected_finding", "local/", "exam_oracle"]
GENERIC = {"PICKED_UP", "USD", "INR"}


def has_digit(s: str) -> bool:
    return any(c.isdigit() for c in s)


def collect(data: Path) -> dict[str, set[str]]:
    toks: dict[str, set[str]] = {"id": set(), "awb": set(), "lane": set(), "name": set()}

    def scan(text: str):
        for m in ID_RE.findall(text):
            if has_digit(m) or m.count("-") >= 1 and len(m) >= 6 and m.isupper():
                if m not in GENERIC and len(m) >= 6:
                    toks["id"].add(m)
        toks["awb"].update(AWB_RE.findall(text))
        toks["lane"].update(LANE_RE.findall(text))
        for name, party in SCHED_RE.findall(text):
            toks["name"].add(name)
            toks["id"].add(party)
        toks["name"].update(SIGN_RE.findall(text))
        toks["name"].update(SIGNOFF_RE.findall(text))
        toks["name"].update(COMPANY_RE.findall(text))

    for f in sorted(data.rglob("*.eml")):
        raw = f.read_bytes()
        msg = parse_eml(raw)
        for h in ("From", "To", "Cc"):
            name, _ = parseaddr(str(msg[h] or ""))
            if name and " " in name:
                toks["name"].add(name)
        scan("\n".join(email_lines(msg)))
        for att, blob in attachments(raw):
            ext = att.rsplit(".", 1)[-1].lower()
            if ext in ("pdf", "xlsx"):
                try:
                    scan("\n".join(pages_of(blob, ext)))
                except Exception:                     # noqa: BLE001
                    pass
    for f in list(data.rglob("*.yaml")) + list(data.rglob("*.json")) + list(data.rglob("*.md")):
        text = f.read_text(errors="ignore")
        scan(text)
        for m in re.findall(r'"(?:name|person|sent_by)":\s*"([^"]+)"', text):
            if " " in m:
                toks["name"].add(m)
    toks["id"] = {t for t in toks["id"] if t not in toks["lane"]}
    return toks


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(prog="check_no_hardcoding.py")
    ap.add_argument("--data", default=str(ROOT / "data"))
    ap.add_argument("--harness", default=str(ROOT / "harness"))
    ap.add_argument("--show-tokens", action="store_true")
    a = ap.parse_args(argv)
    toks = collect(Path(a.data))
    files = [p for p in Path(a.harness).rglob("*") if p.is_file() and p.suffix in (".py", ".md", ".txt", ".json",
                                                                                  ".yaml", ".toml", ".cfg")]
    bad = []
    for p in files:
        text = p.read_text(errors="ignore")
        for kind in ("id", "awb", "lane"):
            for t in toks[kind]:
                if re.search(r"(?<![A-Za-z0-9])" + re.escape(t) + r"(?![A-Za-z0-9])", text):
                    bad.append(f"{p.relative_to(ROOT)}: {kind} {t!r}")
        low = text.lower()
        for n in toks["name"]:
            if re.search(r"\b" + re.escape(n.lower()) + r"\b", low):
                bad.append(f"{p.relative_to(ROOT)}: name {n!r}")
        for path in FORBIDDEN_PATHS:
            if path in text:
                bad.append(f"{p.relative_to(ROOT)}: refers to {path!r}")
    n = {k: len(v) for k, v in toks.items()}
    if a.show_tokens:
        for k, v in toks.items():
            print(k, sorted(v)[:40], "..." if len(v) > 40 else "")
    if bad:
        print(f"✗ hardcoding check: {len(bad)} hit(s) in {a.harness} (collected {n} from {a.data})")
        for b in sorted(set(bad))[:60]:
            print("  -", b)
        return 1
    print(f"✓ hardcoding check: no data-specific token in {len(files)} harness file(s) (checked {n})")
    return 0


if __name__ == "__main__":
    sys.exit(main())
