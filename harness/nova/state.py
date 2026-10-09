"""Everything the harness remembers lives under --state-dir (docs/PLAN.md section 2c).

state.db (SQLite) holds one row per document (with its text layer and extraction), the feedback items and the report
snapshots. llm_cache/ holds raw model responses keyed by request hash, outbox/ the drafted or executed actions, logs/
the usage log. Facts are never derived and stored back: every report recomputes from the documents' extractions.
"""
from __future__ import annotations

import json
import sqlite3
import threading
from pathlib import Path

SCHEMA = """
CREATE TABLE IF NOT EXISTS documents (
  doc_id TEXT PRIMARY KEY,          -- grader format: batch_01/0014.eml or batch_01/0014.eml#INV-1.pdf
  batch TEXT, eml TEXT, attachment TEXT, ext TEXT, sha256 TEXT,
  received_at TEXT,                 -- ISO UTC from the carrying email's Date header
  sender_name TEXT, sender_addr TEXT, to_addrs TEXT, subject TEXT,
  is_scan INTEGER DEFAULT 0,
  pages_json TEXT,                  -- text layer (vendored grader reader; OCR/vision lines for scans)
  status TEXT DEFAULT 'new',        -- new | classified | extracted | failed
  doc_type TEXT, classify_json TEXT, extract_json TEXT, method TEXT, errors TEXT,
  attempts INTEGER DEFAULT 0, seq INTEGER
);
CREATE TABLE IF NOT EXISTS feedback_items (
  item_id TEXT PRIMARY KEY, file TEXT, after_batch TEXT, decided_at TEXT, raw_json TEXT, seq INTEGER
);
CREATE TABLE IF NOT EXISTS snapshots (
  mode TEXT, as_of TEXT, json TEXT, PRIMARY KEY (mode, as_of)
);
"""


class State:
    def __init__(self, state_dir: str | Path):
        self.dir = Path(state_dir)
        self.dir.mkdir(parents=True, exist_ok=True)
        for sub in ("llm_cache", "outbox", "logs", "feedback", "pages"):
            (self.dir / sub).mkdir(exist_ok=True)
        self._lock = threading.Lock()
        self.db = sqlite3.connect(self.dir / "state.db", check_same_thread=False, timeout=60)
        self.db.row_factory = sqlite3.Row
        self.db.execute("PRAGMA journal_mode=WAL")
        self.db.executescript(SCHEMA)
        self.db.commit()

    # ---- documents ---------------------------------------------------------------------------------------------------
    def has_doc(self, doc_id: str, sha256: str) -> bool:
        r = self.db.execute("SELECT sha256 FROM documents WHERE doc_id=?", (doc_id,)).fetchone()
        return r is not None and r["sha256"] == sha256

    def add_doc(self, row: dict) -> None:
        with self._lock:
            seq = self.db.execute("SELECT COALESCE(MAX(seq), 0) + 1 FROM documents").fetchone()[0]
            row = {**row, "seq": seq}
            cols = ",".join(row)
            self.db.execute(f"INSERT OR REPLACE INTO documents ({cols}) VALUES ({','.join('?' * len(row))})",
                            list(row.values()))
            self.db.commit()

    def update_doc(self, doc_id: str, **fields) -> None:
        if not fields:
            return
        with self._lock:
            sets = ",".join(f"{k}=?" for k in fields)
            self.db.execute(f"UPDATE documents SET {sets} WHERE doc_id=?", [*fields.values(), doc_id])
            self.db.commit()

    def docs(self, status: str | None = None) -> list[dict]:
        q = "SELECT * FROM documents" + (" WHERE status=?" if status else "") + " ORDER BY seq"
        return [dict(r) for r in self.db.execute(q, (status,) if status else ())]

    def pending_docs(self) -> list[dict]:
        return [d for d in self.docs() if d["status"] in ("new", "classified")]

    # ---- feedback ----------------------------------------------------------------------------------------------------
    def add_feedback(self, file: str, after_batch: str, decided_at: str, items: list[dict]) -> None:
        with self._lock:
            base = self.db.execute("SELECT COALESCE(MAX(seq), 0) FROM feedback_items").fetchone()[0]
            for i, it in enumerate(items, 1):
                self.db.execute("INSERT OR REPLACE INTO feedback_items VALUES (?,?,?,?,?,?)",
                                (str(it.get("item_id") or f"{file}#{i}"), file, after_batch, decided_at,
                                 json.dumps(it), base + i))
            self.db.commit()

    def feedback_items(self) -> list[dict]:
        out = []
        for r in self.db.execute("SELECT * FROM feedback_items ORDER BY seq"):
            d = dict(r)
            d["item"] = json.loads(d.pop("raw_json"))
            out.append(d)
        return out

    # ---- report snapshots --------------------------------------------------------------------------------------------
    def save_snapshot(self, mode: str, as_of: str, report: dict) -> None:
        with self._lock:
            self.db.execute("INSERT OR REPLACE INTO snapshots VALUES (?,?,?)", (mode, as_of, json.dumps(report)))
            self.db.commit()

    def previous_snapshot(self, mode: str, as_of: str) -> dict | None:
        r = self.db.execute("SELECT json FROM snapshots WHERE mode=? AND as_of<? ORDER BY as_of DESC LIMIT 1",
                            (mode, as_of)).fetchone()
        return json.loads(r["json"]) if r else None

    def log(self, name: str, record: dict) -> None:
        with self._lock, open(self.dir / "logs" / name, "a") as f:
            f.write(json.dumps(record, default=str) + "\n")
