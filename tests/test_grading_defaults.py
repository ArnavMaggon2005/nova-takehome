"""In a grading checkout (no .nova_dev.env, grader's stripped environment) every dev-only switch is inactive.

The harness folder is copied to a temp dir, so the repo's .nova_dev.env is not beside it, and imported in a
subprocess whose environment is what grader/run_grader.py passes: PATH, HOME, TMPDIR and the API key only.
Checks: no spend cap, no ledger, no shared cache, no workspace header, contract model = Opus (no Sonnet override),
and a call is never refused for budget reasons.
"""
from __future__ import annotations

import json
import os
import shutil
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent

PROBE = r"""
import json, sys
sys.path.insert(0, ".")
import config
from nova import spend
from nova.llm import LLM, Budget
from nova.state import State
s = State(sys.argv[1])
llm = LLM(s, Budget(300))
client = llm.client
print(json.dumps({
  "dev_file_loaded": any(k.startswith("NOVA_") for k in __import__("os").environ),
  "cache_dir": config.CACHE_DIR, "ledger": config.SPEND_LEDGER, "limit": config.SPEND_LIMIT_USD,
  "over_limit": spend.over_limit(), "summary": spend.summary_line(),
  "cache_dirs": [str(d) for d in llm._dirs()],
  "workspace_header": "anthropic-workspace-id" in {k.lower() for k in client.default_headers},
  "model_contract": config.MODEL_CONTRACT, "model_doc": config.MODEL_DOC, "threads": config.LLM_THREADS,
}))
"""


def test_dev_switches_are_inactive_in_a_grading_checkout(tmp_path):
    h = tmp_path / "checkout" / "harness"
    shutil.copytree(ROOT / "harness", h, ignore=shutil.ignore_patterns("__pycache__"))
    assert not (h.parent / ".nova_dev.env").exists()
    env = {"PATH": os.environ.get("PATH", ""), "HOME": str(tmp_path / "home"), "TMPDIR": str(tmp_path),
           "ANTHROPIC_API_KEY": "dummy-key-for-this-test"}
    (tmp_path / "home").mkdir()
    r = subprocess.run([sys.executable, "-c", PROBE, str(tmp_path / "state")], cwd=h, env=env,
                       capture_output=True, text=True, timeout=120)
    assert r.returncode == 0, r.stderr
    got = json.loads(r.stdout.strip().splitlines()[-1])
    assert got["dev_file_loaded"] is False
    assert got["cache_dir"] is None and got["ledger"] is None and got["limit"] is None
    assert got["over_limit"] is False and got["summary"] is None
    assert got["cache_dirs"] == [str(tmp_path / "state" / "llm_cache")]
    assert got["workspace_header"] is False
    assert got["model_contract"] == "claude-opus-5-5" and got["model_doc"] == "claude-sonnet-5-5"
    assert got["threads"] == 12


def test_dev_file_is_gitignored():
    r = subprocess.run(["git", "check-ignore", ".nova_dev.env", "local/x", ".nova_cache/x"], cwd=ROOT,
                       capture_output=True, text=True)
    assert r.stdout.split() == [".nova_dev.env", "local/x", ".nova_cache/x"]
