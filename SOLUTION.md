# My solution

The harness uses Claude only to read each document into typed facts, and every fact cites the page and line it came from. Everything else is plain Python: which rate applies, conflicts, date windows, Decimal arithmetic, actions and confidence. The plan I agreed before any code was written is in `docs/PLAN.md`, my assumptions are in `docs/ASSUMPTIONS.md`, and there's a note per phase in `docs/PROGRESS.md`.

## How to run it

```
make setup                  # Linux, macOS or WSL (the Makefile expects .venv/bin/python)
export ANTHROPIC_API_KEY=…  # a workspace-scoped key; ANTHROPIC_BASE_URL is used if set
make grade                  # practice mailbox, both modes -> report_card.txt / .json
make sheet                  # exam mailbox -> answer_sheet.json, out/exam_report.json
make eval                   # the no-hardcoding check, then the 23 eval cases -> evals/results.json
make validate
```

Nothing outside `harness/requirements.txt` is needed. The defaults are:

- Opus 5.5 for contracts, amendments, annexes and rate notices, and Sonnet 5.5 for everything else;
- 12 parallel calls;
- a 240 s budget per step (`NOVA_STEP_BUDGET_S`). Anything unfinished is carried to the next step, so no document is ever skipped silently.

The GitHub workflow is manual only (`workflow_dispatch`). The repo holds no API key secret, so it never runs on push.

A few developer extras exist that grading never touches:

- `requirements-dev.txt` (pytest).
- A gitignored `.nova_dev.env`. The grader strips the environment, so during development the harness reads its `NOVA_*` settings from this file: a shared extraction cache, a model override, fewer threads, a spend ledger and a spend cap. Without the file, all of these are off. `tests/test_grading_defaults.py` proves it, and so did a smoke run with a stripped environment.

And some helper tools:

- `tools/check_examples.py`: runs the 8 worked examples against their expected output.
- `tools/check_no_hardcoding.py`: fails if any invoice id, contract id, AWB, lane or name from `data/` appears in `harness/`.
- `evals/build_mailbox.py`: generates my eval mailboxes.
- `evals/calibrate.py`: Brier score, AUROC and reliability over every labelled item.

## What works

- **Practice card: 99.7 / 100** in both modes, with no hard gate triggered:
  - detection F1 of 1.00 with evidence, all money recovered, nothing wrongly disputed;
  - adaptation 11/11, learning 3/3, conflicts and missing documents 2/2;
  - actions 24/24 in each mode, with 4% escalated.
- **Worked examples:** all 8 match their `expected_finding.json`, decoys included.
- **Exam:** `answer_sheet.json` comes from the final run with the default models, and all 55 citations resolve.
- **Eval set:** 23/23 pass, 21 of them mine, set in two worlds I invented so they don't look like the practice files. They cover:
  - new layouts and column orders, dates written out and in dd.mm.yyyy, lakh digit grouping, and a scanned bill;
  - an INR bill with no exchange-rate row;
  - a waiver seen only quoted inside a forward, and one from a contact without waiver authority;
  - a one-off waiver followed by a month it doesn't cover;
  - a backdated amendment (`retro`);
  - text aimed at "the AI" in an email and in an invoice footer;
  - feedback that should apply, feedback that must not spread, and feedback that closes a key;
  - autonomous mode holding back at $5,000 and for a weak pickup date;
  - the edges of the risk and expiry windows, and an unranked conflict.
- **Tests:** 44 unit tests on synthetic data. They never call the API and are isolated from the dev cache. They cover:
  - the GLOSSARY arithmetic and windows;
  - every feedback kind, with checks that nothing spreads;
  - the cache key and prompt-version pinning;
  - budget carry-over, failure isolation, the refusal fallback and report validity.
- **Prompt injection:** the model only fills extraction schemas. Authority comes from exact Schedule 1 email addresses, only feedback can close a key, and no outbound field ever holds an address.

## What doesn't

- **Assumptions.** Where the brief could be read two ways, I settled it in this order: the GLOSSARY, then the worked examples, then the practice key (as evidence only, never copied), then the conservative reading. Each assumption is a single constant in `harness/config.py`.
  - **A1, the one I'm least sure of:** a re-sent paid invoice counts once in rebate spend. The other reading would change the exam's Q3 rebate from 4,307.34 to 4,469.10.
  - A2: unattended check 1 applies to every shipment in a key.
  - A5: quantities are taken as printed, so an AWB weight difference isn't disputed.
  - A11: tax lines are never disputed.
  - A13: a line whose correct value can't be computed is accepted.
- **Not implemented yet:**
  - the margin step-down: it's extracted but not computed, and every contract I've seen marks it as not applicable;
  - marginal (tiered-by-band) rebates;
  - recomputing chargeable weight from AWB dimensions.
- **Confidence weights are set by hand.** Every labelled item is right, so AUROC couldn't be measured. I've pitched the base at about 0.93 to leave room for harder, unseen data.
- **How the final outputs were produced:**
  - `make grade` and `make sheet` used the default models. Only the contracts were freshly extracted by Opus; everything else came from the cache.
  - `make eval` ran from cached Sonnet extractions.
  - I smoke-tested a run without the dev file and with a stripped environment on one example mailbox.
  - A cold run costs about $21 per 1,000 documents. Under tight rate limits, documents may spill into the next step, but they're never dropped.

## The eval case that caught a bug

`evals/cases/a_conflict_unranked.yaml` expected a conflict between a signed amendment and an authorised rate advice. The harness returned cannot_determine instead.

The amendment says "the Appendix 1 rate for route SEA-ATL … is USD 4.60". The model listed "Appendix 1" as a referenced document; it's the agreement's own annex, so it isn't attached. The resolver treated every referenced document as possibly missing, so the amendment's explicit rate lost to a document that was never actually missing. Any amendment in the hidden set worded like this would have turned a real finding into a request for a document.

The fix is in `harness/nova/terms.py`. A referenced document can only count as missing if the amendment attaches or incorporates it, and an amendment's own rows for a lane win over its references. The regression test is `tests/test_rules.py::test_reference_to_the_annex_being_edited_is_not_a_missing_document`, and the practice, exam and example results didn't change.
