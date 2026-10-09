# Walkthrough (interview prep)

How the harness works, where everything lives, and how to change it quickly. Line numbers are as of the submission
commit; function names are the stable reference.

## 1. Repo layout

```
harness/
  harness.py              the three CLI commands (argparse untouched; bodies call nova.*)
  config.py               every setting and every assumption (ASSUME_*), models, budgets, confidence weights
  requirements.txt        pinned deps (anthropic, pymupdf, openpyxl, jsonschema, pyyaml, rapidocr)
  nova/
    mailbox.py            read_batch: .eml -> document rows (grader doc ids, Date header -> UTC, attachments)
    textlayer.py          vendored grader/extract.py reader + render_numbered ([pN LM]) + quote_for
    ocr.py                scans: render pages, rapidocr lines
    schemas.py            JSON schemas for every extraction kind (structured output)
    prompts.py            the prompts (meaning only, no layouts)
    prompt_versions.py    per-kind prompt versions (part of the cache key) + fingerprints
    llm.py                the one Claude client: cache, retries/backoff, budget, refusal fallback, spend ledger
    extract.py            Extractor: classify -> route -> extract -> number-check -> retry; parse_table for XLSX
    verify.py             every number must be printed on the line it cites
    ingest.py             `ingest`: register docs, extract inside the step budget
    state.py              SQLite in --state-dir: documents, feedback items, report snapshots
    world.py              the fact view for one as_of: Contract, Invoice/Line, LedgerRow, Event, Waiver, Notice...
    terms.py              resolve_rate: precedence, conflicts, missing documents; holder_for
    rules/overcharge.py duplicate.py waiver.py late_fees.py cashback.py expiry.py   one module per class
    outcome.py            Outcome: what a rule concludes about one finding key
    policy.py             actions per mode, the 5-check unattended test, $5k sums, confidence()
    feedback.py           `feedback`: store items; feedback_view -> FeedbackItem (scope matching)
    evaluate.py           `report`: rules with/without feedback, directives, learned_at, evidence, ids, outbox
    report.py             always prints a schema-valid report
    spend.py              dev-only cost ledger and spend cap
tests/                    44 tests, no API calls (synthetic invented world)
evals/                    build_mailbox.py (generator), mailboxes/, cases/*.yaml, feedback/, run_evals.py,
                          calibrate.py, results.json
tools/                    check_examples.py, check_no_hardcoding.py (+ the shipped run_mailbox / check_submission)
docs/                     PLAN.md, ASSUMPTIONS.md, PROGRESS.md, WALKTHROUGH.md
```

## 2. The three commands

| Command | Entry | What happens |
|---|---|---|
| `ingest <batch>` | `harness.py:ingest` -> `ingest.run_ingest` | `mailbox.read_batch` -> `State.add_doc` (new hashes only) -> `extract_pending` (`Extractor.run`) inside `NOVA_STEP_BUDGET_S`; unfinished docs stay pending |
| `report --as-of D --mode M` | `harness.py:report` -> `report.run_report` -> `evaluate.build_report` | finish pending extraction first (60% of budget), build `World`, run the rules with and without feedback, apply directives, actions, confidence, evidence, ids; print JSON |
| `feedback <file>` | `harness.py:feedback` -> `feedback.run_feedback` | store items verbatim with `after_batch` and `decided_at`; nothing is decided here |

## 3. One example traced end to end

`data/examples/overcharge`: invoice TX-US-2032-5394 bills 241 kg at 6.69; the contract rate is 6.01. Expected
finding: 196.92. These are the real intermediate values from `out/state_examples/overcharge`.

1. **Email to documents.** `mailbox.read_batch` (`mailbox.py:23`) parses `batch_01/0003.eml`. It makes two rows:
   `batch_01/0003.eml` (the body, via `textlayer.email_lines`) and `batch_01/0003.eml#TX-US-2032-5394.pdf` (pages via
   `textlayer.pdf_pages`), with `received_at 2032-01-03T12:06:00Z` from the Date header. `State.add_doc` stores them.
2. **Classify.** `Extractor.process` (`extract.py:72`) calls `LLM.json_call` with `prompts.CLASSIFY` and
   `schemas.CLASSIFY` on the first two pages. Stored `classify_json`: `{"doc_type": "invoice",
   "contract_ids": ["TBX-US-EXP-E60"], ...}`.
3. **Extract.** `Extractor._checked` (`extract.py:166`) uses `prompts.INVOICE` + `schemas.INVOICE` on
   `render_numbered(pages)`. The first line is stored as `{"awb": "TE56915687", "charge_label": "Air freight",
   "lane": "USE2-INE2", "pickup_date": "2031-12-25", "qty": "241", "rate": "6.69", "amount": "1612.29",
   "ref": {"page": 1, "line": 9}}`.
4. **Number check.** `verify.check` (`verify.py:34`): 13 numbers checked, 13 found on their cited lines, so no retry.
   The extraction goes into `documents.extract_json` (SQLite).
5. **The contract.** The MSA attachment was classified `msa`. `Extractor._contract` (`extract.py:125`) made two calls
   (clauses + Schedule 1, rate tables + annexes), stored the same way.
6. **Fact view.** At report time, `World.__init__` (`world.py:354`) keeps documents received by 2032-08-31 23:59:59Z.
   - `World._invoice` turns the line into `Line(awb='TE56915687', code='FRT', kind='freight', lane='USE2-INE2',
     qty=241, rate=6.69, amount=1612.29, src=Src('…TX-US-2032-5394.pdf', page 1, line 9))`.
   - `Contract.code_for` (`world.py:206`) maps "Air freight" to the contract's Annex E code FRT, and then to the
     generic kind `freight`.
7. **Pickup date.** `World.pickup` (`world.py:681`): the tracking export row `TE56915687 | PICKED_UP | 2031-12-25`
   gives `(2031-12-25, 'tracking', Src(tracking-…xlsx, page 1, line 2))`, the top of the GLOSSARY ladder.
8. **Rate.** `terms.resolve_rate` (`terms.py:76`): period P1; no amendment or notice for this lane; the agreement row
   on MSA page 8, line 34 gives rate 6.01 and minimum 58.00. `World.fuel_pct` gives 20.16% (MSA page 9, line 4).
9. **Rule.** `overcharge._invoice` (`rules/overcharge.py:40`):
   - freight `max(6.01 x 241, 58.00) = 1448.41`, a difference of 163.88;
   - fuel `20.16% x 1448.41 = 292.00` against 325.04 billed, a difference of 33.04;
   - total `196.92`, giving `Outcome(overcharge, TX-US-2032-5394, finding, 196.92, shipments=[(TE56915687,
     tracking)])`.
10. **Action and confidence.** `policy.assign_actions` (`policy.py:36`): supervised gives `draft:dispute`; autonomous
    gives `execute:dispute` after `policy.unattended` (`policy.py:77`) passes all five checks.
    `policy.confidence` (`policy.py:107`) sets the confidence.
11. **Report item.** `evaluate._item` (`evaluate.py:153`) builds the evidence through `_quote` ->
    `textlayer.quote_for`, i.e. the exact cited lines: the invoice line, the rate row, the tracking row, the fuel row
    and the pricing clause. `evaluate._ids` (`evaluate.py:179`) gives `overcharge:TX-US-2032-5394`, plus supersedes
    or retro against the previous snapshot. `evaluate._outbox` writes the draft addressed to the Schedule 1
    billing-disputes contact.

## 4. Where each GLOSSARY rule lives

| Rule | Code |
|---|---|
| One item per key; key shapes | `outcome.Outcome.key`; `evaluate.evaluate_all` (merge) |
| invoice_id normalisation | `world.norm_id` (the grader's regex); scan id repair `World._reconcile_ids` + `world.skeleton` |
| Statement = invoice; credit note never a key | `schemas.INVOICE.document_kind`; `World._invoice` |
| Amount = billed − correct, positive lines only | `rules/overcharge._invoice` (`ASSUME_OVERCHARGE_POSITIVE_LINES_ONLY`) |
| Half-up rounding, % on a base of rounded lines | `money.round2`, `money.pct`, `money.line_amount` |
| Pickup-date ladder | `World.pickup` |
| INR once per finding; no FX row → cannot_determine | `money.to_usd`; `World.fx_rate`; `rules/overcharge._fx_missing` |
| Precedence, Schedule 1 authority, quoted text | `terms.resolve_rate`, `World.authorised` (exact address), `World.person_by_addr`, `world.norm_categories` |
| Conflict + amount_range | `terms.resolve_rate` (status `conflict`) → `rules/overcharge._invoice` (range) |
| Cannot_determine + holder | `terms._missing`, `terms.holder_for`; waiver originals `rules/waiver._cannot` |
| Duplicates (resend; same line on two invoices; credits) | `rules/duplicate.evaluate` |
| Waivers (authority, scope, condition, forwarded) | `rules/waiver.evaluate`, `_targets`, `_original_held`, `_cannot` |
| Late fee not owed (extension, grace, ceil/30, compounding) | `rules/late_fees.evaluate_not_owed`, `due_date`, `expected_fees` |
| Late-fee risk (1..14 days, principal less disputes, FX) | `rules/late_fees.evaluate_risk` |
| Cashback (QS, tiers, closed periods, credits issued, due) | `rules/cashback.evaluate`, `qualifying_spend`, `_period` |
| Expiry (0..60 days, notice deadline, extensions) | `rules/expiry.evaluate` |
| Actions, modes, $5k sums, unattended test | `policy.assign_actions`, `policy.outbound_sums`, `policy.unattended`, `policy.recipient` |
| as_of filtering | `World.__init__` (cutoff), `feedback.feedback_view` (decided_at) |
| Evidence quotes on the cited page | `evaluate._quote`, `textlayer.quote_for` (same text as the grader) |
| supersedes / retro / stale keys gone | `evaluate._ids`, `evaluate._is_retro`; recompute-from-scratch in `build_report` |
| learned_at | `evaluate._learned` (with- vs without-feedback diff) |
| Feedback kinds and scope | `feedback.FeedbackItem.matches/in_dates`; scoped facts in `World.authorised`, `terms._accepted`, `terms._feedback_precedence`, `rules/waiver` (one_off); directives in `evaluate._directives` |
| Injection: AI-directed text is data | `prompts.SYSTEM` rule 1; `directives_to_automation` fields; addresses only in `evaluate._outbox` |

## 5. How to extend

**A new invoice layout.** Usually nothing: extraction reads meaning, not positions (see `evals/mailboxes/` for three
layouts the practice never shows). If the new layout prints a field the schema doesn't have:
1. add the field to `schemas.INVOICE` (`LINE` or the header) and describe it in `prompts.INVOICE`;
2. bump `VERSIONS["invoice"]` in `nova/prompt_versions.py`, run `pytest tests/test_cache_key.py` and re-pin
   `tests/prompt_fingerprints.json` (delete it and re-run);
3. read the field in `World._invoice` (`world.py:582`) and use it in the rule;
4. add an eval mailbox in `evals/build_mailbox.py` and run `make eval K=<name>`.

**A new charge kind.** Add words to `world.KIND_WORDS`, and an expected-value branch in
`rules/overcharge._expected_other`. If it counts toward qualifying spend, also add it to
`rules/cashback.ACCESSORIAL_KINDS`.

**A new feedback type.**
1. Parsing is generic: `feedback.feedback_view` already gives `decision`, `fact_type`, `subject`, `value` and the
   scope.
2. If it changes exactly one key, add a branch in `evaluate._directives` (`evaluate.py:96`).
3. If it changes how sources are read (authority, rates, precedence), consume it where that decision is made:
   `World.authorised`, `terms.resolve_rate` (see `_accepted`, `_feedback_precedence`), or the class rule. Always
   filter with `fb.matches(...)` and `fb.in_dates(...)`, and append `fb` to `outcome.feedback_used` so `learned_at`
   is set.
4. Add a test to `tests/test_feedback.py` that it applies and that it doesn't spread.

## 6. Five likely "change this on the spot" requests

| Request | Edit | Check |
|---|---|---|
| 1. "Make the human_review threshold $2,500" or "change the expiry window to 90 days" | `harness/config.py`: `HUMAN_REVIEW_THRESHOLD_USD`, `EXPIRY_WINDOW_DAYS`, `RISK_WINDOW_DAYS` | `pytest tests/test_rules.py -k threshold`; `make grade` (cached, $0) |
| 2. "Count re-sent invoices twice in rebate spend" (A1) or "apply check 1 only when the pickup date decides the amount" (A2) | `harness/config.py`: `ASSUME_RESENT_INVOICE_COUNTS_ONCE_IN_QS = False` / `ASSUME_CHECK1_SCOPE = "pickup_decides_amount"`; update `docs/ASSUMPTIONS.md` | `make grade`, `make sheet`; the exam Q3 rebate moves to 4,469.10 under A1 = False |
| 3. "Also dispute tax lines" or "dispute a weight that differs from the AWB" | Tax: `config.ASSUME_CHECK_TAX_LINES` + a `tax` branch in `rules/overcharge._expected_other`. Weight: `config.ASSUME_QUANTITY_AS_PRINTED` + use `World.waybills[awb]["chargeable_weight"]` in `_invoice` | `tests/test_rules.py` new case; `make eval` |
| 4. "Add a confidence feature" (e.g. lower confidence for invoices older than 90 days) | set `o.features[...]` in the rule (`rules/*.py`), add a weight to `config.CONF_WEIGHTS`, read it in `policy.confidence` | `python evals/calibrate.py` (cached) |
| 5. "Support a new feedback decision" (e.g. `extend_due_date` for one invoice) | `evaluate._directives` (one-key) or `rules/late_fees.due_date` (treat it as an authorised extension filtered by `fb.matches(invoice_id=...)`) | new test in `tests/test_feedback.py` |

Others that come up: "show no_finding items too" (drop the `no_finding` filter in `evaluate.evaluate_all`); "only Opus"
(`DEFAULT_MODEL_DOC` in `config.py`; costs more); "a fourth unattended check" (`policy.unattended`).

## 7. Running things fast (dev)

- Commands: `~/bin/nova-run "<cmd>"` loads the API key from `~/.bashrc`.
- `.nova_dev.env` (gitignored): shared cache `~/.nova_cache`, Sonnet override, 4 threads, ledger at
  `local/api_spend.json`, cap $15. Add `NOVA_DEV_DEFAULT_MODELS=1` to use the code-default models with the cache on.
- Rules, report or policy changes cost $0: every extraction is cached. Only a prompt or schema change re-extracts,
  and only that kind.
- `python tools/check_examples.py -k overcharge --keep`, `make eval K=conflict`, `python -m pytest -q tests`,
  `python evals/calibrate.py`.
- `make grade` (both modes) runs in about a minute from the cache; `make sheet` in about 15 s.

## 8. Things to say about limits

- A1 (re-sent invoice counted once in QS) is the least certain call; A2–A20 are in `docs/ASSUMPTIONS.md`.
- Step budget: ingest stops launching calls at 72% of 300 s; in-flight calls are capped to the time left; the rest
  stays pending and the next step (report first) finishes it. Nothing is dropped silently.
- Confidence weights are hand-set: there were no wrong items to fit, so AUROC is unmeasured.
- Margin step-down and marginal tiers are extracted but not computed.
