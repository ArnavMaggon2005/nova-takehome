# My solution

The harness reads each document with Claude into typed facts that cite their page and line. Plain Python makes every
decision: which rate applies, conflicts, windows, Decimal arithmetic, actions and confidence. The plan is in
`docs/PLAN.md`, assumptions in `docs/ASSUMPTIONS.md`, and phase notes in `docs/PROGRESS.md`.

## How to run it

```
make setup                  # Linux, macOS or WSL (the Makefile expects .venv/bin/python)
export ANTHROPIC_API_KEY=…  # a workspace-scoped key; ANTHROPIC_BASE_URL is honoured if set
make grade                  # practice mailbox, both modes -> report_card.txt / .json
make sheet                  # exam mailbox -> answer_sheet.json, out/exam_report.json
make eval                   # tools/check_no_hardcoding.py, then the 23 eval cases -> evals/results.json
make validate
```

Nothing beyond `harness/requirements.txt` is needed to run. Defaults:
- Opus 5.5 for contracts, amendments, annexes and rate notices; Sonnet 5.5 for everything else;
- 12 parallel calls;
- a 300 s budget per step (`NOVA_STEP_BUDGET_S`), with unfinished documents carried to the next step, so nothing is
  ever skipped silently.

The GitHub workflow is manual only (`workflow_dispatch`): this repo holds no API key secret, so it never runs on push.

Developer extras that grading never uses:
- `requirements-dev.txt` (pytest).
- A gitignored `.nova_dev.env`. The grader strips the environment, so dev runs read `NOVA_*` settings from it: a
  shared extraction cache, a model override, fewer threads, a spend ledger and a spend cap. Without that file every
  one of these is inactive; `tests/test_grading_defaults.py` proves it, and so did a stripped-environment smoke run.

Tools:
- `tools/check_examples.py`: the 8 worked examples against their expected output.
- `tools/check_no_hardcoding.py`: no invoice id, contract id, AWB, lane or name from `data/` may appear in `harness/`.
- `evals/build_mailbox.py`: generates the eval mailboxes.
- `evals/calibrate.py`: Brier, AUROC and reliability on every labelled item.

## What works

- **Practice card: 99.7 / 100** in both modes, with no hard gate triggered:
  - detection F1 1.00 with evidence, all money recovered, nothing wrongly disputed;
  - adaptation 11/11, learning 3/3, conflicts and missing documents 2/2;
  - actions 24/24 in each mode, 4% escalated.
- **Worked examples:** 8/8 match `expected_finding.json`, decoys included.
- **Exam:** `answer_sheet.json` is from the final run with the default models; all 55 citations resolve.
- **Eval set:** 23/23 pass (21 mine, two invented worlds). Cases cover:
  - new layouts and column orders, text and dd.mm.yyyy dates, lakh digit grouping, a scanned bill;
  - an INR bill with no exchange-rate row;
  - a waiver seen only quoted in a forward, and one from a contact without waiver authority;
  - a one-off waiver followed by a month it doesn't cover;
  - a backdated amendment (`retro`);
  - "AI"-directed text in an email and in an invoice footer;
  - feedback that applies, must not spread, and closes a key;
  - autonomous hold-backs at $5,000 and for a weak pickup date;
  - risk and expiry window edges, and an unranked conflict.
- **Tests:** 44 unit tests on synthetic data, never calling the API. They cover:
  - GLOSSARY arithmetic and windows;
  - every feedback kind with no-spread checks;
  - the cache key and prompt-version pinning;
  - budget carry-over, failure isolation, refusal fallback and report validity.
- **Prompt injection:** the model only fills extraction schemas; authority comes from exact Schedule 1 addresses; only
  feedback can close a key; no outbound field ever holds an address.

## What doesn't

- **Assumptions.** Ambiguities were settled in this order: GLOSSARY, then the worked examples, then the practice key
  (as evidence only), then the conservative reading. Each is one constant in `harness/config.py`.
  - **A1, the least certain:** a re-sent paid invoice counts once in rebate spend. The other reading changes the exam
    Q3 rebate from 4,307.34 to 4,469.10.
  - A2: unattended check 1 applies to every shipment in a key.
  - A5: quantities are taken as printed (an AWB weight difference isn't disputed).
  - A11: tax lines are never disputed.
  - A13: a line whose correct value can't be computed is accepted.
- **Not implemented:**
  - margin step-down: extracted but not computed, and every contract seen marks it not applicable;
  - marginal (tiered-by-band) rebates;
  - recomputing chargeable weight from AWB dimensions.
- **Confidence weights are hand-set.** Every labelled item is right, so AUROC couldn't be measured; the base is hedged
  to about 0.93.
- **How the final cards were produced:**
  - `make grade` and `make sheet` used the default models, with only contract documents freshly extracted by Opus;
    everything else came from the cache.
  - `make eval` ran from cached Sonnet extractions.
  - A run without the dev file and with a stripped environment was smoke-tested on one example mailbox.
  - Cold-run cost is about $21 per 1,000 documents. With low rate limits, documents may spill into the next step;
    they're never dropped.

## The eval case that caught a bug

`evals/cases/a_conflict_unranked.yaml` expected a conflict between a signed amendment and an authorised rate advice.
The harness said cannot_determine instead.

The amendment reads "the Appendix 1 rate for route SEA-ATL … is USD 4.60". The model listed "Appendix 1" as a
referenced document (the agreement's own annex, not attached). The resolver treated every referenced document as
possibly missing, so the explicit rate lost to a document that was never missing. Any hidden-set amendment worded this
way would have turned real findings into requests for a document.

Fix in `harness/nova/terms.py`: a referenced document can be missing only if the amendment attaches or incorporates
it, and an amendment's own rows for a lane win over its references. The regression test is
`tests/test_rules.py::test_reference_to_the_annex_being_edited_is_not_a_missing_document`; practice, exam and examples
were unchanged.
