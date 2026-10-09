"""Time budget carry-over, failure isolation, refusal fallback and a report that never crashes (no model calls)."""
from __future__ import annotations

import json
import sys
import time
from pathlib import Path

import jsonschema

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "harness"))

import config  # noqa: E402
from nova import extract as X  # noqa: E402
from nova.llm import LLM, Budget, _Refused  # noqa: E402
from nova.mailbox import read_batch  # noqa: E402
from nova.state import State  # noqa: E402

SCHEMA = json.loads((ROOT / "grader" / "schema" / "report.schema.json").read_text())


def _state_with_docs(tmp_path) -> State:
    s = State(tmp_path / "state")
    for row in read_batch(ROOT / "evals" / "mailboxes" / "a_waivers" / "batch_01"):
        row.pop("_bytes", None)
        s.add_doc(row)
    return s


def test_budget_leaves_unstarted_documents_pending_and_the_next_step_finishes_them(tmp_path, monkeypatch):
    s = _state_with_docs(tmp_path)
    n = len(s.pending_docs())

    def slow(self, doc):
        time.sleep(0.4)
        return {"status": "extracted", "doc_type": "other", "extract_json": json.dumps({"type": "other", "data": None})}
    monkeypatch.setattr(X.Extractor, "process", slow)
    monkeypatch.setattr(config, "LLM_THREADS", 1)
    b = Budget(1.0)
    r1 = X.Extractor(s, LLM(s, b), b, 0.5).run(s.pending_docs())
    assert r1["pending"] > 0 and r1["extracted"] < n                 # stopped launching at 50% of the budget
    b2 = Budget(60)
    r2 = X.Extractor(s, LLM(s, b2), b2, 0.9).run(s.pending_docs())
    assert r2["extracted"] == r1["pending"] and not s.pending_docs()  # carried over, nothing silently skipped


def test_one_failing_document_does_not_stop_the_others(tmp_path, monkeypatch):
    s = _state_with_docs(tmp_path)
    bad = s.pending_docs()[0]["doc_id"]

    def flaky(self, doc):
        if doc["doc_id"] == bad:
            raise RuntimeError("unreadable reply")
        return {"status": "extracted", "doc_type": "other", "extract_json": json.dumps({"type": "other", "data": None})}
    monkeypatch.setattr(X.Extractor, "process", flaky)
    for _ in range(2):                                                # ingest, then report: two attempts
        b = Budget(60)
        X.Extractor(s, LLM(s, b), b, 0.9).run(s.pending_docs())
    statuses = {d["doc_id"]: d["status"] for d in s.docs()}
    assert statuses[bad] == "failed" and all(v == "extracted" for k, v in statuses.items() if k != bad)


def test_refusal_retries_on_the_other_model(tmp_path, monkeypatch):
    monkeypatch.setattr(config, "MODEL_CONTRACT", "model-strong")
    monkeypatch.setattr(config, "MODEL_DOC", "model-routine")
    s = State(tmp_path / "s")
    llm = LLM(s, Budget(60))
    seen = []

    def fake(model, *a, **k):
        seen.append(model)
        if len(seen) == 1:
            raise _Refused()
        return {"ok": True}, model, {"input": 1, "output": 1, "cache_read": 0, "cache_write": 0}
    llm._call = fake
    out = llm.json_call(model=config.MODEL_CONTRACT, system="s", blocks=[{"type": "text", "text": "x"}], schema={},
                        effort="low", max_tokens=10, purpose="amendment")
    assert out == {"ok": True} and seen == [config.MODEL_CONTRACT, config.MODEL_DOC]


def test_report_is_always_schema_valid(tmp_path, monkeypatch):
    from nova import evaluate
    from nova.report import run_report
    monkeypatch.setattr(evaluate, "extract_pending", lambda *a, **k: {"stubbed": True})   # tests never call the API
    s = _state_with_docs(tmp_path)
    s.update_doc(s.docs()[0]["doc_id"], status="extracted", doc_type="msa", extract_json="{not json")
    rep = run_report("2041-08-31", "supervised", str(s.dir))
    jsonschema.validate(rep, SCHEMA)
    rep = run_report("2041-08-31", "autonomous", str(tmp_path / "empty_state"))
    jsonschema.validate(rep, SCHEMA)
