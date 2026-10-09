"""The extraction cache can never serve a result from another model, an older prompt or another document.

1. The key changes with the model, the prompt version, the document text, the schema and the effort.
2. A cache entry recorded for another model or prompt version is rejected even if its key file is found.
3. Each extraction kind's prompt+schema fingerprint is pinned to its version: editing a prompt without bumping its
   version in harness/nova/prompt_versions.py fails this test (bump the version, then update PINNED below).
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "harness"))

from nova import prompt_versions as PV  # noqa: E402
from nova.llm import LLM, Budget  # noqa: E402
from nova.state import State  # noqa: E402

PINNED = {  # kind -> (version, fingerprint of its prompt text + schema)
    "classify": (1, None), "email": (1, None), "invoice": (1, None), "table": (1, None), "shipping": (1, None),
    "contract": (1, None), "amendment": (1, None), "rate_notice": (1, None), "vision": (1, None),
}
PINNED_FILE = Path(__file__).with_name("prompt_fingerprints.json")


def test_key_depends_on_model_version_content_schema_effort():
    blocks = [{"type": "text", "text": "instructions"}, {"type": "text", "text": "[p1 L1] document text"}]
    base = LLM.cache_key("model-a", "v1", "sys", blocks, {"type": "object"}, "low")
    assert base == LLM.cache_key("model-a", "v1", "sys", blocks, {"type": "object"}, "low")
    assert base != LLM.cache_key("model-b", "v1", "sys", blocks, {"type": "object"}, "low")
    assert base != LLM.cache_key("model-a", "v2", "sys", blocks, {"type": "object"}, "low")
    other_doc = [blocks[0], {"type": "text", "text": "[p1 L1] different text"}]
    assert base != LLM.cache_key("model-a", "v1", "sys", other_doc, {"type": "object"}, "low")
    assert base != LLM.cache_key("model-a", "v1", "sys", blocks, {"type": "array"}, "low")
    assert base != LLM.cache_key("model-a", "v1", "sys", blocks, {"type": "object"}, "medium")


def test_entry_for_other_model_or_version_is_rejected(tmp_path):
    s = State(tmp_path / "s")
    llm = LLM(s, Budget(60))
    blocks = [{"type": "text", "text": "x"}]
    key = LLM.cache_key("m1", PV.version_tag("email"), "sys", blocks, {}, "low")
    (s.dir / "llm_cache" / f"{key}.json").write_text(json.dumps(
        {"data": {"ok": 1}, "requested_model": "m2", "prompt_version": "v1"}))
    called = {}

    def fake_call(*a, **k):
        called["yes"] = True
        return {"fresh": 1}, "m1", {"input": 1, "output": 1, "cache_read": 0, "cache_write": 0}
    llm._call = fake_call
    out = llm.json_call(model="m1", system="sys", blocks=blocks, schema={}, effort="low", max_tokens=10,
                        purpose="email")
    assert called and out == {"fresh": 1}


def test_prompt_changes_require_a_version_bump():
    current = {k: (PV.VERSIONS[k], PV.fingerprint(k)) for k in PV.VERSIONS}
    if not PINNED_FILE.exists():                 # first run writes the pin file; commit it
        PINNED_FILE.write_text(json.dumps(current, indent=1, sort_keys=True))
    pinned = {k: tuple(v) for k, v in json.loads(PINNED_FILE.read_text()).items()}
    for kind, (ver, fp) in current.items():
        pv, pfp = pinned.get(kind, (None, None))
        if pv == ver:
            assert pfp == fp, (f"the {kind} prompt or schema changed but its version is still {ver}: bump "
                               f"VERSIONS['{kind}'] in harness/nova/prompt_versions.py and re-pin")
    assert set(PINNED) == set(PV.VERSIONS)
