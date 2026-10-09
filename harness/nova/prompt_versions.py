"""Extraction prompt versions, one per kind. Bump a kind's number whenever its prompt or schema changes.

The version is part of every cache key (with the model and a hash of the full request, which contains the document
text), so a cached extraction can never come from a different model or an older prompt. tests/test_cache_key.py
fingerprints each kind's prompt and schema and fails if one changes without a bump here.
"""
from __future__ import annotations

import hashlib
import json

VERSIONS = {"classify": 1, "email": 1, "invoice": 1, "table": 1, "shipping": 1, "contract": 1, "amendment": 1,
            "rate_notice": 1, "vision": 1}

# purpose label used by extract.py -> kind
PURPOSE_KIND = {"classify": "classify", "email": "email", "invoice": "invoice", "table": "table",
                "shipping": "shipping", "msa_clauses": "contract", "msa_tables": "contract",
                "amendment": "amendment", "rate_notice": "rate_notice", "vision": "vision"}


def kind_of(purpose: str) -> str:
    return PURPOSE_KIND.get(purpose.replace("_retry", ""), "other")


def version_tag(purpose: str) -> str:
    """'v1' for every kind at version 1 (the original global tag, so existing cache entries stay valid)."""
    return f"v{VERSIONS.get(kind_of(purpose), 1)}"


def fingerprint(kind: str) -> str:
    """Hash of the prompt text(s) and schema(s) a kind uses."""
    from . import prompts as P, schemas as SC
    parts = {
        "classify": (P.SYSTEM, P.CLASSIFY, SC.CLASSIFY),
        "email": (P.SYSTEM, P.EMAIL, SC.EMAIL),
        "invoice": (P.SYSTEM, P.INVOICE, SC.INVOICE),
        "table": (P.SYSTEM, P.TABLE, SC.TABLE),
        "shipping": (P.SYSTEM, P.SHIPPING, SC.SHIPPING),
        "contract": (P.SYSTEM, P.CONTRACT_TERMS, P.SCHEDULE1, P.RATES, P.ANNEXES, SC.CONTRACT_CLAUSES,
                     SC.CONTRACT_TABLES),
        "amendment": (P.SYSTEM, P.AMENDMENT, SC.AMENDMENT),
        "rate_notice": (P.SYSTEM, P.RATE_NOTICE, SC.RATE_NOTICE),
        "vision": (P.SYSTEM, P.INVOICE, P.VISION, SC.INVOICE),
    }[kind]
    return hashlib.sha256(json.dumps(parts, sort_keys=True).encode()).hexdigest()[:16]
