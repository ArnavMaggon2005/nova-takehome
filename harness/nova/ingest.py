"""`harness.py ingest <batch_dir>`: register every document of the batch, then extract inside the step budget."""
from __future__ import annotations

import sys
from pathlib import Path

import config

from .llm import LLM, Budget
from .mailbox import read_batch
from .state import State


def run_ingest(batch_dir: str, state_dir: str) -> dict:
    budget = Budget(config.STEP_BUDGET_S)
    state = State(state_dir)
    added = 0
    for row in read_batch(Path(batch_dir)):
        data = row.pop("_bytes", None)
        if state.has_doc(row["doc_id"], row["sha256"]):
            continue
        if row.get("is_scan") and data is not None:
            (state.dir / "pages" / f"{row['sha256']}.pdf").write_bytes(data)
        state.add_doc(row)
        added += 1
    summary = extract_pending(state, budget, config.INGEST_LAUNCH_FRACTION)
    summary["added"] = added
    state.log("steps.jsonl", {"step": "ingest", "batch": Path(batch_dir).name, "secs": round(budget.elapsed(), 1),
                              **summary})
    print(f"ingest {Path(batch_dir).name}: {summary}", file=sys.stderr)
    return summary


def extract_pending(state: State, budget: Budget, launch_fraction: float) -> dict:
    from .extract import Extractor
    pending = state.pending_docs()
    if not pending:
        return {"extracted": 0, "failed": 0, "pending": 0}
    llm = LLM(state, budget)
    return Extractor(state, llm, budget, launch_fraction).run(pending)
