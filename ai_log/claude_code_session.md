# Prompt log (Claude Code session export)

Exported from the Claude Code session file. Kept: every prompt I sent, every reply Claude wrote, and one line per tool call. Left out: raw tool output (file and command dumps), the model's internal thinking, and system messages. No secrets appeared in the session; the API key was never printed.

## Prompt 1 (2026-10-09 05:27:10 UTC)

<pasted_content id="6518">
You are helping me with a take-home assignment for an "AI Full Stack Engineer" role at GoComet. I have 48 hours in
total, and the brief is sized for about 16 focused hours. In this session I want ONLY an architecture and an
implementation plan. Do not write harness code yet. When the plan is done, stop and wait for my go-ahead.

## Step 0: get the repo
If this folder doesn't already contain the repo, clone it here:
  git clone https://github.com/gocomet-india/nova-takehome .
Then run `make setup`. If it fails, tell me why; don't work around it silently.

## Step 1: read the spec properly before designing anything
Read these fully, in this order. GLOSSARY.md is the real spec, and it wins over README.md where they differ.
1. README.md, GLOSSARY.md (every line), SUBMISSION.md, DESIGN.md, SOLUTION.md, AI_USE.md
2. grader/schema/report.schema.json, harness/harness.py (the stub), harness/requirements.txt, Makefile
3. grader/*.py, especially extract.py (the text layer the grader uses to check my quotes), run_grader.py, score.py
   and validate.py, plus tools/*.py and evals/README.md with the two sample cases. Note exactly how the grader
   matches items, scores amounts, checks quotes and applies the "cap at 40" penalties.
4. Every data/examples/*/EXPLANATION.md and expected_finding.json (8 worked examples, one per class, plus a
   conflict and a duplicate rebilled 4 months later).
5. data/scenarios/feedback/W1_batch_01.json and 4-5 files in data/scenarios/answers/ covering different classes.
6. Run grader/extract.py over a few practice emails AND a few data/exam emails, so you can see the real text of
   the invoices, contracts (Schedule 1, annexes, precedence clause), Excel statements and tracking exports. Compare
   the practice and exam layouts. Find the scanned invoice with no text layer in each mailbox.

As you read, keep a list of every rule, formula, window, threshold and edge case in the glossary. You'll need it in
the plan.

## What the system must do (my summary; verify it against the files)
Build harness/harness.py with three CLI commands: `ingest <batch_dir>`, `report --as-of D --mode
supervised|autonomous` and `feedback <file>`. Each runs in a fresh process with all memory under --state-dir. The
harness reads a mailbox (.eml files with PDF and XLSX attachments, plus one scanned PDF needing OCR or vision) and
finds six classes of money leak: overcharge, duplicate, waived_but_billed, late fees (not_owed and risk), cashback
(rebate, margin_step_down, promised_credit) and expiry. It also handles conflict and cannot_determine, the
authority/precedence ladder, Schedule 1 sender authority, pickup-date resolution, half-up rounding, INR to USD via
Annex F, as_of filtering, the action matrix per mode with the 5-check unattended-action test and the $5,000
human_review threshold, supersedes/retro/learned_at, scoped feedback (one_off vs standing), calibrated confidence,
and evidence quotes that must match grader/extract.py text on the cited page.

It is graded mainly on a HIDDEN set with a new customer, carrier, invoice layouts, wordings, backdated amendments,
one-off waivers, prompt-injection emails and new feedback kinds. A rules-only harness tuned to the practice files
scored about 11/100 there. Design for generalisation: an LLM reads documents by meaning, deterministic Python does
all arithmetic and rule logic, and nothing is hardcoded from the practice data (no names, lanes, invoice numbers or
per-layout regexes).

## Deliverable: write docs/PLAN.md with these sections
1. **Problem in your own words.** One paragraph, then a checklist table of every glossary rule
   (rule → where it's defined → which component implements it).
2. **Architecture diagrams (Mermaid).**
   a) A component diagram: email parsing, attachment extraction, OCR/vision, document classification, LLM
      structured extraction, fact store, rules engine (one module per class), conflict/authority resolver, action
      and mode policy, confidence model, report builder, quote verifier.
   b) A sequence diagram for each of ingest, report and feedback.
   c) The on-disk layout of --state-dir.
3. **Component by component.** For each component: its responsibility, inputs and outputs, LLM or deterministic
   and why, the glossary rules it covers, the scoring component it serves, and its failure modes.
4. **Fact model.** Typed schemas for every fact kind: contract terms, rate rows and bands, fuel %, surcharges,
   Annex F fx, Schedule 1 contacts, invoice lines, credit notes, ledger entries, tracking events, waivers,
   extensions, amendments, feedback facts. Each carries provenance (doc path in the grader's format, page, verbatim
   quote, received_at from the Date header, sender, authority level 1-5, in-force dates, extraction confidence).
   Explain how facts are keyed and how they're re-evaluated when new batches arrive.
5. **Detection logic per class**, including how each class's decoys and near misses stay no_finding (use the
   EXPLANATION.md decoys).
6. **Verdict and action decisions.** The finding / no_finding / conflict / cannot_determine / human_review decision
   tree, the action table per mode, the unattended-action test, amount_range for conflicts, and the missing_doc
   holder lookup from Schedule 1.
7. **Feedback.** How each decision and fact type is stored and applied, scope matching (applies_to filters,
   valid_from/valid_to), one_off vs standing, learned_at, and what stops a fact spreading too far.
8. **Change over time.** Stable item ids, supersedes, retro for backdated documents, and keys that must disappear.
9. **Confidence model.** The concrete formula or feature scoring, and how I'll check calibration (Brier/AUROC) on
   my eval set.
10. **Prompt-injection defence.** How text addressed to "the AI", "automated systems" or "the auditor" is treated
    as data and never followed, and how outbound actions can never become irreversible.
11. **LLM usage.** The model(s), prompts with structured JSON output, temperature 0, caching extractions by content
    hash in the state dir, retries, staying within per-step time limits, and an estimate of cost and time per
    1,000 documents with the arithmetic shown.
12. **Eval plan.** At least 12 eval cases I'll build with MY OWN mailboxes under evals/ (new layouts, reworded
    emails, edge dates on windows, INR without an Annex F row, a forwarded waiver, a one-off waiver applied to the
    wrong month, a backdated amendment, injection emails, feedback that should and shouldn't generalise, an
    autonomous case that must hold back). Give each its name, purpose and expected verdict.
13. **Implementation plan.** Phased milestones in priority order. Getting the exam answer_sheet.json right is a
    pass/fail gate, so it comes early. Each phase lists its tasks, the files and modules created (propose a
    harness/ package layout), the acceptance check (examples pass, a `make grade` target, `make validate` green),
    and hour estimates totalling about 16.
14. **Requirement → component → verification.** A traceability table covering every scoring row in README.md, every
    one of the five "cap at 40" mistakes, and every item in SUBMISSION.md.
15. **Risks, assumptions and open questions.** Mark which claims you verified in the files and which you assumed.
    List anything ambiguous enough that I should email GoComet about it.

## Rules for this session
- Python 3.11+, pinned dependencies, the anthropic SDK, with ANTHROPIC_API_KEY and ANTHROPIC_BASE_URL read from the
  environment. Never put a key in any file.
- Use decimal.Decimal with ROUND_HALF_UP for money, never floats.
- Build on grader/extract.py's text so evidence quotes match what the grader checks.
- Be concrete. Cite file paths and glossary sections rather than giving generic advice.
- When PLAN.md is written, give me a 10-line summary in chat plus your open questions, then stop.
</pasted_content id="6518">


**Claude:** I'll start by checking whether the repo is already here.


- `Bash`: List project folder and check git status

**Claude:** The folder is empty, so I'll clone the repo.


- `Bash`: Clone the take-home repo into the folder

- `Bash`: Show Makefile, gitignore and directory file counts


**Claude:** Now `make setup`. The Makefile assumes `.venv/bin/python` (a Unix layout), so I'll check what tools exist on this Windows machine first.


- `Bash`: Check for make, uv and Python installations

- `Bash`: Show requirements and CI workflow


- `Bash`: Try make setup and look for make or WSL



- `Bash`: Check make and Python inside WSL Ubuntu



- `Bash`: Run make setup inside WSL Ubuntu


**Claude:** `make setup` passed in WSL. I'll check which Python it picked and whether the OCR dependency and the anthropic SDK import.


- `Bash`: Check venv Python version and key imports


**Claude:** The environment works (Python 3.13 in `.venv`, with anthropic 1.8.0, pymupdf 1.28.2 and rapidocr all importing). Now Step 1: reading the spec, starting with README and GLOSSARY.


- `Read`: C:\Users\arnav\OneDrive\Desktop\Nova\README.md

- `Read`: C:\Users\arnav\OneDrive\Desktop\Nova\GLOSSARY.md

- `Bash`: Show submission and template docs

- `Bash`: Show report schema and harness stub

**Claude:** Spec and schema are read. Next, the grader code. extract.py matters most because it defines the text my quotes must match.


- `Bash`: List grader, tools and evals files with line counts

- `Read`: C:\Users\arnav\OneDrive\Desktop\Nova\grader\extract.py

- `Read`: C:\Users\arnav\OneDrive\Desktop\Nova\grader\score.py

- `Read`: C:\Users\arnav\OneDrive\Desktop\Nova\grader\run_grader.py

- `Read`: C:\Users\arnav\OneDrive\Desktop\Nova\grader\validate.py


**Claude:** I've read score.py in full. Next: the sheet tooling, the submission check and the evals runner.


- `Read`: C:\Users\arnav\OneDrive\Desktop\Nova\grader\make_sheet.py

- `Read`: C:\Users\arnav\OneDrive\Desktop\Nova\grader\grade_sheet.py


- `Bash`: Show run_mailbox and check_submission tools

- `Bash`: Show evals runner, sample cases and batch dates


**Claude:** Grader and tools are done. Now the 8 worked examples: every EXPLANATION.md and expected_finding.json.


- `Bash`: Show first three worked examples and file list

- `Bash`: Show remaining five worked examples

- `Bash`: Show the remaining examples' explanations without the finding JSON


**Claude:** The explanations are read. Now the expected_finding.json files for the last five examples, focusing on the fields that drive grading.


- `Bash`: Summarise key fields of example expected findings


**Claude:** Shell quoting broke there (the outer shell expanded `$d`). I'll put helper scripts in the scratchpad and run them through the WSL venv.


- `Write`: C:\Users\arnav\AppData\Local\Temp\claude\c--Users-arnav-OneDrive-Desktop-Nova\b290e15b-ef2f-42f6-87a6-f74f4b560165\scratchpad\ex_summary.py

- `Bash`: Run the example summary helper via WSL venv


- `Bash`: Run example summary helper via WSL without path mangling


**Claude:** Now the practice feedback file and the list of answer files.


- `Bash`: Show feedback file and answer file list


**Claude:** That paste came out garbled. I'll write a proper summariser for all 30 answer files.


- `Write`: C:\Users\arnav\AppData\Local\Temp\claude\c--Users-arnav-OneDrive-Desktop-Nova\b290e15b-ef2f-42f6-87a6-f74f4b560165\scratchpad\ans_summary.py

- `Bash`: Summarise all 30 practice answer files


**Claude:** I'll read several answer files in full, covering different classes: feedback, cannot_determine, conflict, late-fee risk, the INR overcharge, expiry and cashback.


- `Bash`: Show feedback and cannot_determine answer files

- `Bash`: Show conflict, risk, INR, expiry, cashback, duplicate answers



- `Write`: C:\Users\arnav\AppData\Local\Temp\claude\c--Users-arnav-OneDrive-Desktop-Nova\b290e15b-ef2f-42f6-87a6-f74f4b560165\scratchpad\inventory.py

- `Bash`: Inventory every practice mailbox email


**Claude:** The practice scan is `batch_02/0016.eml#TXI-35-36-0024.pdf`, an INR invoice whose answer is a clean control. Now the exam mailbox inventory.


- `Bash`: Inventory every exam mailbox email


**Claude:** The exam scan is `batch_02/0016.eml#CDI-3031-0306.pdf`, also an INR invoice. Now I'll dump the full grader text layer for both mailboxes to scratchpad files so I can compare layouts.


- `Write`: C:\Users\arnav\AppData\Local\Temp\claude\c--Users-arnav-OneDrive-Desktop-Nova\b290e15b-ef2f-42f6-87a6-f74f4b560165\scratchpad\dump.py

- `Bash`: Dump grader text layer of both mailboxes to files


**Claude:** The exam mailbox decides the pass/fail gate, so I'll read its whole text layer, starting with the contracts.


- `Read`: C:\Users\arnav\AppData\Local\Temp\claude\c--Users-arnav-OneDrive-Desktop-Nova\b290e15b-ef2f-42f6-87a6-f74f4b560165\scratchpad\exam.txt


- `Read`: C:\Users\arnav\AppData\Local\Temp\claude\c--Users-arnav-OneDrive-Desktop-Nova\b290e15b-ef2f-42f6-87a6-f74f4b560165\scratchpad\exam.txt


- `Read`: C:\Users\arnav\AppData\Local\Temp\claude\c--Users-arnav-OneDrive-Desktop-Nova\b290e15b-ef2f-42f6-87a6-f74f4b560165\scratchpad\exam.txt

- `Read`: C:\Users\arnav\AppData\Local\Temp\claude\c--Users-arnav-OneDrive-Desktop-Nova\b290e15b-ef2f-42f6-87a6-f74f4b560165\scratchpad\exam.txt



- `Grep`: ^======================== batch_0[12]/00(01|02|03|04|07|08|20|23|24|25|29|30|31)\.eml

- `Read`: C:\Users\arnav\AppData\Local\Temp\claude\c--Users-arnav-OneDrive-Desktop-Nova\b290e15b-ef2f-42f6-87a6-f74f4b560165\scratchpad\practice.txt



- `Read`: C:\Users\arnav\AppData\Local\Temp\claude\c--Users-arnav-OneDrive-Desktop-Nova\b290e15b-ef2f-42f6-87a6-f74f4b560165\scratchpad\practice.txt


- `Read`: C:\Users\arnav\AppData\Local\Temp\claude\c--Users-arnav-OneDrive-Desktop-Nova\b290e15b-ef2f-42f6-87a6-f74f4b560165\scratchpad\practice.txt

- `Read`: C:\Users\arnav\AppData\Local\Temp\claude\c--Users-arnav-OneDrive-Desktop-Nova\b290e15b-ef2f-42f6-87a6-f74f4b560165\scratchpad\practice.txt


- `Bash`: Show INR invoice, waivers, statement and AP register samples


**Claude:** Now the two scanned invoices. I'll render them to PNG to look at, and run rapidocr to see what local OCR returns.


- `Write`: C:\Users\arnav\AppData\Local\Temp\claude\c--Users-arnav-OneDrive-Desktop-Nova\b290e15b-ef2f-42f6-87a6-f74f4b560165\scratchpad\ocr.py

- `Bash`: OCR the exam scanned invoice with rapidocr



- `Read`: C:\Users\arnav\AppData\Local\Temp\claude\c--Users-arnav-OneDrive-Desktop-Nova\b290e15b-ef2f-42f6-87a6-f74f4b560165\scratchpad\exam_scan.png

- `Bash`: OCR the practice scanned invoice with rapidocr



- `Write`: C:\Users\arnav\AppData\Local\Temp\claude\c--Users-arnav-OneDrive-Desktop-Nova\b290e15b-ef2f-42f6-87a6-f74f4b560165\scratchpad\verify.py

- `Bash`: Run Decimal checks of practice and exam arithmetic



- `Skill`: claude-api

## Prompt 2 (2026-10-09 05:37:22 UTC)

Base directory for this skill: C:\Users\arnav\AppData\Local\Temp\claude\bundled-skills\2.1.289\200cb8222f91befd0fe9fd0bea1369aa\claude-api

# Building LLM-Powered Applications with Claude

This skill helps you build LLM-powered applications with Claude. Choose the right surface based on your needs, detect the project language, then read the relevant language-specific documentation.

## Before You Start

Scan the target file (or, if no target file, the prompt and project) for non-Anthropic provider markers - `import openai`, `from openai`, `langchain_openai`, `OpenAI(`, `gpt-4`, `gpt-5`, file names like `agent-openai.py` or `*-generic.py`, or any explicit instruction to keep the code provider-neutral. If you find any, stop and tell the user that this skill produces Claude/Anthropic SDK code; ask whether they want to switch the file to Claude or want a non-Claude implementation. Do not edit a non-Anthropic file with Anthropic SDK calls. (Exception: the `prompt-audit` subcommand is non-interactive and does not stop here - it records non-Anthropic provider markers in its report's stated assumptions and never proposes switching a non-Anthropic file to the Anthropic SDK.)

## Output Requirement

When the user asks you to add, modify, or implement a Claude feature, your code must call Claude through one of:

1. **The official Anthropic SDK** for the project's language (`anthropic`, `@anthropic-ai/sdk`, `com.anthropic.*`, etc.). This is the default whenever a supported SDK exists for the project.
2. **Raw HTTP** (`curl`, `requests`, `fetch`, `httpx`, etc.) - only when the user explicitly asks for cURL/REST/raw HTTP, the project is a shell/cURL project, or the language has no official SDK.

Never mix the two - don't reach for `requests`/`fetch` in a Python or TypeScript project just because it feels lighter. Never fall back to OpenAI-compatible shims.

**Never guess SDK usage.** Function names, class names, namespaces, method signatures, and import paths must come from explicit documentation - either the `{lang}/` files in this skill or the official SDK repositories or documentation links listed in `shared/live-sources.md`. If the binding you need is not explicitly documented in the skill files, WebFetch the relevant SDK repo from `shared/live-sources.md` before writing code. Do not infer Ruby/Java/Go/PHP/C# APIs from cURL shapes or from another language's SDK.

**If WebFetch or repository access fails** (network restricted, timeouts, clone blocked): do not keep retrying - write code from the patterns and namespace/package tables in the `{lang}/` file, run the compiler or interpreter on it, and iterate on the error output. For statically-typed SDKs (C#, Java, Go) a compile-fix loop against local errors reaches working code faster than blocked network research.

## Defaults

Unless the user requests otherwise:

For the Claude model version, please use Claude Opus 5.5, which you can access via the exact model string `claude-opus-5-5`. Please default to using adaptive thinking (`thinking: {type: "adaptive"}`) for anything remotely complicated. And finally, please default to streaming for any request that may involve long input, long output, or high `max_tokens` - it prevents hitting request timeouts. Use the SDK's `.get_final_message()` / `.finalMessage()` helper to get the complete response if you don't need to handle individual stream events. When a streaming request defines user-defined (client) tools, set `eager_input_streaming: true` on each of those tools so large tool inputs (file contents, code, documents) stream as they are generated instead of arriving in one burst after the server finishes buffering them; the client then owns validation: the SDKs' tolerant parsers can return a silently truncated input instead of raising, so validate each parsed tool input against its schema before running it (the typed runner helpers such as `betaZodTool` / typed `@beta_tool` do this; `betaTool()` JSON-Schema tools and manual loops must validate themselves), treat a failure like invalid JSON (`INVALID_JSON` error `tool_result` when you hold the block, re-issue otherwise), check `max_tokens` / `refusal` stop reasons before running tools, and catch only the SDK's JSON error, never its typed API errors - pattern in `shared/tool-use-concepts.md` -> Eager input streaming. Leave it off for non-streaming requests, for server tools, and when the request goes through a proxy or an older Bedrock model deployment that rejects the field.

## Warning: API Drift - Your Training Prior May Be Stale

Several common Claude API shapes changed in 2025-2026. If you recall a pattern from training, verify it against the `{lang}/` files in this skill before writing - the rows below are the most frequent drift points:

| Area | Stale prior | Current API |
|---|---|---|
| Extended thinking | `thinking: {type: "enabled", budget_tokens: N}` | On Claude 4.6+ models: `thinking: {type: "adaptive"}`. `budget_tokens` is deprecated on Opus 4.6 / Sonnet 4.6 and **rejected with a 400** on Fable 5/5.1 / Sonnet 5.5 / Sonnet 5 / Opus 5.5 / 5 / 4.8 / 4.7. Pre-4.6 models still use `budget_tokens`. |
| Web search / web fetch tool type | `web_search_20250305`, `web_fetch_20250910` | `web_search_20260209`, `web_fetch_20260209` (dynamic filtering) on Opus 5.5/5/4.8/4.7/4.6, Sonnet 5.5, Sonnet 5, and Sonnet 4.6. Older models keep the basic variants; on Vertex AI only basic `web_search_20250305` is available (web fetch is not on Vertex) - see the Server Tools QR below. |
| PHP parameter names | snake_case wire names as named args (`max_tokens`) | Top-level named args are camelCase (`maxTokens`). Nested array keys vary by feature (e.g. `'taskBudget'`, `'skillID'`, `'mcp_server_name'`) - copy the exact key from the documented example; do not bulk-convert. |
| Managed Agents credentials | Keep secrets host-side via custom tools (the only option before vaults shipped) | Vault `environment_variable` credentials - stored by Anthropic, substituted at egress, never visible in the sandbox (`shared/managed-agents-tools.md` -> Vaults). Host-side custom tools remain the fallback for self-hosted sandboxes. |
| Files API / Skills | `client.beta.files.*` / `client.beta.skills.*` with beta `files-api-2025-04-14` / `skills-2025-10-02` | Out of beta: `client.files.*` / `client.skills.*`, no beta header. In current SDKs `client.beta.files` / `client.beta.skills` have breaking shape changes from previous versions, matching the stable namespaces - migrate per `shared/live-sources.md` -> Files API / Skills Guide. |

The `{lang}/` files in this skill are authoritative over recalled patterns.

---

## Subcommands

If the User Request at the bottom of this prompt is a bare subcommand string (no prose), search every **Subcommands** table in this document - including any in sections appended below - and follow the matching Action column directly. This lets users invoke specific flows via `/claude-api <subcommand>`. If no table in the document matches, treat the request as normal prose.

| Subcommand | Action |
|---|---|
| `migrate` | Migrate existing Claude API code to a newer model. **Read `shared/model-migration.md` immediately** and follow it in order: Step 0 (confirm scope - ask which files/directories before any edit), Step 1 (classify each file), then the per-target breaking-changes section. Do not summarize the guide - execute it. If the user did not name a target model, ask which model to migrate to in the same turn as the scope question. After the per-target changes are applied, audit the in-scope prompt text, tool descriptions, and request code against `shared/prompt-audit.md` - prompting written for the source model is part of every migration, and it does not announce itself. |
| `prompt-audit` | Audit existing prompts, tool descriptions, skills, and agent configuration files (`CLAUDE.md`, rule files, commands, subagents) for dated patterns ("cruft"): text written for older models, and instructions the repository has outgrown or that contradict each other. **Read `shared/prompt-audit.md` immediately** and follow it in order: Step 0 (establish scope and target model from the request and the repository - state the assumptions in the report, do not stop to ask), inventory, provenance, then the pattern scan. Produce both deliverables in full - the audit report (findings with `file:line`, pattern, why it's obsolete, confidence) and a proposed diff - without pausing for confirmation; apply edits only if the request explicitly asked for them. Do not summarize the guide - execute it. |
| `upgrade` | Upgrade the project's Anthropic SDK dependency across a major version - currently the Python SDK, `anthropic` 0.x -> 1.x. Trailing words may name the language and/or a scope (`upgrade python`, `upgrade python sdk src/`). **Read `python/claude-api/sdk-upgrade.md` immediately** and follow it in order: Step 0 (confirm scope, then establish the current and target versions - a published 1.x must exist before you write a pin), the Step 1 inventory, each numbered section, then verification and the report. Do not summarize the guide - execute it. If the detected or named language has no `sdk-upgrade.md` in this skill, say that no major-version upgrade guide is bundled for that SDK yet and point the user at that SDK's CHANGELOG (repositories in `shared/live-sources.md`); do not improvise one from the Python guide. This is not model migration - to move code to a newer Claude model, use `migrate`. |
| `cost-optimize` | Reduce what existing Claude API code costs to run, without sacrificing output quality. **Read `shared/cost-optimization.md` immediately** and follow it in order: Step 0 (establish scope, quality bar, and baseline), the token profile - measured through the Usage and Cost Admin API when the user has an Admin API key, from the app's own `response.usage` logs when it has those (ask), or estimated from the code otherwise - then a savings-ranked shortlist of levers (quoted in dollars, % of bill, or relative buckets depending on which of those data sources you have), free wins (caching, input-token hygiene, loop hygiene, output-token hygiene, batch) before tradeoffs (budgets, effort, model choice, multi-model); any lever that earns a place becomes its own diff - proposed by default, applied and measured against the eval covering the traffic it touches when the user asks and approves - and "no changes recommended" is a valid outcome. Two standing rules: every run that exercises the model spends real money, so get the user's approval first; and when context for a lever is missing, work through it interactively with the user - this workflow is not expected to one-shot the audit. Do not summarize the guide - execute it; presenting the profile and the ranked plan to the user is part of executing it. |
| `build-eval` | Help the user build an eval set for their Claude-powered app. **Read `shared/evals/build-eval.md` immediately** and run its interview: Step 0 (what's being evaluated), Step 1 (source the prompts - existing eval / transcripts / synthesized), Step 2 (grading method), Step 3 (runnable script + measured cost). Get the user's explicit sign-off on the inputs, the grading method, and the cost before producing the eval. |
| `preserved-thinking-migration` | Make an existing integration compatible with preserved thinking - the check that keeps a thinking block valid only in the conversation that produced it. **Read `shared/preserved-thinking-migration.md` immediately** and follow it in order: Step 0 (scope, traffic classes, platform and model, enforcement status, quality bar, baseline), Step 0.5 (prove the check is running with the three-request self-test), Step 1 (capture request bodies, diff consecutive pairs with `shared/preserved-thinking-migration/prefix_diff.py`, scan the code for the causes, name each edit and whether it is deliberate), Step 2 (replay a test slice with `prefix_mismatch_behavior: "drop_block"` under the `thinking-binding-controls-2026-08-01` header, count new dropped blocks per conversation, read the diagnosis header when present), Step 3 (one cause per diff in order of reasoning lost - proposed by default, applied when the user asks - then re-measure, keep or revert; the three-arm protocol when an eval exists), the model-switch section (in `shared/preserved-thinking-migration/causes.md`, with the cause table and the keep list) when the harness routes between models, Step 4 (the break profile and the changes). Two standing rules: every replay spends real money, so get the user's approval for the measurement budget first; and "no changes recommended" - the slice replayed thinking and nothing was dropped - is a valid outcome. Causes that have an append-only form only under a newer beta (keep-tail and background compaction: `compact-2026-09-04`; same-name tool changes: `inline-tools-2026-09-15`) are, where that beta is not available, measured and decided, not rewritten. For the *why* (the three-step check, the append-only edit table) it chains to `shared/model-migration.md` -> Breaking change 3; do not summarize the guide - execute it. |
| `hillclimb` | Iteratively improve the user's app against an existing eval. **Read `shared/evals/eval-hillclimb.md` immediately** and follow it: Step 0 (confirm a runnable eval exists - if not, route to `build-eval`), Step 1 (what to change / what's off-limits), Step 2 (budget + stopping condition from measured per-run cost), get the plan approved, then the read->propose->apply->run->record loop with on-disk state and a train/validation/test split. |

---

## Language Detection

Before reading code examples, determine which language the user is working in (exception: for the `prompt-audit` subcommand, skip this section's ask steps - the audit is non-interactive and its inventory is language-agnostic; when no language is inferable, proceed without asking and state the assumption in the report):

1. **Look at project files** to infer the language:

 - `*.py`, `requirements.txt`, `pyproject.toml`, `setup.py`, `Pipfile` -> **Python** - read from `python/`
 - `*.ts`, `*.tsx`, `package.json`, `tsconfig.json` -> **TypeScript** - read from `typescript/`
 - `*.js`, `*.jsx` (no `.ts` files present) -> **TypeScript** - JS uses the same SDK, read from `typescript/`
 - `*.java`, `pom.xml`, `build.gradle` -> **Java** - read from `java/`
 - `*.kt`, `*.kts`, `build.gradle.kts` -> **Java** - Kotlin uses the Java SDK, read from `java/`
 - `*.scala`, `build.sbt` -> **Java** - Scala uses the Java SDK, read from `java/`
 - `*.go`, `go.mod` -> **Go** - read from `go/`
 - `*.rb`, `Gemfile` -> **Ruby** - read from `ruby/`
 - `*.cs`, `*.csproj` -> **C#** - read from `csharp/`
 - `*.php`, `composer.json` -> **PHP** - read from `php/`

2. **If multiple languages detected** (e.g., both Python and TypeScript files):

 - Check which language the user's current file or question relates to
 - If still ambiguous, ask: "I detected both Python and TypeScript files. Which language are you using for the Claude API integration?"

3. **If language can't be inferred** (empty project, no source files, or unsupported language):

 - Use AskUserQuestion with options: Python, TypeScript, Java, Go, Ruby, cURL/raw HTTP, C#, PHP
 - If AskUserQuestion is unavailable, default to Python examples and note: "Showing Python examples. Let me know if you need a different language."

4. **If unsupported language detected** (Rust, Swift, C++, Elixir, etc.):

 - Suggest cURL/raw HTTP examples from `curl/` and note that community SDKs may exist
 - Offer to show Python or TypeScript examples as reference implementations

5. **If user needs cURL/raw HTTP examples**, read from `curl/`.

### Language-Specific Feature Support

Every SDK language above supports both the beta Tool Runner and Managed Agents (beta) - Python (`@beta_tool` decorator), TypeScript (`betaZodTool` + Zod), Java (annotated classes), Go (`BetaToolRunner` in the `toolrunner` pkg), Ruby (`BaseTool` + `tool_runner`), C# (`BetaToolRunner` + raw JSON schema), PHP (`BetaRunnableTool` + `toolRunner()`); code entry points are in the Tool Use Patterns quick reference below. cURL is raw HTTP (no SDK features) and supports Managed Agents.

> **Managed Agents code examples**: see the reading guide in the `## Managed Agents (Beta)` section below.

---

## Which Surface Should I Use?

> **Start simple.** Default to the simplest tier that meets your needs. Single API calls and workflows handle most use cases - only reach for agents when the task genuinely requires open-ended, model-driven exploration. "Simplest" means the least code you own: for a hosted, scheduled, or memory-backed agent, Managed Agents is usually the simplest option (no loop code, no state files, no scheduler), even though it's a bigger platform.

| Use Case                                        | Tier            | Recommended Surface       | Why                                                          |
| ----------------------------------------------- | --------------- | ------------------------- | ------------------------------------------------------------ |
| Classification, summarization, extraction, Q&A  | Single LLM call | **Claude API**            | One request, one response                                    |
| Batch processing or embeddings                  | Single LLM call | **Claude API**            | Specialized endpoints                                        |
| Multi-step pipelines with code-controlled logic | Workflow        | **Claude API + tool use** | You orchestrate the loop                                     |
| Custom agent with your own tools                | Agent           | **Claude API + tool use** | Maximum flexibility                                          |
| Server-managed stateful agent with workspace    | Agent           | **Managed Agents**        | Anthropic runs the loop and hosts the tool-execution sandbox |
| Persisted, versioned agent configs              | Agent           | **Managed Agents**        | Agents are stored objects; sessions pin to a version         |
| Long-running multi-turn agent with file mounts  | Agent           | **Managed Agents**        | Per-session containers, SSE event stream, Skills + MCP       |
| Agent that runs on a schedule (cron, "every night") | Agent       | **Managed Agents** - scheduled deployments | Deployments fire sessions autonomously; no client-side scheduler |
| Agent work that must meet a quality bar ("until it's right") | Agent | **Managed Agents** - outcomes | A separate grader iterates the agent against your rubric until it passes |

> **Note:** Managed Agents is the right choice when you want Anthropic to run the agent loop *and* host the container where tools execute - file ops, bash, code execution all run in the per-session workspace. If you want to host the compute yourself or run your own custom tool runtime, Claude API + tool use is the right choice - use the tool runner for the agentic loop - its per-turn hooks still give you approval gates, logging, error interception, and conditional execution (see `shared/tool-use-concepts.md`) - or the manual loop when you want to own the entire loop yourself.

> **Cloud-provider access.** **Claude Platform on AWS** is Anthropic-operated with same-day API parity - see `shared/claude-platform-on-aws.md` for client setup. For per-feature availability on **Claude Platform on AWS**, **Amazon Bedrock**, **Google Vertex AI**, and **Microsoft Foundry**, see `shared/platform-availability.md` - that table is the single source of truth in this skill; do not infer availability from anywhere else.

### Building an Agent: Four Approaches

Once you've decided you actually need an agent (open-ended, model-driven tool use), there are four distinct ways to build one. Two independent questions separate them: **who supplies the harness** (the agent loop + context management) and **who supplies the deployment** (the infra the agent runs on). The Tool Runner and the Claude Agent SDK both supply a *harness only* - you still host and deploy them yourself - which is why they're easy to conflate. Managed Agents (CMA) is the only option that supplies **both** the harness *and* managed deployment; the manual loop supplies neither.

| # | Approach | You write | Harness & deployment | Tools available | Use when |
|---|----------|-----------|----------------------|-----------------|----------|
| 1 | **Claude API - manual loop** | The `while stop_reason == "tool_use"` loop yourself | You build the harness; you host | Only tools you define | You want to own the *entire* loop - no beta dependency, or a control flow the Tool Runner's per-turn hooks don't fit |
| 2 | **Claude API - Tool Runner** (`client.beta.messages.tool_runner` + `@beta_tool` / `betaZodTool`) | Just the tool functions | SDK supplies the loop (**harness only**); you host | Only tools you define | A custom-tool agent without hand-writing the loop (most cases). Per-turn hooks still give you approval gates, error interception, result modification (e.g. `cache_control`), retries, streaming, and compaction |
| 3 | **Managed Agents** (REST, beta) | Agent config + your tool results | Anthropic supplies the harness **and** hosts a per-session sandbox (**harness + deployment**) | Anthropic-hosted sandbox (bash, files, code exec) + Skills/MCP + your tools | You want Anthropic to run the loop *and* host the per-session workspace; persisted/versioned configs; long-running sessions |
| 4 | **Claude Agent SDK** - *separate product* (`claude-agent-sdk` / `@anthropic-ai/claude-agent-sdk`) | A prompt + options | SDK supplies the Claude Code harness + built-in tools (**harness only**); you host | Built-in Read/Write/Edit/Bash/Glob/Grep/WebSearch/WebFetch + MCP + subagents | You want a batteries-included coding/filesystem agent running on your own infra |

The harness/deployment split is the key mental model: options 1, 2, and 4 all **leave deployment to you**; only option 3 (CMA) adds managed deployment. Options 1-3 are what this skill generates; option 4 is a different library with its own docs - see the disambiguation below.

> **Tool Runner != Claude Agent SDK.** These sound alike but are different packages:
> - **Tool Runner** is part of the regular Anthropic API SDK (`anthropic` / `@anthropic-ai/sdk`), reached via `client.beta.messages.tool_runner`. It automates the request -> execute -> loop cycle *for tools you define*. No built-in tools, no filesystem access, no sandbox - you supply every tool and host the compute. It is option 2 above, a thin helper over `POST /v1/messages`.
> - **Claude Agent SDK** (`claude-agent-sdk` / `@anthropic-ai/claude-agent-sdk`) is Claude Code packaged as a library. It ships built-in tools (file read/write/edit, bash, grep, web search), the full agent loop, context management, hooks, subagents, permissions, and sessions. You call `query(prompt, options)` and it drives everything.
>
> Both are **harness-only - you host and deploy them.** The difference is scope of harness: the Tool Runner loops over tools *you* define (with per-turn hooks for approval, interception, result modification, and retries - but no built-in tools); the Agent SDK is the full Claude Code harness with built-in tools. Neither provides managed deployment - that's what **Managed Agents (CMA)** adds (Anthropic hosts the loop and a per-session sandbox).
>
> **This skill covers the Claude API and Managed Agents (options 1-3); it does not generate Claude Agent SDK code.** If the user actually wants the Claude Agent SDK, point them to its docs (`code.claude.com/docs/en/agent-sdk`) - don't substitute the API Tool Runner for it, or vice-versa.

### Should I Build an Agent?

Before choosing the agent tier, check all four criteria:

- **Complexity** - Is the task multi-step and hard to fully specify in advance? (e.g., "turn this design doc into a PR" vs. "extract the title from this PDF")
- **Value** - Does the outcome justify higher cost and latency?
- **Viability** - Is Claude capable at this task type?
- **Cost of error** - Can errors be caught and recovered from? (tests, review, rollback)

If the answer is "no" to any of these, stay at a simpler tier (single call or workflow).

---

## Architecture

Everything goes through `POST /v1/messages`. Tools and output constraints are features of this single endpoint - not separate APIs.

**User-defined tools** - You define tools (via decorators, Zod schemas, or raw JSON), and the SDK's tool runner handles calling the API, executing your functions, and looping until Claude is done. For full control, you can write the loop manually.

**Server-side tools** - Anthropic-hosted tools that run on Anthropic's infrastructure. Code execution is fully server-side (declare it in `tools`, Claude runs code automatically). Computer use can be server-hosted or self-hosted.

**Structured outputs** - Constrains the Messages API response format (`output_config.format`) and/or tool parameter validation (`strict: true`). The recommended approach is `client.messages.parse()` which validates responses against your schema automatically. Note: the old `output_format` parameter is deprecated; use `output_config: {format: {...}}` on `messages.create()`.

**Supporting endpoints** - Batches (`POST /v1/messages/batches`), Files (`POST /v1/files`), Token Counting (`POST /v1/messages/count_tokens` - see `shared/token-counting.md`), and Models (`GET /v1/models`, `GET /v1/models/{id}` - live capability/context-window discovery) feed into or support Messages API requests.

---

## Current Models (cached: 2026-09-25)

| Model             | Model ID            | Context        | Input $/1M | Output $/1M |
| ----------------- | ------------------- | -------------- | ---------- | ----------- |
| Claude Fable 5.1    | `claude-fable-5-1`      | 1M             | $10.00     | $50.00      |
| Claude Mythos 5.1 (Project Glasswing only) | `claude-mythos-5-1` | 1M | $10.00     | $50.00      |
| Claude Fable 5 | `claude-fable-5` | 1M             | $10.00     | $50.00      |
| Claude Opus 5.5 | `claude-opus-5-5` | 1M | $4.00 | $20.00 |
| Claude Opus 5     | `claude-opus-5`       | 1M             | $5.00      | $25.00      |
| Claude Opus 4.8 | `claude-opus-4-8`  | 1M             | $5.00      | $25.00      |
| Claude Opus 4.7   | `claude-opus-4-7`   | 1M             | $5.00      | $25.00      |
| Claude Opus 4.6   | `claude-opus-4-6`   | 1M             | $5.00      | $25.00      |
| Claude Sonnet 5.5 | `claude-sonnet-5-5` | 1M | $2.00 | $10.00 |
| Claude Sonnet 5   | `claude-sonnet-5`   | 1M             | $2.00      | $10.00      |
| Claude Sonnet 4.6 | `claude-sonnet-4-6` | 1M             | $3.00      | $15.00      |
| Claude Haiku 4.5  | `claude-haiku-4-5`  | 200K           | $1.00      | $5.00       |

**Partner pricing:** The prices above are Anthropic first-party API rates - they also apply to Claude on Microsoft Foundry, which is billed through the Microsoft Marketplace at standard API rates. Claude on Amazon Bedrock and Vertex AI is partner-operated with separate pricing - see [Bedrock](https://aws.amazon.com/bedrock/pricing/) or [Vertex AI](https://cloud.google.com/vertex-ai/generative-ai/pricing#claude-models). For WebFetch, use the Pricing row in `shared/live-sources.md`.

**ALWAYS use `claude-opus-5-5` unless the user explicitly names a different model.** This is non-negotiable. Do not use `claude-sonnet-5-5`, `claude-sonnet-5`, or any other model unless the user literally says "use sonnet" or "use haiku". Never downgrade for cost - that's the user's decision, not yours. A request that describes a Sonnet by attribute ("cheapest Sonnet", "cheaper Sonnet", "newest Sonnet", "latest Sonnet") resolves to `claude-sonnet-5-5`. Where a second, cheaper model is in play alongside the main one (worker or sub-agent threads, bulk extractors, LLM judges, the executor under an advisor) - because the user asked for one or a guide in this skill calls for it - or the user says "sonnet" or "haiku" without a version, that means the current generation from the table above (`claude-sonnet-5-5`, `claude-haiku-4-5`); previous-generation IDs such as `claude-sonnet-5` are only for users who name that version. Use `claude-fable-5-1` only when the user explicitly asks for Claude Fable 5.1, "fable", or Anthropic's most capable model - it has different API behavior than the Opus family (see below) and pricing that exceeds Opus-tier. **Use only the exact model ID strings from the table - they are complete as-is; never append date suffixes** (`claude-opus-5-5`, never `claude-opus-5-5-20260401` or any other date-suffixed variant you might recall from training data). If the user requests an older model not in the table (e.g., "opus 4.5", "sonnet 3.7"), read `shared/models.md` for the exact ID - do not construct one yourself.

### Claude Fable 5.1 (`claude-fable-5-1`) - most capable widely released model

Claude Fable 5.1 is Anthropic's most capable widely released model, for the most demanding reasoning and long-horizon agentic work; everything below also applies to **Claude Mythos 5.1** (`claude-mythos-5-1`, Project Glasswing - same capabilities, pricing, and API surface; it runs safeguards that depend on the access program, so the `refusal` handling below applies there too; successor to Claude Mythos 5, which ran no safety classifiers). 1M context window (the maximum is also the default), 128K max output. Key API differences from Opus-tier - see `shared/model-migration.md` -> Migrating to Claude Fable 5.1 for details:

- **Thinking is always on** - omit the `thinking` parameter entirely (or send `{type: "adaptive"}`). Any other explicit configuration is rejected: `{type: "disabled"}` and `{type: "enabled", budget_tokens: N}` both return a 400. Control depth with `output_config.effort` (supports `low` through `xhigh` and `max`).
- **The raw chain of thought is never returned** - responses carry regular `thinking` blocks (not `redacted_thinking`): `display: "summarized"` returns a readable summary, `"omitted"` (the default) leaves the `thinking` field as an empty string. Replay rules: pass thinking blocks back unchanged on the same model; other models drop them silently (unbilled - nothing to strip; Claude Mythos 5.1 instead reads them); details in `shared/model-migration.md`.
- **Tokenizer** - same tokenizer as Opus 4.8 (introduced with Opus 4.7). Token counts are roughly unchanged when migrating from Opus 4.7/4.8; per-token pricing differs. Coming from Opus 4.6, Sonnet, Haiku, or older, re-baseline with `count_tokens` (the Opus 4.7 tokenizer uses ~1×-1.35× as many tokens).
- **`refusal` stop reason - handle it, and opt into fallbacks by default** - safety classifiers may decline a request (HTTP 200, `stop_reason: "refusal"`, with a `stop_details` category); always check `stop_reason` before reading `content`. **When you write `claude-fable-5-1`, `claude-opus-5-5`, `claude-opus-5`, or `claude-sonnet-5-5` code, include the server-side `fallbacks` parameter by default** (for `claude-sonnet-5-5`, only the `"default"` form and only on the Claude API; on other platforms use the SDK middleware below, except when the request sends `between_tools`: only Claude Sonnet 5.5 accepts it and the middleware re-sends the same request body on the fallback model, so write the retry yourself and send it without `between_tools` - see `shared/model-migration.md` -> Migrating to Claude Sonnet 5.5 -> Safeguards and fallback). Simplest form: `betas: ["server-side-fallback-2026-07-01"]` + `fallbacks: "default"`, which routes by refusal category so you never maintain a model list. (The older array form - `betas: ["server-side-fallback-2026-06-01"]` + `fallbacks: [{"model": "claude-opus-4-8"}]` - still works; Claude API and Claude Platform on AWS - on Bedrock, Vertex and Foundry, use the SDKs' client-side `BetaRefusalFallbackMiddleware` + `BetaFallbackState`). Tell the user you've enabled it; drop it only if they decline. Full semantics (billing, mid-stream refusals, credit repricing) in `shared/model-migration.md` -> refusal section. **Per-language code examples in `{lang}/claude-api/README.md` § Refusal Fallbacks cover the array form only** - for the `"default"` mode, follow the raw-HTTP shape in `shared/model-migration.md` -> Migrating to Claude Opus 5 -> New API features and swap `fallbacks: [{...}]` for `fallbacks: "default"` plus the `-2026-07-01` header; the rest of the request is unchanged.
- **No assistant prefill** - same as the rest of the 4.6+ family.
- **30-day data retention required** - Claude Fable 5.1 is not available under zero data retention unless expressly authorized by Anthropic; requests from an org whose retention configuration doesn't meet the requirement return `400 invalid_request_error`.
- **Longer turns, different prompting** - single requests on hard tasks can run many minutes (plan timeouts/streaming/progress UX); effort sweeps should include low/medium for routine work; prompts written for prior models are often too prescriptive and reduce output quality. See `shared/model-migration.md` -> Migrating to Claude Fable 5.1 -> Behavioral shifts (prompt-tunable) for the recommended prompt snippets.
- **Successor to Claude Fable 5 (`claude-fable-5`, still served) in the same tier at the same per-token price.** Same surface as Claude Fable 5 with three breaking changes - forced tool use (`tool_choice` `any` / `tool`) returns a 400 (use `auto` + a prompt instruction, `strict: true` for schema-valid arguments, or structured outputs); thinking blocks are bound to the producing model (other models drop them, unbilled); and editing earlier turns invalidates thinking blocks ("preserved thinking"; new accounts created on/after 2026-08-31 get a 400 on edited history on every platform, and enforcement scope is decided per model, and Claude Mythos 5.1 doesn't run this check. Make every harness append-only and run the three-step check; the opt-in controls beta is on the Claude API, Claude Platform on AWS, Bedrock, and Vertex - Foundry unconfirmed, see `shared/platform-availability.md`) - plus per-message `effort` (beta `mid-conversation-output-config-2026-07-01`, also on Claude Opus 5 and Claude Opus 5.5), turn-scoped `clear_at: "next_user_message"` system messages (beta), `thinking.display: "updates"` progress notes (beta, all platforms), cache reads at $0.25/MTok, and content provenance. Covered Model - ZDR orgs get `400 invalid_request_error` as on Claude Fable 5 (ZDR only if expressly authorized by Anthropic); no Priority Tier. Same tokenizer as Claude Fable 5. See `shared/model-migration.md` -> Migrating to Claude Fable 5.1 from Claude Fable 5.

### Claude Opus 5.5 (`claude-opus-5-5`) - the current Opus and the default model

Successor to Claude Opus 5 in the Opus line at a lower price ($4 / $20 per MTok, cache reads $0.20), same 1M context / 128K output / tokenizer / feature set. Four breaking changes for code running on Claude Opus 5: **thinking can't be disabled** (`{type: "disabled"}` and `budget_tokens` both 400 at every effort level - effort is the only control, and its **default is `medium`**, one level below Claude Opus 5's `high`, so set it explicitly); **forced `tool_choice` `any`/`tool` returns a 400** (use `auto` + `strict: true` and steer from the prompt, or structured outputs); **thinking blocks are tied to the model and the conversation** (preserved thinking: only Claude Fable 5.1 / Claude Mythos 5.1 on the Claude API read its blocks, so a fallback to Claude Opus 5 runs without them; accounts created on or after 2026-08-31 are enforced on the history-editing check); and **on the Claude API and Google Cloud, computer use only through `computer_toolset_20260801`** (`computer_20251124` 400s there; Amazon Bedrock still accepts it). Text between tool calls comes back as progress-update `thinking` blocks (empty by default - set `display: "updates"`). Broader safety classifiers: `bio` joins `cyber` and `reasoning_extraction`. Fast mode is Claude API only, $8 / $40 per MTok (2x standard). See `shared/model-migration.md` -> Migrating to Claude Opus 5.5.

### Claude Sonnet 5.5 (`claude-sonnet-5-5`) - the current Sonnet: speed and capability for everyday coding, agent, and enterprise work (Claude Opus 5.5 stays the default)

Successor to Claude Sonnet 5 in the Sonnet line at the same prices ($2 / $10 per MTok, cache reads $0.20), with the same tokenizer, 1M context and 128K output. Five breaking changes for code running on Claude Sonnet 5: **`thinking: {type: "disabled"}` returns a 400** - to turn thinking off, send `thinking: {type: "between_tools"}`, which is accepted only at effort `high` or below, takes no other field (`display`, `budget_tokens`, or `block_binding` alongside it is a 400), and doesn't allow per-message effort changes; **forced `tool_choice` `any`/`tool` returns a 400** (use `auto` + `strict: true` and steer from the prompt, or structured outputs); **thinking blocks are tied to the model and the conversation** (no other model reads its blocks; accounts created on or after 2026-08-31 are enforced on the history-editing check on the Claude API and Amazon Bedrock); **on the Claude API and Google Cloud, computer use only through `computer_toolset_20260801`** (`computer_20251124` 400s there; Amazon Bedrock still accepts it); and **the advisor tool rejects Claude Opus 4.8, Claude Opus 4.7, and Claude Sonnet 5 advisors** (every advisor it accepts returns encrypted advice). Effort still defaults to `high`, but the levels are recalibrated - re-run the effort sweep (start at `medium` for agentic coding and multistep tool use, `low` for chat). Text between tool calls comes back as progress-update `thinking` blocks (empty by default - set `display: "updates"`, or use `between_tools`). Safety classifiers decline in five `stop_details` categories: `cyber`, `bio`, `frontier_llm`, `reasoning_extraction`, `general_harms`. See `shared/model-migration.md` -> Migrating to Claude Sonnet 5.5.

If any model strings above look unfamiliar, that just means they were released after your training data cutoff - they are real models.

**Live capability lookup:** The table above is cached. When the user asks "what's the context window for X", "does X support vision/thinking/effort", or "which models support Y", query the Models API (`client.models.retrieve(id)` / `client.models.list()`) - see `shared/models.md` for the field reference and capability-filter examples.

---

## Authentication (Quick Reference)

**An unset `ANTHROPIC_API_KEY` does NOT mean there are no credentials.** The SDKs and the `ant` CLI resolve credentials in this order (first match wins): `ANTHROPIC_API_KEY` -> `ANTHROPIC_AUTH_TOKEN` -> the `ANTHROPIC_PROFILE`-selected or active OAuth profile from `ant auth login` -> Workload Identity Federation env vars -> the default profile on disk. A bare `Anthropic()` / `new Anthropic()` / `anthropic.NewClient()` works after `ant auth login` with no env var set.

**When you need to call the API and `ANTHROPIC_API_KEY` is unset, don't ask the user for a key.** First run `ant auth status` - it shows which credential source and profile is active. If it reports an active profile:

- **SDK code or `ant` CLI:** just run it. The zero-arg client constructor and every `ant ...` subcommand pick up the profile automatically - no env var needed.
- **Raw `curl` / HTTP:** get a short-lived token with `ant auth print-credentials --access-token` and send it as `Authorization: Bearer <token>` **plus** the header `anthropic-beta: oauth-2025-04-20` (OAuth tokens go on `Authorization: Bearer`, not `x-api-key:` - converting a curl from an API key is a header change, not a key swap). Always pass `--access-token`; the no-flag form prints JSON, not a bare token.

Only ask the user for a key if `ant auth status` reports no active credential source (or `ant` itself isn't installed). Suggest `ant auth login` as the first option - it stores a profile under `~/.config/anthropic/` that the SDKs read automatically - and an exported `ANTHROPIC_API_KEY` as the alternative.

Full auth details (named profiles, scopes, the API-key-shadows-profile trap, refresh-token expiry): `shared/anthropic-cli.md`.

---

## Thinking & Effort (Quick Reference)

Use adaptive thinking (`thinking: {type: "adaptive"}`) on every current model except Haiku 4.5, which still takes `budget_tokens` (table below) - Claude dynamically decides when and how much to think. Per-model rules:

| Model | Thinking config | Omitting `thinking` | `budget_tokens` | Sampling (`temperature`/`top_p`/`top_k`) | Effort levels |
|---|---|---|---|---|---|
| Fable 5 / Claude Fable 5.1 (and the Mythos counterparts) | `{type: "adaptive"}` or omit; explicit `{type: "disabled"}` returns 400 - omit the param instead (Claude Fable 5.1 / Claude Mythos 5.1 also 400 on forced `tool_choice` `any`/`tool`; Claude Fable 5.1 runs preserved thinking's history-editing check on replayed thinking blocks, Claude Mythos 5.1 does not) | Runs adaptive (thinking is always on) | Removed - `{type: "enabled", budget_tokens: N}` returns 400 | Removed - 400 | `low`/`medium`/`high`/`xhigh`/`max` |
| Claude Opus 5.5 | `{type: "adaptive"}` or omit; `{type: "disabled"}` and `{type: "enabled", budget_tokens}` return 400 at **every** effort level - omit the param and lower effort instead (also 400s on forced `tool_choice` `any`/`tool`, and runs preserved thinking - see `shared/model-migration.md` -> Migrating to Claude Opus 5.5) | Runs **adaptive** | Removed - 400 | Removed - 400 | `low`/`medium`/`high`/`xhigh`/`max` - **default `medium`** (not `high`); per-message effort (beta) supported |
| Claude Opus 5 | `{type: "adaptive"}` or omit; `{type: "disabled"}` accepted **only at effort `high` or below** - 400 at `xhigh`/`max`, and see the disabled-thinking pitfall below | Runs **adaptive** (thinking is on by default - unlike Opus 4.8/4.7) | Removed - 400 | Removed - 400 | `low`-`max` (all five) |
| Opus 4.8 / 4.7 | `{type: "adaptive"}` is the only on-mode; `{type: "disabled"}` accepted | Runs **without** thinking - set `{type: "adaptive"}` explicitly | Removed - 400 | Removed - 400 | `low`/`medium`/`high`/`xhigh`/`max` |
| Claude Sonnet 5.5 | `{type: "adaptive"}` or omit; `{type: "disabled"}` returns 400 - to turn thinking off send `{type: "between_tools"}` (no other field; 400 at `xhigh`/`max`; effort can't change mid-conversation with it) (also 400s on forced `tool_choice` `any`/`tool`, and runs preserved thinking - see `shared/model-migration.md` -> Migrating to Claude Sonnet 5.5) | Runs **adaptive** | Removed - 400 | Non-default values - 400 | `low`/`medium`/`high`/`xhigh`/`max` - default `high`, levels recalibrated from Claude Sonnet 5; per-message effort (beta) supported with thinking on |
| Sonnet 5 | `{type: "adaptive"}` is the only on-mode; `{type: "disabled"}` accepted | Runs adaptive | Removed - 400 | Removed - 400 | `low`/`medium`/`high`/`xhigh`/`max` |
| Opus 4.6 / Sonnet 4.6 | `{type: "adaptive"}` (recommended; auto-enables interleaved thinking, no beta header) | Set `{type: "adaptive"}` explicitly | Deprecated - do not use in new code; transitional escape hatch only (see below) | Allowed | `low`/`medium`/`high`/`max` (`xhigh` arrived with Opus 4.7) |
| Haiku 4.5; older models (Sonnet 4.5, ...) only if explicitly requested | `{type: "enabled", budget_tokens: N}` | No thinking | Required for thinking; must be less than `max_tokens`, minimum 1024 - errors otherwise | Allowed | `effort` works on Opus 4.5 (`low`/`medium`/`high` only - no `xhigh`/`max`); errors on Sonnet 4.5 / Haiku 4.5 |

Opus 4.8 keeps the same request surface as 4.7 (no new breaking changes) - see `shared/model-migration.md` -> Migrating to Opus 4.8 for the behavioral re-tuning, and -> Migrating to Opus 4.7 for the full breaking-change list when coming from 4.6 or earlier. With `thinking` disabled, Opus 4.8 may write longer reasoning into the visible response - leave adaptive thinking on, or add a final-answer-only instruction (see the migration guide).

- **Effort (GA, no beta header):** `output_config: {effort: "low"|"medium"|"high"|"xhigh"|"max"}` - inside `output_config`, not top-level; default `high` (equivalent to omitting it) on every current model except Claude Opus 5.5, whose default is `medium` (thinking table above) - set it explicitly there. Controls thinking depth and overall token spend; combine with adaptive thinking for the best cost-quality tradeoffs. `xhigh` (added on Opus 4.7, between `high` and `max`) is the best setting for most coding and agentic use cases on Fable 5 / Opus 4.7/4.8 / Sonnet 5, and the default in Claude Code; effort matters more on those models than on any prior model in their tier - re-tune it when migrating, and run long-horizon/agentic tasks at `high`/`xhigh` with the full task spec given up front. Use a minimum of `high` for intelligence-sensitive work, `max` when correctness matters more than cost, and `low` for subagents or simple tasks - lower effort means fewer and more-consolidated tool calls, less preamble, and terser confirmations (`high` is often the sweet spot balancing quality and token efficiency).
- **Choosing an effort level (cost tuning):** Effort is the first quality-trading lever, after the free wins (caching first) - it trades thoroughness against token spend within one model, and the top of the range earns its cost only on hard problems (raise to `max` only when measurement shows headroom at the level below). Which workloads repay higher effort is a property of the workload: coding and long-horizon agentic work respond strongly; chat, classification, and high-volume or latency-sensitive routes often don't and do well at `low`, with `medium` as the cost-saving step-down where quality holds (the per-level defaults above cover the rest). Measure on a sample of real requests before raising a default, and tune per route rather than globally. Before building a multi-model cost cascade, measure the simpler alternative first - the most capable model at lower effort on the same tasks: lower effort on the newest models often matches or exceeds prior-generation performance at high effort (on Fable 5, lower effort often exceeds `xhigh` on prior models), and one model means one cache namespace (caches are model-scoped, so a cascade forfeits cache reuse across its models; a mid-conversation top-level `effort` change still invalidates the messages cache, though the per-message effort system message avoids that on Claude Fable 5.1 / Claude Mythos 5.1 / Claude Opus 5.5 / Claude Opus 5 / Claude Sonnet 5.5 (with adaptive thinking) - `shared/prompt-caching.md` § Invalidation hierarchy). Judge cost per completed task, not per request - a cheaper request that needs more turns or retries to finish the job isn't cheaper. For the measured effort/cost tradeoffs by workload and the full lever order, `shared/cost-optimization.md` § 2.6.
- **Thinking display - `"omitted"` by default on Fable 5 / Claude Fable 5.1 / Mythos 5 / Claude Mythos 5.1 / Opus 5.5 / 5 / 4.8 / 4.7 / Sonnet 5 / Claude Sonnet 5.5:** `display: "summarized"` returns a readable summary of the reasoning; `"omitted"` (the default on all ten - a silent change from Opus 4.6 and Sonnet 4.6, where it was `"summarized"`) streams `thinking` blocks with empty text. `display` controls visibility only - thinking happens and is billed the same under every setting; the raw chain of thought is never exposed on any model. If you stream reasoning to users, the default looks like a long pause before output - set `thinking: {type: "adaptive", display: "summarized"}` explicitly. (Independent of display, echo thinking blocks back unchanged when continuing on the same model; other models silently ignore them (Claude Fable 5.1 / Claude Mythos 5.1 read them, and Claude Sonnet 5.5 reads Claude Sonnet 5, Opus 4.8, Haiku 4.5, and earlier models' blocks) - see the migration guide.) On Claude Fable 5.1 / Claude Mythos 5.1 / Claude Fable 5 / Claude Opus 5.5 / Claude Sonnet 5.5, `display: "updates"` (beta `thinking-display-updates-2026-08-18`, every platform) hides reasoning like `"omitted"` but returns the model's between-tool-call progress notes as short `thinking` block summaries - see `shared/model-migration.md` -> Migrating to Claude Fable 5.1 from Claude Fable 5 -> New API features.
- **When the user asks for "extended thinking", a "thinking budget", or `budget_tokens`:** always use Fable 5/5.1, Opus 5.5, 5, 4.8, 4.7, or 4.6 with `thinking: {type: "adaptive"}` - the fixed thinking-token-budget concept is deprecated and adaptive thinking replaces it. Do NOT use `budget_tokens` for new 4.6/4.7/4.8 code and do NOT switch to an older model just because the user mentions it. *Gradual-migration carve-out:* `budget_tokens` is still functional on Opus 4.6 and Sonnet 4.6 only, as a transitional escape hatch for existing code that needs a hard token ceiling before you've tuned `effort` - see `shared/model-migration.md` -> Transitional escape hatch. It is fully removed on Fable 5/5.1, Opus 5.5/5/4.7/4.8, and Sonnet 5.

---

## Compaction (Quick Reference)

**Beta, Fable 5/5.1, Opus 5.5, Opus 5, Opus 4.8, Opus 4.7, Opus 4.6, Sonnet 5.5, Sonnet 5, and Sonnet 4.6.** For long-running conversations that may exceed the 1M context window, enable server-side compaction. The API automatically summarizes earlier context when it approaches the trigger threshold (default: 150K tokens). Requires beta header `compact-2026-01-12`.

**Critical:** Append `response.content` (not just the text) back to your messages on every turn. Compaction blocks in the response must be preserved - the API uses them to replace the compacted history on the next request. Extracting only the text string and appending that will silently lose the compaction state.

See `{lang}/claude-api/README.md` (Compaction section) for code examples. Full docs via WebFetch in `shared/live-sources.md`.

---

## Prompt Caching (Quick Reference)

**Prefix match.** Any byte change anywhere in the prefix invalidates everything after it. Render order is `tools` -> `system` -> `messages`. Keep stable content first (frozen system prompt, deterministic tool list), put volatile content (timestamps, per-request IDs, varying questions) after the last `cache_control` breakpoint.

**Mid-conversation operator instructions** (Claude Opus 5, Claude Opus 5.5, Claude Opus 4.8, Claude Fable 5, Claude Fable 5.1, Claude Mythos 5, Claude Mythos 5.1, Claude Sonnet 5.5; not Claude Sonnet 5; no beta header): append `{"role": "system", ...}` to `messages[]` instead of editing top-level `system`. Preserves the cached history prefix and is the prompt-injection-safe operator channel. See `shared/prompt-caching.md` § Mid-conversation system messages.

**Top-level auto-caching** (`cache_control: {type: "ephemeral"}` on `messages.create()`) is the simplest option when you don't need fine-grained placement. Max 4 breakpoints per request. Minimum cacheable prefix is model-dependent (512-4096 tokens - see `shared/prompt-caching.md` § API reference) - shorter prefixes silently won't cache.

**Verify with `usage.cache_read_input_tokens`** - if it's zero across repeated requests, a silent invalidator is at work (`datetime.now()` in system prompt, unsorted JSON, varying tool set).

For placement patterns, architectural guidance, and the silent-invalidator audit checklist: read `shared/prompt-caching.md`. Language-specific syntax: `{lang}/claude-api/README.md` (Prompt Caching section).

---

## Fast Mode (Quick Reference)

**Research preview, Claude Opus 5 / Claude Opus 5.5 / Opus 4.8 only** - Claude API and Managed Agents, not Bedrock / Google Cloud / Foundry. Opus 4.7 fast mode has been removed: `speed: "fast"` on 4.7 returns an error. Fast mode on Claude Opus 5 is priced at $10 / $50 per MTok; on Claude Opus 5.5, $8 / $40. Fast mode runs the same model at up to 2.5x higher output tokens per second, at premium pricing. Three things are required on every request: use the **beta** messages endpoint (`client.beta.messages....`), pass the beta flag `fast-mode-2026-02-01`, and set `speed: "fast"` as a top-level request parameter (not a header, not in `extra_body`).

```python
client.beta.messages.create(
    model="claude-opus-5-5", max_tokens=4096,
    speed="fast", betas=["fast-mode-2026-02-01"],
    messages=[...],
)
```

| Language | Beta flag | Speed parameter |
|---|---|---|
| Python | `betas=["fast-mode-2026-02-01"]` | `speed="fast"` |
| TypeScript / Ruby | `betas: ["fast-mode-2026-02-01"]` | `speed: "fast"` |
| Go | `[]anthropic.AnthropicBeta{anthropic.AnthropicBetaFastMode2026_02_01}` | `Speed: anthropic.BetaMessageNewParamsSpeedFast` |
| Java | `.addBeta(AnthropicBeta.FAST_MODE_2026_02_01)` | `.speed(MessageCreateParams.Speed.FAST)` |
| C# | `Betas = ["fast-mode-2026-02-01"]` | `Speed = Speed.Fast` (`Anthropic.Models.Beta.Messages`) |
| PHP | `betas: ['fast-mode-2026-02-01']` | `speed: 'fast'` |
| cURL | `anthropic-beta: fast-mode-2026-02-01` header | `"speed": "fast"` in body |

`response.usage.speed` reports which speed was used. Fast mode has its own rate limit separate from standard Opus; on 429, either retry after the `retry-after` delay or drop `speed` and fall back to standard (note: switching speed invalidates prompt cache). Not available with Batch API, Priority Tier, Claude Platform on AWS, or third-party platforms.

**Priority Tier is not supported on every current model.** It is supported on Claude Fable 5, Opus 4.8, and the older current models, but Claude Opus 5.5, Claude Opus 5, Claude Sonnet 5, Claude Sonnet 5.5, Claude Fable 5.1, Claude Mythos 5.1, Claude Mythos 5, and Mythos Preview are excluded - a Priority Tier request naming one of them fails validation.

---

## Task Budgets (Quick Reference)

**Beta, Claude Opus 5 / Claude Opus 5.5 / Fable 5 / Claude Fable 5.1 (confirm at launch) / Claude Sonnet 5.5 / Opus 4.8 / 4.7 (not Claude Sonnet 5).** A task budget gives Claude a token ceiling for an agentic loop so it paces itself and finishes gracefully instead of being cut off - distinct from `max_tokens`, which is an enforced per-response ceiling the model is not aware of. Minimum `total`: 20,000. Set `task_budget` inside `output_config` on `client.beta.messages.stream(...)` with beta flag `task-budgets-2026-03-13` - use streaming so the large `max_tokens` doesn't hit HTTP timeouts (full details: `shared/model-migration.md` -> Task Budgets):

```python
with client.beta.messages.stream(
    model="claude-opus-5-5", max_tokens=128000,
    output_config={"effort": "high", "task_budget": {"type": "tokens", "total": 64000}},
    betas=["task-budgets-2026-03-13"],
    messages=[...], tools=[...],
) as stream:
    response = stream.get_final_message()
```

`task_budget` fields: `type` (always `"tokens"`), `total`, and optional `remaining` (defaults to `total`). The server injects a countdown marker Claude sees during generation; the budget counts what Claude generates and the tool results it reads this turn - **not** the full history you resend each request. Not the same thing as **Managed Agents session budgets** - those are hard, dollar-denominated, platform-enforced caps on one CMA session (`shared/managed-agents-core.md` § Session budgets); a task budget is advisory and token-denominated.

**Observing spend:** accumulate `response.usage.output_tokens` (plus the token count of the tool-result blocks you append) across loop iterations if you want to display progress. Leave `remaining` unset in the normal loop - the server tracks the countdown itself, and passing a client-computed `remaining` while also resending full history under-reports the budget. **Only pass `remaining`** when you compact or rewrite history between requests and the server can no longer derive prior spend.

---

## Provider Clients (Quick Reference)

When targeting Claude on a third-party platform, use that platform's dedicated client class - not the first-party `Anthropic()` client with a `base_url` override. After construction the client exposes the same `messages.create` / `.stream` surface as the first-party SDK.

### Amazon Bedrock

Use the **Mantle** client (Messages-API Bedrock endpoint). Bedrock model IDs take an `anthropic.` prefix (e.g. `"anthropic.claude-opus-5-5"`). Region is required.

| Language | Client |
|---|---|
| Python | `from anthropic import AnthropicBedrockMantle` -> `AnthropicBedrockMantle(aws_region="...")` |
| TypeScript | `import { AnthropicBedrockMantle } from "@anthropic-ai/bedrock-sdk"` -> `new AnthropicBedrockMantle({ awsRegion: "..." })` |
| Go | `bedrock.NewMantleClient(ctx, bedrock.MantleClientConfig{ AWSRegion: "..." })` |
| Java | `AnthropicOkHttpClient.builder().backend(BedrockMantleBackend.fromEnv()).build()` (from `com.anthropic.bedrock.backends`) |
| C# | `new AnthropicBedrockMantleClient(new() { AwsRegion = "..." })` (package `Anthropic.Bedrock`) |
| PHP | `use Anthropic\Bedrock\MantleClient;` -> `new MantleClient(awsRegion: '...')` |
| Ruby | `Anthropic::BedrockMantleClient.new(aws_region: "...")` |

`AnthropicBedrock` / `BedrockClient` / `BedrockBackend` (without `Mantle`) are the legacy `bedrock-runtime` InvokeModel path - prefer the Mantle client for new code.

### Microsoft Foundry

| Language | Client |
|---|---|
| Python | `from anthropic import AnthropicFoundry` -> `AnthropicFoundry(api_key=..., resource="...")` |
| TypeScript | `import AnthropicFoundry from "@anthropic-ai/foundry-sdk"` -> `new AnthropicFoundry({ ... })` |
| Java | `AnthropicOkHttpClient.builder().backend(FoundryBackend.fromEnv()).build()` (from `com.anthropic.foundry.backends`) |
| C# | `new AnthropicFoundryClient(new AnthropicFoundryApiKeyCredentials(...))` (package `Anthropic.Foundry`) |
| PHP | `Foundry\Client::withCredentials(...)` |

The Go and Ruby SDKs do not currently support Foundry. For Ruby, use the standard `Anthropic::Client.new(base_url: "<foundry endpoint>")` as a fallback (Entra ID auth is not built in). For Claude Platform on AWS, see `shared/claude-platform-on-aws.md`.

### Google Cloud Vertex AI

Two required constructor args: GCP `project_id` and `region`. Vertex model IDs take **no prefix** - current-generation models (Opus 5.5/5/4.8/4.7/4.6, Sonnet 5.5, Sonnet 5, Sonnet 4.6) use the bare first-party ID (e.g. `"claude-opus-5-5"`); dated-snapshot models use an `@` version separator (e.g. `claude-opus-4-5@20251101`, **not** `claude-opus-4-5-20251101`). Auth is GCP ADC (`gcloud auth application-default login`); no Anthropic API key. `region` can be `"global"` (recommended), a multi-region (`"us"`/`"eu"`), or a specific region. After construction, use the same `messages.create` / `.stream` surface.

| Language | Client |
|---|---|
| Python | `from anthropic import AnthropicVertex` -> `AnthropicVertex(project_id="...", region="...")` (install `"anthropic[vertex]"`) |
| TypeScript | `import { AnthropicVertex } from "@anthropic-ai/vertex-sdk"` -> `new AnthropicVertex({ projectId, region })` |
| Go | `import "github.com/anthropics/anthropic-sdk-go/vertex"` -> `anthropic.NewClient(vertex.WithGoogleAuth(ctx, region, projectID))` |
| Java | `AnthropicOkHttpClient.builder().backend(VertexBackend.builder().region("...").project("...").build()).build()` (from `com.anthropic.vertex.backends`) |
| C# | `new AnthropicClient { Backend = new VertexBackend(projectId, region) }` (package `Anthropic.Vertex`) |
| PHP | `use Anthropic\Vertex;` -> `Vertex\Client::fromEnvironment(location: '...', projectId: '...')` - note `location`, not `region` |
| Ruby | `Anthropic::VertexClient.new(region: "...", project_id: "...")` |

---

## Context Editing (Quick Reference)

**Beta.** Context editing **clears** old tool results or thinking blocks from the conversation before the model sees it; it is **not compaction** (which summarizes). On `client.beta.messages.*` with beta `context-management-2025-06-27`, pass `context_management.edits` with a strategy type:

```python
client.beta.messages.create(
    model="claude-opus-5-5", max_tokens=4096,
    betas=["context-management-2025-06-27"],
    context_management={"edits": [{"type": "clear_tool_uses_20250919"}]},
    tools=[...], messages=[...],
)
```

Strategy types: `clear_tool_uses_20250919` (clears old tool results; optional `clear_tool_inputs: true` also clears the tool_use params) and `clear_thinking_20251015` (clears thinking blocks). Do **not** use `compact_20260112` or beta `compact-2026-01-12` - those are the separate compaction feature.

---

## Mid-Conversation System Messages (Quick Reference)

**Claude Opus 5, Claude Opus 5.5, Claude Opus 4.8, Claude Fable 5, Claude Fable 5.1, Claude Mythos 5, Claude Mythos 5.1, and Claude Sonnet 5.5; not Claude Sonnet 5; no beta header.** Append `{"role": "system", "content": "..."}` to the `messages` array (not the top-level `system` field) to add an operator instruction mid-conversation without invalidating the cached prefix. Use the regular `client.messages.create` - there is no beta. A mid-conversation system message must follow a `user` message (or an `assistant` message ending in server-tool use), and must be either the last entry in `messages` or be followed by an `assistant` turn - it cannot be `messages[0]`. Availability: `shared/platform-availability.md`. See `shared/prompt-caching.md` § Mid-conversation system messages. A beta extension shipped with Claude Fable 5.1: `output_config: {effort: ...}` with `content: []` changes effort from that point on without a cache reset (beta `mid-conversation-output-config-2026-07-01`; Claude Fable 5.1, Claude Mythos 5.1, Claude Opus 5.5, Claude Opus 5, and Claude Sonnet 5.5 with thinking on; Claude API and Google Cloud). An effort-only message (empty `content`) is exempt from the placement rules above - it can sit anywhere in `messages`, including first or between an assistant turn and the next user turn; the rules apply to text and `clear_at` messages. For a per-turn reminder, give the message `clear_at: "next_user_message"` (beta `mid-conversation-system-clear-at-2026-08-21`): it renders for one turn, then stays in the transcript cleared - never delete earlier copies (on Claude Fable 5.1, Claude Opus 5.5, and Claude Sonnet 5.5 deleting one invalidates later thinking blocks); without the beta, a text block after the tool results, earlier copies kept. See `shared/model-migration.md` -> Migrating to Claude Fable 5.1 from Claude Fable 5 -> New API features.

---

## Managed Agents (Beta)

**Managed Agents** is a third surface: server-managed stateful agents with Anthropic-hosted tool execution. You create a persisted, versioned Agent config (`POST /v1/agents`), then start Sessions that reference it. Each session provisions a container as the agent's workspace - bash, file ops, and code execution run there; the agent loop itself runs on Anthropic's orchestration layer and acts on the container via tools. The session streams events; you send messages and tool results back.

Availability: `shared/platform-availability.md`. For agents on Bedrock / Vertex / Foundry (where Managed Agents is unsupported), use Claude API + tool use.

**Mandatory flow:** Agent (once) -> Session (every run). `model`/`system`/`tools` live on the agent, never the session. See `shared/managed-agents-overview.md` for the full reading guide, beta headers, and pitfalls.

**Beta headers:** `managed-agents-2026-04-01` - the SDK sets this automatically for all `client.beta.{agents,environments,sessions,vaults,deployments,deployment_runs}.*` calls. Memory stores use `agent-memory-2026-07-22` instead, which the SDK sets on `client.beta.memory_stores.*` calls; sending both headers on a memory store request returns a 400. Files API and Skills API are out of beta - no beta header needed (see the API Drift table above for the migration guides).

**Subcommands** - invoke directly with `/claude-api <subcommand>`:

| Subcommand | Action |
|---|---|
| `managed-agents-onboard` | Walk the user through setting up a Managed Agent from scratch. **Read `shared/managed-agents-onboarding.md` immediately** and follow its interview script: **describe -> configure the agent (propose, don't interrogate) -> environment -> session** (same arc as the Console quickstart, auth deferred to the session step) - defaults and inline suggestions do the work, with a silent viability gate (job vs tools/credentials/data) before any code is emitted. Do not summarize - run the interview. |

**Reading guide:** Start with `shared/managed-agents-overview.md`, then the topical `shared/managed-agents-*.md` files (core, environments, tools, events, outcomes, multiagent, webhooks, memory, scheduled-deployments, client-patterns, onboarding, api-reference). For Python, TypeScript, Go, Ruby, PHP, and Java, read `{lang}/managed-agents/README.md` for code examples. For cURL, read `curl/managed-agents.md`. **Agents are persistent - create once, reference by ID.** Define agents and environments as version-controlled files synced with `ant apply` - this is the recommended flow (see `shared/anthropic-cli.md`): the CLI owns the control plane (creating and updating agents), your code owns the data plane (`sessions.create` with the stored agent ID). Call `agents.create()` in code only when you must provision programmatically; either way, store the returned agent ID and pass it to every subsequent `sessions.create`; never call `agents.create()` in the request path. If a binding you need isn't shown in the language README, WebFetch the relevant entry from `shared/live-sources.md` rather than guess. C# has beta Managed Agents support via `client.Beta.Agents` and related namespaces - see `csharp/claude-api/README.md` for details, or `curl/managed-agents.md` for raw HTTP reference.

**When the user wants to set up a Managed Agent from scratch** (e.g. "how do I get started", "walk me through creating one", "set up a new agent"): read `shared/managed-agents-onboarding.md` and run its interview - same flow as the `managed-agents-onboard` subcommand.

**When the user asks "how do I write the client code for X":** reach for `shared/managed-agents-client-patterns.md` - covers lossless stream reconnect, `processed_at` queued/processed gate, interrupt, `tool_confirmation` round-trip, the correct idle/terminated break gate, post-idle status race, stream-first ordering, file-mount gotchas, etc. For credentials, lead with vault `environment_variable` credentials - the first-class mechanism; secrets are substituted at egress and never enter the sandbox (`shared/managed-agents-tools.md` -> Vaults). Keeping credentials host-side via custom tools is the fallback where vault credentials don't fit (e.g. self-hosted sandboxes).

**When the task is a deliverable - default the kickoff to an outcome, not a plain message.** If the session's job is to produce something checkable (an artifact, a report, a PR, a dataset, a fixed set of changes), read `shared/managed-agents-outcomes.md` and kick off with `user.define_outcome` plus a starter rubric you draft from the task (5-10 concrete, independently gradeable criteria; comment it as a starter to tune). Reserve plain `user.message` for genuinely conversational sessions. Trigger on intent, not just the word: "keep working until it's right", "make sure the output is actually good", "don't stop at a first draft" all mean outcomes.

**When the user asks about tool approvals, permission policies, or "auto mode"** (which tool calls need a human, letting the server evaluate calls, `evaluated_permission` / `evaluation` on tool-use events): read `shared/managed-agents-tools.md` § Permission Policies - `always_allow` / `always_ask` / `auto` and the three `auto` outcomes (runs, denied as high-risk, pauses when indeterminate). For attaching a terminal to a live session (`ant beta:sessions connect`): `shared/anthropic-cli.md`.

**When the user wants the agent to run on a schedule** (cron, "every night", "weekly report"): read `shared/managed-agents-scheduled-deployments.md` - deployments fire sessions autonomously on a cron cadence, with per-firing run records and lifecycle controls (pause/unpause/archive).

**When the agent's work fans out** (research across several sources, per-file or per-record work, "look into N things, then summarize") **or one loop would fill its context with reading:** read `shared/managed-agents-multiagent.md` and recommend a multiagent session - start with just `{"type": "self"}` in the roster so the agent can delegate to copies of itself, then move reading-heavy sub-tasks to a cheaper worker agent (e.g. Claude Haiku 4.5, or Claude Sonnet 5.5 when the worker needs more judgment) referenced by ID.

---

## Server Tools (Quick Reference)

Server-side tools run on Anthropic's infrastructure - no client-side execution loop. Declare in `tools`; results arrive as content blocks in the same response. **No beta header** unless noted. **Prefer the latest type variant your model supports.** The `_20260209` web search / web fetch variants below (dynamic filtering) require Opus 5.5/5/4.8/4.7/4.6, Sonnet 5.5, Sonnet 5, or Sonnet 4.6; the basic variants for older models are listed after the table.

| Tool | `type` | `name` | Key optional params | Result block type |
|---|---|---|---|---|
| Web search | `web_search_20260209` | `web_search` | `max_uses`, `allowed_domains`/`blocked_domains`, `user_location` | `web_search_tool_result` -> `.content` is a list of `web_search_result` |
| Web fetch | `web_fetch_20260209` | `web_fetch` | `max_uses`, `allowed_domains`/`blocked_domains`, `citations`, `max_content_tokens` | `web_fetch_tool_result` -> `.content` is a `web_fetch_result` with a `document` block |
| Code execution | `code_execution_20260521` | `code_execution` | none | `bash_code_execution_tool_result` -> `.content.stdout` / `.stderr` / `.return_code` |
| Tool search (regex) | `tool_search_tool_regex_20251119` | `tool_search_tool_regex` | mark other tools `defer_loading: true` | `tool_search_tool_result` |
| Tool search (BM25) | `tool_search_tool_bm25_20251119` | `tool_search_tool_bm25` | mark other tools `defer_loading: true` | `tool_search_tool_result` |

`web_search_20260209` / `web_fetch_20260209` have built-in dynamic filtering - code execution runs under the hood, so do **not** separately declare `code_execution` in `tools` (a second execution environment confuses the model). For models older than Opus 4.6 / Sonnet 4.6, use the basic variants `web_search_20250305` / `web_fetch_20250910` instead; on Vertex AI only basic `web_search_20250305` is available. `code_execution_20260120` (REPL persistence + programmatic tool calling) runs on Opus 4.5+ / Sonnet 4.5+. **Go SDK only**: `code_execution_20260521` lives under `client.Beta.Messages.New` with `Betas: []anthropic.AnthropicBeta{"code-execution-2025-08-25"}` (other languages use plain `client.messages.create`); `code_execution_20260120` uses the non-beta `client.Messages.New` in Go like everywhere else. Web fetch only fetches URLs already present in the conversation. Provider availability varies by tool - see `shared/platform-availability.md`. See `shared/tool-use-concepts.md` for `pause_turn` handling.

## Document & File Input (Quick Reference)

**PDF (base64, no beta):** `{"type": "document", "source": {"type": "base64", "media_type": "application/pdf", "data": <b64 string>}}` in user content, placed before the text block. Base64 string must have no newlines. Limits: 32 MB request, 600 pages (100 for 200k-context models). Java: `ContentBlockParam.ofDocument(DocumentBlockParam... Base64PdfSource.builder().data(...))`.

**Files API (no beta):** upload via `client.files.upload(...)` -> response `id` is the `file_id`. Reference it as `{"type": "document", "source": {"type": "file", "file_id": "..."}}` for PDF/text, or `{"type": "image", ...}` for images - the content-block type must match the file's MIME type. To migrate code off `files-api-2025-04-14`, WebFetch the Files API row in `shared/live-sources.md`. Availability: `shared/platform-availability.md`.

**Citations (no beta):** set `citations: {enabled: true}` on each `document` content block (all or none). Response splits into multiple `text` blocks; cited blocks carry a `citations` array. Each citation has `cited_text`, `document_index`, `document_title`, and a location by `type`: `char_location` (`start_char_index`/`end_char_index`) for plain text, `page_location` (`start_page_number`/`end_page_number`, 1-indexed) for PDF, `content_block_location` for custom content. Incompatible with `output_config.format` (returns a 400).

## Tool Use Patterns (Quick Reference)

**Strict tool use (no beta):** set `strict: true` as a top-level field on the tool definition (alongside `name`/`description`/`input_schema`), **not** on `tool_choice`. Schema must have `additionalProperties: false` + `required`. Guarantees `tool_use.input` validates exactly. Go: `Strict: anthropic.Bool(true)` + `additionalProperties` via `InputSchema.ExtraFields`; Java: `.strict(true)` + `.putAdditionalProperty("additionalProperties", JsonValue.from(false))`.

**Parallel tool use (default on):** one assistant message may contain multiple `tool_use` blocks. Execute them concurrently, then return **all** `tool_result` blocks in a **single** user message - splitting them across multiple messages silently trains Claude to stop making parallel calls. For a failed tool, return `tool_result` with `is_error: true` - don't drop it.

**Tool Runner (SDK beta helper):** drives the tool-call loop for you via `client.beta.messages.*`. Python: `@beta_tool` decorator + `client.beta.messages.tool_runner(...)` -> `runner.until_done()`. TypeScript: `betaZodTool({...})` from `@anthropic-ai/sdk/helpers/beta/zod` + `client.beta.messages.toolRunner(...)` -> `await runner`. Go: `toolrunner.NewBetaToolFromJSONSchema(...)` + `client.Beta.Messages.NewToolRunner(...)` -> `.RunToCompletion(ctx)`. Java requires `.addBeta("structured-outputs-2025-11-13")`. Ruby: `Anthropic::BaseTool` subclass + `client.beta.messages.tool_runner(...)`. PHP: `BetaRunnableTool` + `->toolRunner(...)`. C#: raw JSON-schema tools + `BetaToolRunner` via `client.Beta.Messages.ToolRunner(...)`.

**Programmatic tool calling (no beta header):** Claude calls your custom tool from inside code execution. Add `{"type": "code_execution_20260120", "name": "code_execution"}` **and** set `"allowed_callers": ["code_execution_20260120"]` on your custom tool. Opus 4.5+ / Sonnet 4.5+ (availability: `shared/platform-availability.md`). When responding to a pending programmatic call, the user message must contain **only** `tool_result` blocks (no text). Not compatible with `strict: true`, `disable_parallel_tool_use`, forced `tool_choice`, or MCP tools.

## Other API Surfaces (Quick Reference)

**Message Batches (no beta; availability: `shared/platform-availability.md`):** `client.messages.batches.create(requests=[{custom_id, params}, ...])` -> poll `client.messages.batches.retrieve(id).processing_status` until `"ended"` -> stream `client.messages.batches.results(id)`. Each result has `.custom_id` + `.result.type` (`succeeded`/`errored`/`canceled`/`expired`); on success read `.result.message.content`. Python wraps requests as `Request(custom_id=..., params=MessageCreateParamsNonStreaming(...))`. Results arrive in **any order** - key by `custom_id`, never by position.

**Models API (no beta; availability: `shared/platform-availability.md`):** `client.models.list()` (auto-paginates) and `client.models.retrieve("claude-opus-5-5")`. Each model object has `id`, `display_name`, `created_at`, and - since Mar 2026 - `max_input_tokens` (the context window), `max_tokens` (the output cap), and `capabilities`. There is no `context_window` field.

**Stop details (GA, Opus 4.7+):** `response.stop_details` is populated **only when `stop_reason == "refusal"`** (fields: `type: "refusal"`, `category` - an open set, e.g. `"cyber"`, `"bio"`, `"reasoning_extraction"`, `"frontier_llm"`, or `null`; see the docs for the full list - and `explanation`). It is `null` for every other `stop_reason` (`end_turn`, `max_tokens`, `tool_use`, `pause_turn`, ...) - always guard before reading.

**Admin API (beta, since 2026-08-26):** organization management - members, invites, workspaces and workspace members, API keys, rate limit reports, service accounts, federation issuers/rules, CMEK external keys - under `client.beta.organization` in all seven SDKs and `ant beta:organization` in the CLI. Requires an admin credential: an Admin API key (`sk-ant-admin...`, read from `ANTHROPIC_API_KEY`) or an `org:admin` OAuth token (`ANTHROPIC_AUTH_TOKEN`); regular API keys are rejected. Usage and cost reports and the Claude Enterprise user-management/analytics endpoints are **not** in the SDKs - raw HTTP only. See `shared/admin-api.md`.

**Client config (no beta):** `timeout` default 10 min; **units differ by SDK** - Python/Ruby: seconds; TypeScript: **milliseconds**; Go `option.WithRequestTimeout(time.Duration)`; Java `Duration`; C# `TimeSpan`. TS scales the default up to 60 min for large `max_tokens` on non-streaming requests; Java does so for streaming requests (Java non-streaming scales 30s-10 min). `max_retries`/`maxRetries` default 2 (retries 408/409/429/5xx + connection errors). `base_url` (or `ANTHROPIC_BASE_URL` env). Per-request override: Python `client.with_options(timeout=5.0).messages.create(...)`; TS `client.messages.create({...}, {timeout: 5_000})`; Ruby `request_options: {timeout: 5}`. Timeouts are retried - wall-clock can reach `timeout × (max_retries+1)`.

## Workload Identity Federation (Quick Reference)

**GA, no beta header.** Construct the normal zero-arg client (`Anthropic()` / `new Anthropic()` / `anthropic.NewClient()` / `AnthropicOkHttpClient.fromEnv()`); the SDK auto-detects WIF when **all** of `ANTHROPIC_FEDERATION_RULE_ID`, `ANTHROPIC_ORGANIZATION_ID`, `ANTHROPIC_SERVICE_ACCOUNT_ID`, and `ANTHROPIC_IDENTITY_TOKEN_FILE` (or `ANTHROPIC_IDENTITY_TOKEN`) are set, exchanges the JWT at `/v1/oauth/token`, and auto-refreshes. `ANTHROPIC_WORKSPACE_ID` does not gate activation - required only when the federation rule spans multiple workspaces (else 400 `workspace_id_required`), optional for single-workspace rules. `ANTHROPIC_API_KEY` or `ANTHROPIC_AUTH_TOKEN` (even empty) outrank WIF, and a set `ANTHROPIC_PROFILE` also wins over the federation env vars (a missing named profile is an error, not a fall-through) - unset all three.

---

## Reading Guide

After detecting the language, read the relevant files based on what the user needs. Every `{lang}/...`, `shared/...`, and `curl/...` path cited in this document is relative to this skill's base directory, and none of those files' content is included above - Read each one on demand before relying on what it covers.

**All SDK languages use the same multi-file layout** - directory `{lang}/claude-api/` containing `README.md` (install, client init, basic request, thinking, caching, stop details, misc), `tool-use.md` (tool definitions, agentic loop, Anthropic-defined tools, structured outputs), `streaming.md`, `batches.md`, `files-api.md`. Not every language has every file (e.g., Ruby has no `batches.md`); if a file is absent, that feature's example is not yet documented for that language - fall back to the cURL shape or WebFetch the SDK repo from `shared/live-sources.md`. **cURL** -> `curl/examples.md`.

The Quick Task Reference below uses the `{lang}/claude-api/FILE.md` path notation for all languages.

### Quick Task Reference

**Single text classification/summarization/extraction/Q&A:**
-> Read only `{lang}/claude-api/README.md` - **always read the README first** for any task (installation, quick start, common patterns, error handling)

**Chat UI or real-time response display:**
-> Read `{lang}/claude-api/README.md` + `{lang}/claude-api/streaming.md`

**Long-running conversations (may exceed context window):**
-> Read `{lang}/claude-api/README.md` - see Compaction section
**Migrating to a newer model (Sonnet 5.5 / Opus 5.5 / Fable 5.1 / Fable 5 / Opus 5 / Opus 4.8 / Opus 4.7 / Opus 4.6 / Sonnet 5 / Sonnet 4.6), replacing a retired model, or translating `budget_tokens` / prefill patterns to the current API:**
-> Read `shared/model-migration.md`
**Upgrading the Anthropic SDK package itself across a major version (`anthropic` 0.x -> 1.x: `httpx2`, awaited async `.with_raw_response`, removed deprecated parameters / aliases / Text Completions, Python >= 3.10) - or writing new code against a project already on 1.x:**
-> Read `{lang}/claude-api/sdk-upgrade.md` (currently Python only; other SDKs have no bundled major-version guide yet - use that SDK's CHANGELOG via `shared/live-sources.md`)
**Building an eval set for a Claude app (or "how do I know if my change helped"):**
-> Read `shared/evals/build-eval.md` - it loads `shared/evals/eval-audit.md` (the health checklist every eval must satisfy) before Step 0.
**Checking whether an existing eval is trustworthy ("is my eval any good?"):**
-> Read `shared/evals/eval-audit.md` and run it against the eval; report per its section 6.
**Iteratively improving an app against an eval (prompt tuning, hill-climbing):**
-> Read `shared/evals/eval-hillclimb.md` - runs Step 0 -> Step 5 with a train/test split; test is scored every round and is the headline.
**Rendering an eval-hillclimb HTML report:**
-> Run `shared/evals/report/build-report.mjs` when it is on disk (EAP install), else `shared/evals/report/build-report-lite.mjs` (always extracted with this skill) - both consume the `_state.json` / `vN/` layout produced by the hillclimb guide and write the same `trajectory/scores.tsv`. Don't write a parallel one.
**Migrating to, prompting, or tuning Claude Opus 5.5 (thinking can't be disabled, effort tuning and the `medium` default, forced tool use, computer toolset, progress updates, safeguard false positives, visual inputs / design outputs):**
-> Read `shared/model-migration.md` -> Migrating to Claude Opus 5.5; the preserved-thinking mechanics it points at are under Migrating to Claude Fable 5.1 from Claude Fable 5
**Migrating to, prompting, or tuning Claude Sonnet 5.5 (`between_tools` instead of disabled thinking, recalibrated effort, forced tool use, computer toolset, advisor pairings, progress updates, tool use in chat, mid-turn user messages, verification at low effort, safeguard categories):**
-> Read `shared/model-migration.md` -> Migrating to Claude Sonnet 5.5
**Prompting or tuning Fable 5/5.1 (long turns, effort, verbosity, autonomous runs, sub-agents):**
-> Read `shared/model-migration.md` -> Migrating to Claude Fable 5.1 -> Behavioral shifts (prompt-tunable) + Long-running agent recommendations
**Prompting or tuning Claude Fable 5.1 (progress updates, parallel tool calls, writing density / formatting, autonomy, test sprawl, whole-file rewrites) or making a harness compatible with preserved thinking's history-editing check (history edits, compaction, per-turn reminders):**
-> Read `shared/model-migration.md` -> Migrating to Claude Fable 5.1 from Claude Fable 5 -> New API features + Behavioral shifts (prompt-tunable); for the history-editing check itself (the three-step check, the append-only edit table, compaction shapes), Breaking change 3 in the same section; to find, measure and fix the edits an *existing* harness makes (capture, diff, replay with `drop_block`, one fix per cause, model switches), run `preserved-thinking-migration` (Subcommands table) - it reads `shared/preserved-thinking-migration.md`
**Prompt caching / optimize caching / "why is my cache hit rate low":**
-> Read `shared/prompt-caching.md` (prefix-stability design, breakpoint placement, anti-patterns that silently invalidate cache) + `{lang}/claude-api/README.md` (Prompt Caching section)
**Auditing or cleaning up prompts, tool descriptions, skills, or agent configuration files such as `CLAUDE.md` ("is this prompt outdated", "remove the cruft", "this was written for an older model"):**
-> Read `shared/prompt-audit.md` - dated-pattern tables with greppable signals, the keep list (what NOT to delete), and the report + proposed-diff output contract
**Count tokens in a file / prompt / diff ("how many tokens is X"):**
-> Read `shared/token-counting.md` - use `messages.count_tokens`, never `tiktoken`
**Reducing or reviewing API spend ("the bill is too high", "make this cheaper", "am I overspending", cost per completed task, cheapest model or effort that holds quality):**
-> Read `shared/cost-optimization.md` - baseline and token profile first, then the levers in order (free wins before tradeoffs) with measured expectations, and a workload-shape -> lever mapping table

**Function calling / tool use / agents:**
-> Read `{lang}/claude-api/README.md` + `shared/tool-use-concepts.md` (conceptual foundations: function calling, code execution, memory, structured outputs) + `{lang}/claude-api/tool-use.md` (language-specific code examples: tool runner, manual loop, code execution, memory, structured outputs)

**Agent design (tool surface, context management, caching strategy):**
-> Read `shared/agent-design.md` (bash vs. dedicated tools, programmatic tool calling, tool search/skills, context editing vs. compaction vs. memory, caching principles)

**Batch processing (non-latency-sensitive; runs asynchronously at 50% cost):**
-> Read `{lang}/claude-api/README.md` + `{lang}/claude-api/batches.md`

**File uploads across multiple requests (same file without re-uploading):**
-> Read `{lang}/claude-api/README.md` + `{lang}/claude-api/files-api.md`

**Organization administration (members, invites, workspaces, API keys, rate limit reports, service accounts, WIF resources, CMEK):**
-> Read `shared/admin-api.md` - `client.beta.organization` endpoint/method table, admin credentials, per-language naming and pagination, what stays curl-only

**Debugging HTTP errors or implementing error handling:**
-> Read `shared/error-codes.md` - per-SDK typed exception class table and the Go `errors.As` pattern

**Latest official documentation:**
-> WebFetch the URLs in `shared/live-sources.md`

**Managed Agents (server-managed stateful agents with workspace):**
-> See the reading guide in the `## Managed Agents (Beta)` section above - it lists every `shared/managed-agents-*.md` file and the language-specific READMEs (`{lang}/managed-agents/README.md`, `curl/managed-agents.md`).

---

## When to Use WebFetch

Use WebFetch to get the latest documentation when:

- User asks for "latest" or "current" information
- Cached data seems incorrect
- User asks about features not covered here

Live documentation URLs are in `shared/live-sources.md`.

## Common Pitfalls

- Don't truncate inputs when passing files or content to the API. If the content is too long to fit in the context window, notify the user and discuss options (chunking, summarization, etc.) rather than silently truncating.
- **Prefill removed (Fable 5, Claude Fable 5.1, Opus 5, Claude Opus 5.5, Sonnet 5, Claude Sonnet 5.5, and the 4.6/4.7/4.8 family):** Assistant message prefills (last-assistant-turn prefills) return a 400 error on Fable 5, Claude Fable 5.1, Opus 5, Claude Opus 5.5, Sonnet 5, Claude Sonnet 5.5, Opus 4.6, Opus 4.7, Opus 4.8, and Sonnet 4.6. Use structured outputs (`output_config.format`) or system prompt instructions to control response format instead. (One exception: the fallback-credit prefill claim - when redeeming a credit with `fallback_has_prefill_claim: true`, the server accepts the echoed assistant message; see the migration guide's refusal section.)
- **Confirm migration scope before editing:** When a user asks to migrate code to a newer Claude model without naming a specific file, directory, or file list, **ask which scope to apply first** - the entire working directory, a specific subdirectory, or a specific set of files. Do not start editing until the user confirms. Imperative phrasings like "migrate my codebase", "move my project to X", "upgrade to Sonnet 4.6", or bare "migrate to Opus 4.8" are **still ambiguous** - they tell you what to do but not where, so ask. Proceed without asking only when the prompt names an exact file, a specific directory, or an explicit file list ("migrate `app.py`", "migrate everything under `services/`", "update `a.py` and `b.py`"). See `shared/model-migration.md` Step 0.
- **`max_tokens` defaults:** Don't lowball `max_tokens` - hitting the cap truncates output mid-thought and requires a retry. For non-streaming requests, default to `~16000` (keeps responses under SDK HTTP timeouts). For streaming requests, default to `~64000` (timeouts aren't a concern, so give the model room). Only go lower when you have a hard reason: classification (`~256`), cost caps, deliberately short outputs, or **`max_tokens: 0`** for cache pre-warming (see `shared/prompt-caching.md` -> Pre-warming).
- **Disabling thinking on Claude Opus 5 has two failure modes - prefer low/medium effort instead.** (On Claude Opus 5.5 it can't be disabled at all - `{type: "disabled"}` is a 400 at every effort level; use `low` effort. On Claude Sonnet 5.5, `{type: "disabled"}` is also a 400 - try thinking on at `low` effort first, and if a route must stay thinking-off, send `{type: "between_tools"}` at `high` effort or below.) Only affects code that explicitly opts out; thinking is on by default, so watch for a disabled-thinking setting carried forward from Opus 4.8. With `thinking: {type: "disabled"}`, the model occasionally writes a tool call into its **visible text** instead of a `tool_use` block: the turn succeeds, the call never runs, no error is raised, and in an agentic loop that text pollutes later turns. It can also leak `<thinking>` tags into the response. Turning thinking on and lowering `effort` fixes both and still cuts cost. If a route must stay thinking-off: **delete** any don't-think/don't-reason rule (it makes tag leakage worse), don't name thinking tags, and add the combined instruction *"When you use a tool, you may say a brief sentence first. If no tool can express what the user asked for, say so instead of guessing. Do not include internal or system XML tags in your response."* Details: `shared/model-migration.md` -> Two failure modes when thinking is disabled.
- **128K output tokens:** Fable 5, Claude Fable 5.1, Opus 5, Claude Opus 5.5, Opus 4.6, Opus 4.7, Opus 4.8, Claude Sonnet 5.5, Sonnet 5, and Sonnet 4.6 support up to 128K `max_tokens`, but the SDKs require streaming for values that large to avoid HTTP timeouts. Use `.stream()` with `.get_final_message()` / `.finalMessage()`.
- **Forced tool use removed (Claude Fable 5.1 / Claude Mythos 5.1 / Claude Opus 5.5 / Claude Sonnet 5.5):** `tool_choice: {type: "any"}` and `{type: "tool", name: ...}` return a 400 (`tool_choice: type "tool" and "any" are not supported for this model.`), on `count_tokens` and Batches too. Use `{type: "auto"}` plus an explicit instruction naming the tool, `strict: true` on the tool to keep schema-valid arguments, or structured outputs (`output_config.format`) when the forced call only existed to get JSON back. `{type: "none"}` is unaffected; `disable_parallel_tool_use` still works with `auto` (at most one call).
- **Tool call JSON parsing (Fable 5, Claude Fable 5.1, Opus 5, Claude Opus 5.5, and the 4.6/4.7/4.8 family):** Fable 5, Claude Fable 5.1, Opus 5, Claude Opus 5.5, Opus 4.6, Opus 4.7, Opus 4.8, and Sonnet 4.6 may produce different JSON string escaping in tool call `input` fields (e.g., Unicode or forward-slash escaping). Always parse tool inputs with `json.loads()` / `JSON.parse()` - never do raw string matching on the serialized input.
- **Structured outputs (all models):** Use `output_config: {format: {...}}` instead of the deprecated `output_format` parameter on `messages.create()`. This is a general API change, not 4.6-specific.
- **Don't reimplement SDK functionality:** The SDK provides high-level helpers - use them instead of building from scratch. Specifically: use `stream.finalMessage()` instead of wrapping `.on()` events in `new Promise()`; use typed exception classes (`Anthropic.RateLimitError`, etc.) instead of string-matching error messages; use SDK types (`Anthropic.MessageParam`, `Anthropic.Tool`, `Anthropic.Message`, etc.) instead of redefining equivalent interfaces.
- **Error handling - catch a chain, not one broad class.** A single `except APIStatusError` / `catch (AnthropicServiceException)` / `rescue APIError` loses the distinction between retryable (429, >=500, network) and non-retryable (400/404) failures. Write a most-specific-first chain - e.g. `NotFoundError` -> `RateLimitError` -> `APIStatusError` -> `APIConnectionError` (or the Go equivalent: `errors.As` into `*anthropic.Error` then `switch apierr.StatusCode { case 404: ...; case 429: ...; default: ... }`). Per-language class names and namespaces are in `shared/error-codes.md`.
- **Don't research SDK types - write first.** If a type name isn't shown in the documentation included in this skill, write the code file from the namespace/package tables in the language-specific doc and let the compiler's error point you to the right name. Do not spend turns on WebFetch, SDK-repo clones, or compiling-and-running a separate reflection program to discover type names before writing - produce the source file first, then fix what the compiler reports. A quick `strings` / `jar tf` / `javap` against the installed SDK is acceptable for locating names (it returns in seconds), but don't escalate beyond that. A file with a wrong type name is recoverable; a session spent on discovery with no file written is not.
- **Bash and text editor tools are Anthropic-defined, schema-less.** Declare `{"type": "bash_20250124", "name": "bash"}` / `{"type": "text_editor_20250728", "name": "str_replace_based_edit_tool"}` - no `input_schema`. A custom tool with your own schema named `"bash"` is a different tool. Handler paths and security checks are in `shared/tool-use-concepts.md` § Client-Side Tools.
- **Advisor tool model pairing.** The advisor tool's `model` must be at least as capable as the request's top-level `model` - e.g. executor `claude-sonnet-5-5` -> advisor `claude-opus-5-5`. An invalid pair returns 400; a `claude-sonnet-5-5` executor accepts only the advisors its row in the pairing table lists (not Claude Opus 4.8 / 4.7 / 4.6, Claude Sonnet 5, or Sonnet 4.6). Pairing table (and which advisors return plaintext vs encrypted `advisor_redacted_result` advice) in `shared/tool-use-concepts.md` § Advisor. Availability: `shared/platform-availability.md`.
- **Agent Skills != Managed Agents.** To have Claude generate a `.pptx`/`.xlsx`/etc. via Agent Skills, call `client.beta.messages.create` with `container={"skills": [...]}`, the `code_execution_20260521` tool, and the `code-execution-2025-08-25` beta (Skills is out of beta - no `skills-2025-10-02` header needed). Do not use `client.beta.agents` / `sessions` / `environments` here - those are the Managed Agents surface, not Agent Skills.
- **MCP connector needs both halves.** `mcp_servers=[{type:"url", url, name}]` alone is rejected as a validation error - also add `tools=[{type:"mcp_toolset", mcp_server_name:<same name>}]` with beta `mcp-client-2025-11-20`. Availability: `shared/platform-availability.md`.
- **`inference_geo` is a direct top-level request parameter** - `client.messages.create(..., inference_geo="us")` / `.inferenceGeo("us")`. Do not put it in `extra_body` / `putAdditionalBodyProperty`. (Messages API only - on Managed Agents, `inference_geo` instead nests inside the agent's `model` object, never top-level; see `shared/managed-agents-core.md` § Pinning inference geography.) Supported on Opus 4.6 / Sonnet 4.6 and later; availability: `shared/platform-availability.md`. `response.usage.inference_geo` reports where inference ran.
- **Fine-grained tool streaming is not a beta feature; this skill's default is to turn it on for streaming + client tools (the API itself still defaults to buffered).** Set `eager_input_streaming: true` on the tool definition and call the regular `client.messages.stream(...)`. There is no beta header and no `client.beta.*` path. Do not also send the legacy `fine-grained-tool-streaming-2025-05-14` beta header. Python's `@beta_tool(eager_input_streaming=True)` accepts it directly; TypeScript's `betaZodTool()` does not, so spread it on: `{ ...betaZodTool({...}), eager_input_streaming: true }`. With the field on, the API no longer coerces or validates the input, so the accumulated `partial_json` may be incomplete (`max_tokens`) or invalid - guard the parse (`shared/tool-use-concepts.md` -> Eager input streaming).
- **Cache diagnostics is beta.** Use `client.beta.messages.*` with beta `cache-diagnosis-2026-04-07`. Pass `diagnostics: {previous_message_id: null}` on the first turn and `diagnostics: {previous_message_id: <previous response id>}` on subsequent turns; the result is on `response.diagnostics`. Availability: `shared/platform-availability.md`.
- **Memory tool type is `memory_20250818`.** Declare `{"type": "memory_20250818", "name": "memory"}`. Go uses the beta-namespace type `{OfMemoryTool20250818: &anthropic.BetaMemoryTool20250818Param{}}` on `client.Beta.Messages.New`; Python/TypeScript/Ruby/PHP/C# use the non-beta `client.messages.create`; Java has both a non-beta `MemoryTool20250818` and a beta tool-runner path. Python/TypeScript provide `BetaAbstractMemoryTool` / `betaMemoryTool` helpers for implementing the backend.
- **Use a model the feature actually supports.** Some features are restricted to specific model tiers - fast mode is Claude Opus 5 / Claude Opus 5.5 / Opus 4.8 only (and Claude API only), task budgets (Messages API only - Managed Agents session budgets have no model-tier restriction) are Claude Opus 5 / Claude Opus 5.5 / Fable 5 / Claude Fable 5.1 (confirm at launch) / Claude Sonnet 5.5 / Opus 4.8 / 4.7 only (not Claude Sonnet 5), and the advisor tool requires a valid executor<->advisor pair. If the user's prompt names a model that the feature doesn't support, use a supported model instead and note the substitution in the output.
- **Don't define custom types for SDK data structures:** The SDK exports types for all API objects. Use `Anthropic.MessageParam` for messages, `Anthropic.Tool` for tool definitions, `Anthropic.ToolUseBlock` / `Anthropic.ToolResultBlockParam` for tool results, `Anthropic.Message` for responses. Defining your own `interface ChatMessage { role: string; content: unknown }` duplicates what the SDK already provides and loses type safety.
- **Report and document output:** For tasks that produce reports, documents, or visualizations, the code execution sandbox has `python-docx`, `python-pptx`, `matplotlib`, `pillow`, and `pypdf` pre-installed. Claude can generate formatted files (DOCX, PDF, charts) and return them via the Files API - consider this for "report" or "document" type requests instead of plain stdout text.
- **Server-tool errors don't raise.** Web search and web fetch errors return HTTP 200 with a `web_search_tool_result` / `web_fetch_tool_result` block whose `content` is a single error object (e.g. `{error_code: "max_uses_exceeded"}`) - not a raised exception. For web search, a success `content` is a *list*; an error `content` is an *object* - branch on that before indexing.
- **Managed Agents web tools ignore the environment's `networking`.** `web_search` / `web_fetch` run on Anthropic's servers in cloud *and* self-hosted environments, and Console org-level web settings apply to the Messages API only. Restrict them per tool with `allowed_domains` **or** `blocked_domains` (never both; 1-64 plain hostnames per list, subdomains covered; IPs, bare TLDs, single-label and `localhost`-style names rejected on both tools; a path suffix is allowed only on `web_search`) on the toolset `configs` entry - `shared/managed-agents-tools.md` § Web search & web fetch settings.
- **Eval / hillclimb work has dedicated guides:** If the user says "hillclimb", "improve my eval score", "iterate on my prompt against an eval", or "build me an eval" - load `shared/evals/eval-hillclimb.md` or `shared/evals/build-eval.md` rather than improvising. The bundled HTML report builder is `shared/evals/report/build-report.mjs` when it is on disk (EAP install), else `shared/evals/report/build-report-lite.mjs` (always extracted with this skill); don't write a parallel one.
- **Code execution output block type:** `code_execution_20260521` returns `bash_code_execution_tool_result` (with `.content.stdout`), **not** the legacy bare `code_execution_tool_result`. Iterate `response.content` and match on the correct type.
- **Tool search: never defer everything.** The search tool itself must not have `defer_loading: true`, and at least one tool in `tools` must be non-deferred, or the API returns 400 `All tools have defer_loading set`.

No project language was auto-detected. Ask the user which language they are using (see Language Detection above), then Read the matching `{lang}/claude-api/README.md` (or `curl/examples.md` for cURL/raw HTTP or an unsupported language) from the base directory before anything else.

## User Request

Planning (no code yet) a Python 3.11 harness using anthropic SDK 1.8.0 (pinned) for structured JSON extraction from freight invoices/contracts/emails, plus vision on one scanned PDF page. Need: current model IDs and per-token pricing for the cheapest capable model and a stronger fallback, whether SDK 1.8.0 supports structured outputs / tool-use JSON schema, prompt caching specifics (min tokens, pricing), PDF/image input, and rate-limit/retry behaviour, so I can estimate cost per 1,000 documents.


**Claude:** The project is Python (`harness/harness.py`), so I'll read the Python SDK reference: structured outputs, PDF/image input, caching and errors.


- `Bash`: List Python and shared skill reference files

- `Read`: C:\Users\arnav\AppData\Local\Temp\claude\bundled-skills\2.1.289\200cb8222f91befd0fe9fd0bea1369aa\claude-api\python\claude-api\README.md


- `Grep`: (?i)structured output|messages\.parse|output_config|json_schema

- `Read`: C:\Users\arnav\AppData\Local\Temp\claude\bundled-skills\2.1.289\200cb8222f91befd0fe9fd0bea1369aa\claude-api\python\claude-api\tool-use.md


- `Grep`: (?i)minimum|min.*cacheable|1\.25|2x|write.*cost|ttl

- `Grep`: (?i)temperature|sampling

- `Read`: C:\Users\arnav\AppData\Local\Temp\claude\bundled-skills\2.1.289\200cb8222f91befd0fe9fd0bea1369aa\claude-api\shared\prompt-caching.md



- `Write`: C:\Users\arnav\AppData\Local\Temp\claude\c--Users-arnav-OneDrive-Desktop-Nova\b290e15b-ef2f-42f6-87a6-f74f4b560165\scratchpad\sdkcheck.py

- `Bash`: Check SDK structured-output support and document sizes



- `Bash`: Create docs folder and check pydantic version


- `Write`: C:\Users\arnav\OneDrive\Desktop\Nova\docs\PLAN.md


**Claude:** I'll fix a few things in the file that would break Mermaid rendering (angle-bracket placeholders and semicolons inside diagram text) and one garbled phrase.


- `Edit`: C:\Users\arnav\OneDrive\Desktop\Nova\docs\PLAN.md

- `Edit`: C:\Users\arnav\OneDrive\Desktop\Nova\docs\PLAN.md

- `Edit`: C:\Users\arnav\OneDrive\Desktop\Nova\docs\PLAN.md

- `Edit`: C:\Users\arnav\OneDrive\Desktop\Nova\docs\PLAN.md

- `Edit`: C:\Users\arnav\OneDrive\Desktop\Nova\docs\PLAN.md

- `Edit`: C:\Users\arnav\OneDrive\Desktop\Nova\docs\PLAN.md


**Claude:** Next, a muddled sentence in section 5 about when a missing document can't change the answer. I'll rewrite it to match the glossary's rule.


- `Edit`: C:\Users\arnav\OneDrive\Desktop\Nova\docs\PLAN.md

- `Bash`: Check PLAN.md size, sections and repo status



- `Write`: C:\Users\arnav\.claude\projects\c--Users-arnav-OneDrive-Desktop-Nova\memory\nova-env-wsl.md

- `Write`: C:\Users\arnav\.claude\projects\c--Users-arnav-OneDrive-Desktop-Nova\memory\nova-project-context.md

- `Bash`: Add memory index entries to MEMORY.md


**Claude:** I've written the plan to [docs/PLAN.md](docs/PLAN.md), with all 15 sections and 5 Mermaid diagrams. No harness code is written yet.

Written for: you, as the build spec for the coding phases.

**Setup:** `make setup` failed here because `make` isn't installed on Windows. Even with it, the Makefile expects a Unix-style `.venv/bin/python`. I ran the same command unchanged in WSL Ubuntu and it worked. CI also runs on Ubuntu, so from now on every `make` command goes through WSL.

**Summary**
1. **The split:** Claude reads each document into typed facts, each tied to a page and line in the grader's own text. Plain Python does every date window, precedence decision and Decimal calculation. No names, lanes or layouts are hardcoded; the same name is a key account manager in practice but the pricing manager in the exam.
2. **Pipeline:** `ingest` (parse, OCR or vision, classify, extract, verify) → a SQLite fact store → one rules module per class → action and mode policy → confidence → report. Every report recomputes from scratch, so file order can't change an answer.
3. **Exam gate:** I hand-calculated the expected exam answers (Appendix A, not GoComet's key). Total savings come to $8,165.33: 9 findings, 1 expiry alert, 1 conflict on CDU-3051302 and 1 missing-document case on CDU-3051286 ("Annex A rev 2").
4. **Checks behind it:** my arithmetic reproduces 5 published practice answers to the cent.
5. **Scans:** both mailboxes have one; the exam's carries an $85.46 overcharge. Local OCR reads them well but turns "I" into "1" in invoice ids, so ids get cross-checked against the email subject and the AP register.
6. **Temperature 0 isn't available:** `claude-opus-5-5` rejects `temperature`, and the pinned SDK 1.8.0 doesn't even accept the parameter. Repeatability comes from schema-constrained output, a cache keyed by content hash, and a check that every extracted number appears in its source line.
7. **Cost:** about $38 per 1,000 documents on Opus 5.5 (about $19 on Sonnet 5.5), and about 57 minutes per 1,000 with 8 parallel calls. Each step has a time budget and carries unfinished documents over to the next command.
8. **Prompt injection:** the model only fills extraction fields and can't choose verdicts or actions. Authority comes from exact Schedule 1 email addresses, report items never contain email addresses, and pay, settle or accept actions don't exist in the code.
9. **Feedback:** stored either as scoped facts or as rules tied to one exact key. One-off decisions never spread to other keys. `learned_at` is set by comparing each report with and without feedback.
10. **Phases (about 16h):** skeleton → ingest → rules plus the exam check → modes → feedback → 20 eval cases → confidence → hardening → docs. The exam check comes third, before modes, feedback and evals.

**Questions worth emailing GoComet**
1. When a paid invoice is re-sent asking for payment, does it count twice in the rebate spend? This changes the exam Q3 rebate from 4,307.34 to 4,469.10.
2. What is the hidden per-step time limit, and does their API proxy cap parallel requests or reject beta headers?
3. Which Schedule 1 contact receives an autonomous credit claim: billing disputes, or the key account manager?
4. Does the "pickup date must come from tracking" check apply when the amount doesn't depend on the pickup date, such as a paid-invoice resend or a late fee?
5. For a waiver seen only in a forward, what counts as the missing document's "name exactly as cited"?

**Decisions for you**
- **Model:** Opus 5.5 (my default) or Sonnet 5.5 for extraction, at roughly half the cost?
- **Exam oracle:** commit Appendix A and `docs/exam_oracle_sheet.json`, or keep them local and out of git?
- **Working copy:** move it into the WSL filesystem? It would be faster, and OneDrive would stop syncing the Linux `.venv`.

I'm stopping here until you give the go-ahead.


## Prompt 3 (2026-10-09 05:56:33 UTC)

<pasted_content id="6518">
Go ahead with the plan in docs/PLAN.md, with these decisions:

1. WORKING COPY. Before writing code: clone my private repo fresh into the WSL filesystem (~/nova-takehome), with
   `git config core.autocrlf input`, and copy docs/PLAN.md across. From here on, work only there. Nothing lives
   under OneDrive.

2. MODELS. Make them configurable through environment variables with these defaults:
   NOVA_MODEL_CONTRACT=claude-opus-5-5 for MSAs, amendments, annexes, rate notices and Schedule 1;
   NOVA_MODEL_DOC=claude-sonnet-5-5 for invoices, emails, statements, ledgers and tracking.
   Use one client wrapper with retries, backoff on 429/overloaded, and the per-step time budget.

3. EXAM ORACLE. Move Appendix A and the oracle sheet into local/ and add local/ to .gitignore. The harness must
   never read anything in local/, data/*/answers or data/examples/*/expected_finding.json. Add
   tools/check_no_hardcoding.py: it fails if any invoice id, contract id, AWB, lane code or person name that
   appears in data/ also appears in harness/. Run it in `make eval`. When the harness disagrees with the oracle, go
   back to the documents and the glossary to find which one is wrong, fix the general rule or fix the oracle, and
   never special-case.

4. ASSUMPTIONS. I'm not contacting GoComet. Resolve every ambiguity yourself, in this order:
   (1) the GLOSSARY text, (2) the worked examples, (3) the practice answer key, used as evidence about how a rule
   is read, never copied into code, (4) otherwise the conservative reading. Wrongly disputed money costs double,
   so when in doubt, don't dispute. Implement every assumption behind one clearly named constant in
   harness/config.py, record it in docs/ASSUMPTIONS.md (the question, the reading chosen, the evidence, the
   one-line change if wrong), and keep going without stopping.
   Settle these specifically:
   a) Re-sent paid invoice in rebate spend, once or twice. Test both readings against the practice key: the
      2035-Q1 rebate is a finding of 4450.07, 2035-Q2 is no_finding, and TX-US-2035-0232 (dated 2035-06-24) is a
      paid invoice re-sent. Keep the reading that reproduces both. If both do, count it once (same invoice
      number), and re-run the exam oracle under the chosen reading.
   b) Unattended-action check 1 (pickup date from tracking or a carrier "picked up" email). The practice key gives
      execute:dispute in autonomous mode for late_fee_not_owed (sc-3874a142, sc-bff95595) and for the DU-01
      resends. Check whether those shipments' pickup dates actually come from tracking. If not, the check applies
      only when the pickup date decides the amount. Implement whichever reading the key supports.
   c) Per-step time limit: assume 300s, configurable (NOVA_STEP_BUDGET_S), with carry-over. Report must never
      silently skip unextracted documents: if any are pending, extract them within report's own budget first.
   d) Missing-doc names: the grader's names_match needs our name to CONTAIN every distinctive token of theirs. So
      write descriptive names: the document as cited, plus its sender, date and the AWB or invoice it covers.
   e) Credit-claim recipient: use the Schedule 1 billing-disputes contact consistently.
   Summarise docs/ASSUMPTIONS.md in SOLUTION.md ("What doesn't") and in DESIGN.md ("What I'd do next").

5. ROBUSTNESS. The grader starts with an empty state dir, so the hash cache doesn't help there. If an extraction
   fails the "every number appears in its source line" check, re-extract once with the validation errors fed back.
   On a scanned page, if the line items don't sum to the printed total, read that page with Claude vision.

6. WORKFLOW. Work through the phases in order. After each phase: run `make grade` (and `make sheet` from phase 3
   on), commit with a clear message, and append a 3-line note to docs/PROGRESS.md (what changed, the score, what
   broke). Stop and report to me at two checkpoints: when the phase 3 exam sheet is compared with the oracle, and
   when everything is done. Between checkpoints, only stop for decisions that are genuinely mine.
</pasted_content id="6518">


**Claude:** Starting with the working copy. I need your private repo's URL, so I'll look for it first: git remotes, then the GitHub CLI.


- `Bash`: Check git remotes and GitHub CLI in WSL

- `Bash`: List the user's GitHub repositories



- `Bash`: Check whether Anthropic credentials are set in WSL and Windows

- `Write`: C:\Users\arnav\AppData\Local\Temp\claude\c--Users-arnav-OneDrive-Desktop-Nova\b290e15b-ef2f-42f6-87a6-f74f4b560165\scratchpad\envcheck.sh

- `Bash`: Check WSL for Anthropic credentials without printing them



- `Write`: C:\Users\arnav\AppData\Local\Temp\claude\c--Users-arnav-OneDrive-Desktop-Nova\b290e15b-ef2f-42f6-87a6-f74f4b560165\scratchpad\setup_wc.sh

- `Bash`: Clone fresh working copy in WSL and run make setup



- `Read`: \\wsl.localhost\Ubuntu\home\arnav\nova-takehome\.gitignore



- `Bash`: Show lines of the late-fee and resend practice invoices


**Claude:** Practice has a second invoice layout too (TX-US-2035-0265 didn't match the first one's pattern). I'll check whether these shipments' AWBs appear as PICKED_UP in the tracking exports.


- `Bash`: Show second-layout invoice and tracking pickup rows



- `Write`: \\wsl.localhost\Ubuntu\home\arnav\nova-takehome\harness\config.py


**Claude:** Next the text layer, a verbatim copy of the grader's reader functions plus line-numbered rendering for prompts:


- `Write`: \\wsl.localhost\Ubuntu\home\arnav\nova-takehome\harness\nova\textlayer.py


**Claude:** Now the money helpers (Decimal, half-up only) and date parsing:


- `Write`: \\wsl.localhost\Ubuntu\home\arnav\nova-takehome\harness\nova\money.py


**Claude:** Now the SQLite state store:


- `Write`: \\wsl.localhost\Ubuntu\home\arnav\nova-takehome\harness\nova\state.py


**Claude:** Now the mailbox reader, which produces document rows in the grader's `doc` format:


- `Write`: \\wsl.localhost\Ubuntu\home\arnav\nova-takehome\harness\nova\mailbox.py



- `Write`: \\wsl.localhost\Ubuntu\home\arnav\nova-takehome\harness\nova\llm.py



- `Write`: \\wsl.localhost\Ubuntu\home\arnav\nova-takehome\harness\nova\schemas.py


**Claude:** Now the prompts. They describe meaning only; the few examples are invented values that don't appear in either mailbox.


- `Write`: \\wsl.localhost\Ubuntu\home\arnav\nova-takehome\harness\nova\prompts.py



- `Write`: \\wsl.localhost\Ubuntu\home\arnav\nova-takehome\harness\nova\verify.py


**Claude:** Now OCR: rapidocr locally first, lines rebuilt from box positions; Claude vision is the fallback when line items don't sum to the printed total.


- `Write`: \\wsl.localhost\Ubuntu\home\arnav\nova-takehome\harness\nova\ocr.py


**Claude:** Now the extraction orchestrator: classify, route to the right model and schema, verify, re-extract once with errors fed back, handle scans, and parse spreadsheet tables in Python.


- `Write`: \\wsl.localhost\Ubuntu\home\arnav\nova-takehome\harness\nova\extract.py


**Claude:** Now the `ingest` command:


- `Write`: \\wsl.localhost\Ubuntu\home\arnav\nova-takehome\harness\nova\ingest.py


**Claude:** Now `harness.py`. The argparse block stays exactly as shipped, so `validate.py`'s command-line check still sees the same flags; only the three bodies change.


- `Read`: \\wsl.localhost\Ubuntu\home\arnav\nova-takehome\harness\harness.py

- `Edit`: \\wsl.localhost\Ubuntu\home\arnav\nova-takehome\harness\harness.py

- `Write`: \\wsl.localhost\Ubuntu\home\arnav\nova-takehome\harness\nova\__init__.py


**Claude:** Now the `feedback` command. It's strict parsing with no LLM, and a malformed item is logged and skipped, never fatal:


- `Write`: \\wsl.localhost\Ubuntu\home\arnav\nova-takehome\harness\nova\feedback.py


**Claude:** Now a minimal `report` for Phase 0. It prints a schema-valid report and never crashes; Phase 2 fills in the rules.


- `Write`: \\wsl.localhost\Ubuntu\home\arnav\nova-takehome\harness\nova\report.py


**Claude:** Next, moving the exam oracle out of the tracked plan into `local/` (gitignored):


- `Write`: C:\Users\arnav\AppData\Local\Temp\claude\c--Users-arnav-OneDrive-Desktop-Nova\b290e15b-ef2f-42f6-87a6-f74f4b560165\scratchpad\move_oracle.py

- `Bash`: Move oracle to local/, build oracle sheet, gitignore local/



- `Write`: \\wsl.localhost\Ubuntu\home\arnav\nova-takehome\tools\check_no_hardcoding.py


**Claude:** Now the Makefile: `make eval` runs the hardcoding check first. I'll also add a small WSL run helper that picks up the API key from your interactive shell once you've set it.


- `Edit`: \\wsl.localhost\Ubuntu\home\arnav\nova-takehome\Makefile

- `Write`: C:\Users\arnav\AppData\Local\Temp\claude\c--Users-arnav-OneDrive-Desktop-Nova\b290e15b-ef2f-42f6-87a6-f74f4b560165\scratchpad\wrun.sh

- `Bash`: Install run helper and run the hardcoding check


**Claude:** The check works: it collected 125 ids, 182 AWBs, 57 lanes and 109 names, and the harness is clean. The key still isn't visible. Next the Makefile edit; my edit tool wants a read first.


- `Read`: \\wsl.localhost\Ubuntu\home\arnav\nova-takehome\Makefile

- `Edit`: \\wsl.localhost\Ubuntu\home\arnav\nova-takehome\Makefile


**Claude:** Next, the dev-only test dependency (pytest pinned in `requirements-dev.txt`) and the text-layer parity test:


- `Bash`: Verify Makefile tabs and install pinned pytest

- `Write`: \\wsl.localhost\Ubuntu\home\arnav\nova-takehome\tests\test_textlayer.py

- `Write`: \\wsl.localhost\Ubuntu\home\arnav\nova-takehome\tests\test_money.py

- `Bash`: Run unit tests and validate the empty report and CLI



- `Edit`: \\wsl.localhost\Ubuntu\home\arnav\nova-takehome\harness\nova\llm.py

- `Write`: \\wsl.localhost\Ubuntu\home\arnav\nova-takehome\docs\ASSUMPTIONS.md

- `Write`: \\wsl.localhost\Ubuntu\home\arnav\nova-takehome\docs\PROGRESS.md


**Claude:** Now `make grade` for Phase 0. With the empty report, a low score is expected; this checks the plumbing.


- `Bash`: Run make grade on the Phase 0 skeleton

- `Bash`: Show top of the Phase 0 report card


**Claude:** Phase 0 scores 0.0/100 as expected for an empty report, and all five hard gates are clear. I'll log it in PROGRESS.md and commit.


- `Write`: C:\Users\arnav\AppData\Local\Temp\claude\c--Users-arnav-OneDrive-Desktop-Nova\b290e15b-ef2f-42f6-87a6-f74f4b560165\scratchpad\commit.sh

- `Bash`: Append progress note and commit Phase 0


**Claude:** Phase 0 is committed (`c689c3d`). Phase 1 needs real extraction calls, so I'll check whether the API key has appeared.


- `Bash`: Check whether the API key is now available



- `Write`: \\wsl.localhost\Ubuntu\home\arnav\nova-takehome\harness\nova\world.py


**Claude:** Two fixes in `world.py`. First, a label-ordering bug: "Storage programme fee" would map to *storage* rather than the monthly programme fee. Second, a muddled boolean in the feedback authority check.


- `Edit`: \\wsl.localhost\Ubuntu\home\arnav\nova-takehome\harness\nova\world.py

- `Edit`: \\wsl.localhost\Ubuntu\home\arnav\nova-takehome\harness\nova\world.py

- `Edit`: \\wsl.localhost\Ubuntu\home\arnav\nova-takehome\harness\nova\world.py

- `Edit`: \\wsl.localhost\Ubuntu\home\arnav\nova-takehome\harness\nova\world.py

- `Edit`: \\wsl.localhost\Ubuntu\home\arnav\nova-takehome\harness\nova\world.py



- `Write`: \\wsl.localhost\Ubuntu\home\arnav\nova-takehome\harness\nova\terms.py


**Claude:** Now the `Outcome` type that every rule module returns:


- `Write`: \\wsl.localhost\Ubuntu\home\arnav\nova-takehome\harness\nova\outcome.py



- `Write`: \\wsl.localhost\Ubuntu\home\arnav\nova-takehome\harness\nova\rules\overcharge.py


**Claude:** Now the duplicate rule: a paid invoice re-sent asking for payment, plus the same shipment line (AWB + Annex E code + quantity) billed on two invoice numbers.


- `Write`: \\wsl.localhost\Ubuntu\home\arnav\nova-takehome\harness\nova\rules\duplicate.py


- `Edit`: \\wsl.localhost\Ubuntu\home\arnav\nova-takehome\harness\nova\world.py

- `Edit`: \\wsl.localhost\Ubuntu\home\arnav\nova-takehome\harness\nova\world.py

- `Edit`: \\wsl.localhost\Ubuntu\home\arnav\nova-takehome\harness\nova\rules\duplicate.py

- `Edit`: \\wsl.localhost\Ubuntu\home\arnav\nova-takehome\harness\nova\rules\duplicate.py



- `Write`: \\wsl.localhost\Ubuntu\home\arnav\nova-takehome\harness\nova\rules\waiver.py


**Claude:** Now late fees: "not owed" recomputes the fee from the paid date, the authorised extended due date, grace and compounding; "risk" flags open invoices falling due within 14 days.


- `Write`: \\wsl.localhost\Ubuntu\home\arnav\nova-takehome\harness\nova\rules\late_fees.py


**Claude:** Now cashback: rebates and promised credits per closed period, with qualifying spend computed from the contract's own definition and credit notes already issued subtracted.


- `Write`: \\wsl.localhost\Ubuntu\home\arnav\nova-takehome\harness\nova\rules\cashback.py


**Claude:** Now expiry: the end date, or the non-renewal notice deadline for an auto-renewing contract, moved by any signed extension.


- `Write`: \\wsl.localhost\Ubuntu\home\arnav\nova-takehome\harness\nova\rules\expiry.py

- `Write`: \\wsl.localhost\Ubuntu\home\arnav\nova-takehome\harness\nova\rules\__init__.py


**Claude:** Now `policy.py`: the action matrix per mode, the five-check unattended test, the $5,000 sum per invoice or cashback key, the open-conflict index, and the confidence formula.


- `Write`: \\wsl.localhost\Ubuntu\home\arnav\nova-takehome\harness\nova\policy.py



- `Edit`: \\wsl.localhost\Ubuntu\home\arnav\nova-takehome\harness\nova\rules\waiver.py

- `Write`: \\wsl.localhost\Ubuntu\home\arnav\nova-takehome\harness\nova\evaluate.py



- `Edit`: \\wsl.localhost\Ubuntu\home\arnav\nova-takehome\harness\nova\evaluate.py

- `Write`: \\wsl.localhost\Ubuntu\home\arnav\nova-takehome\harness\nova\report.py

- `Bash`: Import check, run ingest/report without key, tests and hardcoding check



- `Write`: \\wsl.localhost\Ubuntu\home\arnav\nova-takehome\tests\test_rules.py

- `Bash`: Run the synthetic rules tests



- `Bash`: Check whether the API key is now available


**Claude:** Still no key. I'll commit the rules engine and tests as a work-in-progress commit (no phase note, since Phase 1 isn't accepted yet), then stop, because the key is the one thing only you can provide.


- `Bash`: Run tests and commit the rules engine work in progress

**Claude:** I'm stopped: there's no Anthropic API key anywhere I can reach, and every remaining phase needs real Claude calls. I checked WSL's environment, your shell config files, `~/.config/anthropic` and Windows. The code for those phases is written; it just can't be run or scored yet.

**To unblock:** in your own WSL terminal, run:
```
echo 'export ANTHROPIC_API_KEY=sk-ant-...' >> ~/.bashrc
```
Add `ANTHROPIC_BASE_URL` the same way if you use one, and please don't paste the key here. My commands load it from your shell automatically, so once it's set just tell me to continue. I'll re-run Phase 1 and Phase 2 for real, and stop at the agreed checkpoint where the exam sheet is compared with the oracle.

**What's done, in `~/nova-takehome` on branch `nova-harness`:**
- **Working copy:** your account has no private `nova-takehome` repo, so I cloned the public template instead (`core.autocrlf input`, original remote renamed `upstream`). Nothing is pushed, and creating the private repo is still to do. One side effect: a template fix landed in `Makefile` (`make eval` now runs the hardcoding check first).
- **Phase 0, committed as `c689c3d`:** `make grade` scores 0.0/100, as expected with empty reports, and all five hard gates are clear. The command-line check and schema validation pass.
- **Phase 1 code is written but has never made a real call.**
  - One Claude client handles structured output, a cache keyed by content hash, backoff on rate limits and overloads, and the 300s step budget (`NOVA_STEP_BUDGET_S`).
  - Models are set by `NOVA_MODEL_CONTRACT`/`NOVA_MODEL_DOC`. The grader passes only `ANTHROPIC_*` variables through, so under `make grade` the defaults always apply.
  - Extraction is re-run once if a number doesn't appear in its cited line. Scans are read by local OCR, falling back to Claude vision when line items don't add up to the printed total. `report` finishes any unread documents within its own budget first, and warns rather than skipping them silently.
- **Phase 2 code (WIP commit `5f65d0c`):** the fact view, rate resolver, the six class rules, the action policy with the unattended test, confidence, evidence quotes, ids/supersedes/retro, and the outbox. 13 unit tests on an invented contract pass without any API calls.
- **Exam oracle:** moved to `local/`, which is gitignored. `tools/check_no_hardcoding.py` collects 125 ids, 182 AWBs, 57 lanes and 109 names from `data/` and finds none of them in `harness/`.

**Assumptions so far** (every one is a named constant, with an entry in `docs/ASSUMPTIONS.md`):
- **(b) unattended check 1:** every practice key you pointed to has a tracking pickup row, so the answer key can't tell the two readings apart. I took the conservative one: the check applies to every shipment in a finding. Switching is one constant.
- **(c), (d), (e):** implemented as you specified.
- **(a) re-sent invoice in rebate spend:** still to test. It needs real extractions to compute 2035-Q1 and Q2 both ways.


## Prompt 4 (2026-10-09 07:01:29 UTC)

<pasted_content id="6518">
The API key is now set in ~/.bashrc (ANTHROPIC_API_KEY, no base URL). Continue the build, with these rules.

0. VERIFY. Make one tiny API call to confirm the key works. Never print, log or commit the key.

1. BUDGET. I have $20 of API credit in total, and it's a hard limit.
   - Keep a running cost ledger in local/api_spend.json (gitignored), updated after every call from the token
     counts in the response, and print the cumulative total at the end of every command.
   - Spend in this order: about $2 tuning extraction on data/examples/, about $6 for the first full practice and
     exam pass, then re-extraction only when a prompt changes. Keep $5 in reserve for the final uncached
     make grade + make sheet run.
   - STOP and ask me before any run that would push cumulative spend past $15.

2. CHEAP DEVELOPMENT.
   - Add an optional NOVA_CACHE_DIR (dev only, e.g. ~/.nova_cache) so extractions are shared across runs, modes
     and state dirs. When it isn't set, behave exactly as the grader expects.
   - While developing, use claude-sonnet-5-5 for every document type (export NOVA_MODEL_CONTRACT for your
     shell). The code defaults stay as planned (Opus for contracts) for the final runs and for grading.
   - Use at most 4 parallel calls, since a new account has low rate limits; the backoff handles 429s.
   - Debug rules, arithmetic and report logic against cached extractions. Re-extract a document only when its
     extraction is actually wrong, and then only that document.

3. ORDER OF WORK.
   a) Run Phase 1 for real on data/examples/ first, and compare the output with each expected_finding.json.
      Fix extraction prompts there, where runs cost cents.
   b) Then run the full practice mailbox (make grade) and the exam mailbox (make sheet).
   c) Settle assumption (a): compute the 2035-Q1 and 2035-Q2 rebates both ways from the real extractions, keep
      the reading that reproduces the practice key (Q1 = 4450.07 finding, Q2 = no_finding), and update
      docs/ASSUMPTIONS.md and the exam oracle to match.
   d) Continue through the phases in PLAN.md.

4. REPO. Add <YOUR-PRIVATE-REPO-URL> as origin, then push main and nova-harness. Before every push, check that
   nothing under local/, no .nova_cache, no state dir and nothing that looks like an API key is staged.
   Push after each phase.

5. CHECKPOINTS. Same as before: after each phase, commit, push, and add a note to docs/PROGRESS.md (what changed,
   the score, what broke, spend so far). Stop and report to me:
   - when the phase 3 exam sheet has been compared with the oracle: show every difference, and for each one
     say whether the harness or the oracle is wrong and why, with the document line that proves it;
   - when everything is done;
   - before crossing $15 of spend.
</pasted_content id="6518">


**Claude:** The key is set. Before the first call I'll wire in your budget rules. Three of them interact with how the grader runs the harness, which changes the implementation slightly:

- **The grader strips the environment.** `run_grader.py` passes only `PATH`, `HOME`, `TMPDIR` and `ANTHROPIC_*` to the harness, and sets `HOME` to a fresh folder. So a shell-exported `NOVA_CACHE_DIR` or `NOVA_MODEL_CONTRACT` would never reach the harness under `make grade`. To make the dev cache and Sonnet override actually apply there, `config.py` also reads `NOVA_*` values from a gitignored `.nova_dev.env` at the repo root, and only when that file exists. The grading container won't have it, so the defaults (Opus for contracts, no cache) apply there.
- **The spend ledger lives in `local/`**, but the harness must not reference `local/`. Its path comes from `NOVA_SPEND_LEDGER` in that dev file, and a hard stop (`NOVA_SPEND_LIMIT=15`) blocks any call once the total reaches $15.
- **The 4-call limit** needs a global semaphore, because contract extraction runs its own inner pool.

**One gap:** your message says to add `<YOUR-PRIVATE-REPO-URL>` as origin, but the placeholder wasn't filled in, and your GitHub account has no such repo. I'll keep committing locally. Send the URL whenever you like and I'll push after the next phase, running the safety checks first.


- `Write`: \\wsl.localhost\Ubuntu\home\arnav\nova-takehome\harness\nova\spend.py

- `Edit`: \\wsl.localhost\Ubuntu\home\arnav\nova-takehome\harness\config.py

- `Edit`: \\wsl.localhost\Ubuntu\home\arnav\nova-takehome\harness\config.py



- `Edit`: \\wsl.localhost\Ubuntu\home\arnav\nova-takehome\harness\nova\llm.py

- `Edit`: \\wsl.localhost\Ubuntu\home\arnav\nova-takehome\harness\nova\llm.py

- `Edit`: \\wsl.localhost\Ubuntu\home\arnav\nova-takehome\harness\nova\llm.py

- `Edit`: \\wsl.localhost\Ubuntu\home\arnav\nova-takehome\harness\nova\llm.py

- `Edit`: \\wsl.localhost\Ubuntu\home\arnav\nova-takehome\harness\nova\llm.py


**Claude:** Next, the dev settings file and gitignore entries, then one tiny API call to confirm the key works. It's recorded in the ledger, and the key is never printed.


- `Write`: C:\Users\arnav\AppData\Local\Temp\claude\c--Users-arnav-OneDrive-Desktop-Nova\b290e15b-ef2f-42f6-87a6-f74f4b560165\scratchpad\ping.py

- `Bash`: Create dev settings file and make one tiny API call



- `Bash`: Search the SDK for workspace header support

- `Bash`: Inspect SDK workspace handling in the client



- `Edit`: \\wsl.localhost\Ubuntu\home\arnav\nova-takehome\harness\nova\llm.py

- `Edit`: C:\Users\arnav\AppData\Local\Temp\claude\c--Users-arnav-OneDrive-Desktop-Nova\b290e15b-ef2f-42f6-87a6-f74f4b560165\scratchpad\ping.py

- `Bash`: Re-run tests and confirm nothing was spent

**Claude:** I'm stopped again: your key works, but it's an organization-level key, and the API rejects every request that doesn't say which workspace to bill:

> This API key is not scoped to a workspace, so this request must include the anthropic-workspace-id header with the ID of the workspace to use.

Nothing was charged, so the ledger is still at $0.

**Pick one fix, both in your own terminal (don't paste the key here):**
1. **Recommended: a workspace-scoped key.** In the Anthropic Console, create an API key inside a workspace and replace the one in `~/.bashrc`. This is the only fix that also works for GitHub Actions and any other runner that passes just the key.
2. **Keep this key and give me the workspace id.** Run `echo 'NOVA_WORKSPACE_ID=wrkspc_...' >> ~/nova-takehome/.nova_dev.env`; the id isn't a secret. It has to go in that file rather than in `ANTHROPIC_WORKSPACE_ID`, because `make grade` passes only `ANTHROPIC_API_KEY` and `ANTHROPIC_BASE_URL` to the harness.

The harness already sends the header whenever either variable is set, so either fix works without further code changes. Then just say "continue". I'll re-run the one-call key check, then work through the examples (~$2), the first full practice and exam pass (~$6), and the rest of your order, stopping at the agreed checkpoints and before $15.

**Done since your last message (uncommitted, will go in with Phase 1):**
- **Spend ledger:** `harness/nova/spend.py` keeps a running cost in `local/api_spend.json` and refuses to start any call once the total reaches $15. That `local/` path lives only in the gitignored dev file, so the harness code never names `local/`.
- **Dev settings file:** `.nova_dev.env` (gitignored, absent in grading) sets the shared cache at `~/.nova_cache`, Sonnet for every document type, and at most 4 parallel calls. It's needed because the grader strips shell environment variables, so your exports would never reach the harness under `make grade`.
- **Cheaper Sonnet calls:** thinking is switched off on Sonnet for extraction (it's copying, not reasoning), with an automatic fallback if the API refuses that setting.

**Repo:** your message still has the `<YOUR-PRIVATE-REPO-URL>` placeholder and you have no such GitHub repo yet. Send the URL with your reply; before any push I'll check that nothing under `local/`, no cache, no state dir and no key is staged.


## Prompt 5 (2026-10-09 07:24:51 UTC)

<pasted_content id="6518">
Continue with option 1: ~/.bashrc now has a workspace-scoped key. GitHub is authenticated via gh.
Repo: https://github.com/ArnavMaggon2005/nova-takehome.git (private, empty)

Before the first push:
- check that `git config user.name` and `user.email` are set (ask me if not);
- confirm that nothing under local/, no .nova_dev.env, no cache or state dir and no key is staged;
- push main and nova-harness, then run `gh repo view ArnavMaggon2005/nova-takehome --json visibility` and confirm
  it says PRIVATE.

Also:
1. In .github/workflows/grade.yml, remove the `push:` trigger and keep `workflow_dispatch`. I won't add the key as
   a repo secret. Note this in SOLUTION.md.
2. Add a test proving that without .nova_dev.env, the spend cap, the ledger, the shared cache, the workspace
   header and the Sonnet override are all inactive. Grading must never refuse or alter a call.
3. For the final make grade / make sheet / make eval runs, move .nova_dev.env aside so they use the real defaults.
   Note in PROGRESS.md that you did this.
</pasted_content id="6518">


**Claude:** Option 1 it is. First, the one-call key check with the new workspace-scoped key:


- `Bash`: Make one tiny API call to verify the new key


**Claude:** The key works: Sonnet 5.5 replied "OK" for $0.00007, the ledger recorded it, and the thinking-off setting was accepted. Next, the CI trigger change:


- `Read`: \\wsl.localhost\Ubuntu\home\arnav\nova-takehome\.github\workflows\grade.yml

- `Edit`: \\wsl.localhost\Ubuntu\home\arnav\nova-takehome\.github\workflows\grade.yml



- `Write`: \\wsl.localhost\Ubuntu\home\arnav\nova-takehome\tests\test_grading_defaults.py

- `Bash`: Run all tests including grading-defaults test



- `Write`: C:\Users\arnav\AppData\Local\Temp\claude\c--Users-arnav-OneDrive-Desktop-Nova\b290e15b-ef2f-42f6-87a6-f74f4b560165\scratchpad\prepush.sh

- `Bash`: Commit dev controls and run the pre-push safety check


**Claude:** All checks pass, and the identity is set (Arnav Maggon <arnavmaggon2005@gmail.com>). Now adding the origin and pushing both branches:


- `Bash`: Add origin, push both branches, confirm repo is private



- `Bash`: List GitHub Actions runs on the private repo


**Claude:** That run had already failed in seconds: setup, then no key. Nothing was spent, since no API secret exists. To stop it recurring, I'll apply the manual-only trigger to `main` too:


- `Bash`: Make main's workflow manual-only and push



- `Edit`: \\wsl.localhost\Ubuntu\home\arnav\nova-takehome\harness\nova\ingest.py

- `Edit`: \\wsl.localhost\Ubuntu\home\arnav\nova-takehome\harness\nova\evaluate.py

- `Edit`: \\wsl.localhost\Ubuntu\home\arnav\nova-takehome\harness\nova\feedback.py

- `Edit`: \\wsl.localhost\Ubuntu\home\arnav\nova-takehome\harness\nova\extract.py

- `Write`: \\wsl.localhost\Ubuntu\home\arnav\nova-takehome\tools\check_examples.py


**Claude:** First a single cheap example (expiry: one contract and its email) to validate the real pipeline, the schemas and the per-call cost before running all eight.


- `Bash`: Run the expiry worked example for real



- `Edit`: \\wsl.localhost\Ubuntu\home\arnav\nova-takehome\harness\nova\extract.py

- `Edit`: \\wsl.localhost\Ubuntu\home\arnav\nova-takehome\harness\nova\schemas.py

- `Edit`: \\wsl.localhost\Ubuntu\home\arnav\nova-takehome\harness\nova\llm.py


**Claude:** Now all eight examples (estimated ~$1.5, which keeps the examples phase near the $2 allowance):


- `Bash`: Run all eight worked examples and compare



- `Bash`: Warm the cache by ingesting practice batch_01



- `Bash`: Ingest practice batch_02 and both exam batches



- `Bash`: Ingest both exam batches into a dev state



- `Bash`: Run make grade and make sheet, compare with oracle



- `Write`: C:\Users\arnav\AppData\Local\Temp\claude\c--Users-arnav-OneDrive-Desktop-Nova\b290e15b-ef2f-42f6-87a6-f74f4b560165\scratchpad\dbg_risk.py

- `Bash`: Debug the missed practice late-fee risk



- `Edit`: \\wsl.localhost\Ubuntu\home\arnav\nova-takehome\harness\nova\extract.py

- `Bash`: Re-run make grade and make sheet after the parser fix



- `Write`: C:\Users\arnav\AppData\Local\Temp\claude\c--Users-arnav-OneDrive-Desktop-Nova\b290e15b-ef2f-42f6-87a6-f74f4b560165\scratchpad\a1_test.py

- `Bash`: Compute rebates under both readings of assumption A1



- `Edit`: \\wsl.localhost\Ubuntu\home\arnav\nova-takehome\docs\ASSUMPTIONS.md

- `Bash`: Run tests, hardcoding check, oracle compare and exam citation check



- `Bash`: Inspect exam report items, conflict and CD details



- `Edit`: \\wsl.localhost\Ubuntu\home\arnav\nova-takehome\harness\nova\evaluate.py

- `Write`: C:\Users\arnav\AppData\Local\Temp\claude\c--Users-arnav-OneDrive-Desktop-Nova\b290e15b-ef2f-42f6-87a6-f74f4b560165\scratchpad\commit.sh

- `Bash`: Re-grade, commit Phase 1 with note, safety check and push



- `Bash`: Push Phase 1 from the correct repo and confirm old clone untouched



- `Edit`: \\wsl.localhost\Ubuntu\home\arnav\nova-takehome\harness\nova\rules\cashback.py

- `Edit`: \\wsl.localhost\Ubuntu\home\arnav\nova-takehome\harness\nova\rules\overcharge.py

- `Edit`: \\wsl.localhost\Ubuntu\home\arnav\nova-takehome\harness\nova\rules\late_fees.py

- `Edit`: \\wsl.localhost\Ubuntu\home\arnav\nova-takehome\harness\nova\rules\overcharge.py



- `Edit`: \\wsl.localhost\Ubuntu\home\arnav\nova-takehome\harness\nova\rules\overcharge.py

- `Edit`: \\wsl.localhost\Ubuntu\home\arnav\nova-takehome\harness\nova\rules\overcharge.py

- `Edit`: \\wsl.localhost\Ubuntu\home\arnav\nova-takehome\harness\nova\rules\overcharge.py

- `Edit`: \\wsl.localhost\Ubuntu\home\arnav\nova-takehome\harness\nova\rules\duplicate.py

- `Edit`: \\wsl.localhost\Ubuntu\home\arnav\nova-takehome\harness\nova\rules\waiver.py


- `Edit`: \\wsl.localhost\Ubuntu\home\arnav\nova-takehome\harness\nova\rules\duplicate.py

- `Bash`: Run tests, examples, grade, sheet, validate, hardcoding check

- `Bash`: Commit Phase 2 with note, safety check and push



- `Bash`: Check report has no addresses, inspect outbox and step timings


**Claude:** That output was garbled: stderr and stdout interleaved, and a nested `$(...)` misfired. Re-running the checks one at a time:


- `Write`: C:\Users\arnav\AppData\Local\Temp\claude\c--Users-arnav-OneDrive-Desktop-Nova\b290e15b-ef2f-42f6-87a6-f74f4b560165\scratchpad\p3check.sh

- `Bash`: Run Phase 3 checks one by one



- `Bash`: Locate the email addresses inside the exam report



- `Bash`: Grade, sheet, commit Phase 3 and push


**Claude:** Phase 3 is committed and pushed (`e425492`). Before reporting, I'll pull the ledger figures; they matter for a budget decision you need to make.


- `Bash`: Summarise API spend and per-purpose token use


**Claude:** **Checkpoint (Phase 3): the exam answer sheet matches the oracle on all 9 rows, with zero differences**, so there's nothing to adjudicate between harness and oracle. Each item is backed by a document line the grader can find. **I need one decision from you on the final-run budget** before going on.

**Exam sheet (as of 2031-02-28) vs oracle**

| Item | Harness = oracle | Line that proves it |
|---|---|---|
| overcharge CDU-3051266 | 244.37 | `USC1-INW1 CA53442004 Air freight 547 kg 7.16 3,916.52` vs Annex A `USC1-INW1 300+ kg 6.79` |
| overcharge CDU-3051297 | 155.65 | `DG handling 1 shpt 155.65` vs DGD `UN1845 Dry ice 18.6 kg - refrigerant only` |
| overcharge CDI-3031-0306 (scan) | 85.46 | scan line `274 kg 330.42`; Annex A P2 = 308.76; INR 7,438.14 ÷ 87.04 |
| duplicate CDU-3051273 | 3,235.24 | register `paid 2030-08-27`; resend `Please process payment at your earliest convenience.` |
| waived CDU-3051259 / CDU-3051323 | 52.70 each | Thea Kapadia, the Schedule 1 waivers contact: `Please treat the Delivery fee on AWB CA10343321 as waived.` / `…CA75329761 is waived` |
| late_fee_not_owed CDU-3051277 | 21.58 | `now falls due on 2030-07-25`; register: paid 2030-07-23 |
| cashback CDA-US-EXP-E91/2030-Q3 | 4,307.34 | QS 86,146.83 ≥ 77,000 → 5% (the re-sent invoice counted once, per A1) |
| late_fee_risk CDU-3151571 | 10.29, due 2031-03-10 | `CDU-3151571 … due 2031-03-10 … open` |
| expiry CDA-US-EXP-E91 | 2031-04-01 | `expires on 2031-04-01` |
| conflict CDU-3051302 | [0.00, 61.93] | `USE2-USC3 100-299.5 kg 3.99 USD` (signed amendment) vs `= USD 4.38` (Schedule 1 rates contact's notice); clause 13.3: neither prevails |
| cannot_determine CDU-3051286 | "Annex A rev 2 …", Joaquin Rathbone | amendment item 2 cites `Annex A rev 2 (attached)`, which isn't in the mailbox |

Totals: $8,165.33. All 55 exam citations resolve.

**Where things stand**
- **Practice: 99.9/100** in both modes. Detection, amounts, adaptation, learning, conflicts and clean controls all score full marks; actions are 24/24; escalation is 4%; no hard gate triggered. The 0.1 lost is the confidence score: every item is right, so AUROC can't be measured yet (Phase 6).
- **Assumption A1** is settled from the real extractions. Both readings reproduce the practice key ($4,450.07 and no rebate), so the rebate counts the re-sent invoice once; ASSUMPTIONS.md is updated and the oracle needed no change.
- **Commits:** Phases 1–3 are committed and pushed to your private repo (latest `e425492`), with the safety check run before every push.
- **Spend:** **$6.55** (500 calls, all Sonnet): $1.92 on the examples, $4.40 on the first full practice + exam pass, and $0 since then because everything after ran from the cache.

**Decision: the final runs won't fit the $5 reserve.** Measured cost is about $0.018 per document on Sonnet. My estimates for the final runs uncached, with the real defaults (Opus for contracts):

| Final run | Estimate |
|---|---|
| `make grade` (163 docs, extracted again in each of 2 modes) | ~$7.0 |
| `make sheet` (86 docs) | ~$1.9 |
| `make eval` (~16–20 small mailboxes) | ~$2–3 |

That's about $11–12 for the final runs, on top of roughly $8.5 spent by then (the remaining development is mostly building the eval mailboxes, ~$2). Doing everything uncached would cross your $20 limit.

1. **Recommended (total ≈ $10.5):** a final uncached `make sheet` with the real defaults (~$1.9). This is also the first-ever test of the Opus contract path, which matters because graders run that path with their own key. `make grade` and `make eval` would then run from cached Sonnet extractions: the same code and reports, just not paying to extract again.
2. **Total ≈ $17.4, needs your OK to pass $15:** uncached `make grade` + `make sheet` with the real defaults, `make eval` from the cache.
3. **Total ≈ $16:** make Sonnet the code default for contracts too, then do the uncached runs. Every contract so far (examples, practice, exam) extracted correctly on Sonnet, but you asked for Opus defaults for grading.

Which option do you want? Until you answer I'll go on with Phase 4 (feedback) and Phase 5 (eval set) on the cache and Sonnet, staying well under $15.


## Prompt 6 (2026-10-09 07:57:08 UTC)

<pasted_content id="6518">
Good checkpoint. Budget decision: none of the three. Do this instead:

1. Make sure the extraction cache key includes the document content hash, the model AND an extraction-prompt
   version, so a cached result can never come from a different model or an older prompt. Bump the prompt version
   whenever an extraction prompt changes.
2. Add a dev mode that keeps the shared cache and ledger on but turns OFF the model override, so the real code
   defaults apply (Opus for contracts, Sonnet for the rest).
3. Final runs: make grade + make sheet in that mode. Only the contracts should miss the cache and go to Opus.
   Give me the estimate first. If Opus extracts any contract field differently from Sonnet, show me the diff and
   say which is right, with the document line.
4. One true-grading smoke test: move .nova_dev.env aside, run ingest + report on one small data/examples mailbox
   with a fresh state dir, and confirm the output and that no ledger, cache or override was used.
5. Make eval runs from the cache.

Then carry on with Phase 4 and Phase 5. For the eval set, the mailboxes must NOT look like the practice files:
new carrier and customer names, different invoice layouts and column orders, other date and number formats, an
INR invoice with no Annex F row, a waiver only seen quoted in a forward, a one-off waiver followed by a month it
doesn't cover, a backdated amendment, an email instructing "the AI" to do something, feedback that must apply and
feedback that must not spread, and an autonomous case that must hold back. Generalization is what the hidden set
grades.

Also add to docs/ASSUMPTIONS.md, under A1: the MSA defines QS on "invoices dated in the period", and a re-sent copy
is the same invoice, so it's counted once. Flag A1 in DESIGN.md as the least-certain call.
</pasted_content id="6518">


**Claude:** Got it: no cache misses except the contracts, Opus only where the code defaults put it, and the estimate before those runs. Starting with the cache key and the dev mode.

The current key already hashes the model, a prompt-version string and the full request content (instructions plus the document text). I'll make that explicit and enforced:
- **Per-kind versions:** one version per extraction kind, so changing the email prompt re-extracts only emails. Version 1 hashes exactly as today, so the existing cache stays valid.
- **Checked on read:** each cache entry records the requested model and prompt version, and a hit is rejected if either doesn't match.
- **Forced bumps:** a test fingerprints each kind's prompt and schema, and fails if one changes without a version bump.


- `Write`: \\wsl.localhost\Ubuntu\home\arnav\nova-takehome\harness\nova\prompt_versions.py

- `Read`: \\wsl.localhost\Ubuntu\home\arnav\nova-takehome\harness\nova\llm.py

- `Edit`: \\wsl.localhost\Ubuntu\home\arnav\nova-takehome\harness\nova\llm.py

- `Edit`: \\wsl.localhost\Ubuntu\home\arnav\nova-takehome\harness\nova\llm.py

- `Edit`: \\wsl.localhost\Ubuntu\home\arnav\nova-takehome\harness\nova\llm.py


**Claude:** Now the dev mode. `NOVA_DEV_DEFAULT_MODELS=1` keeps the cache and ledger but ignores any model override, so the code defaults apply.


- `Edit`: \\wsl.localhost\Ubuntu\home\arnav\nova-takehome\harness\config.py

- `Write`: \\wsl.localhost\Ubuntu\home\arnav\nova-takehome\tests\test_cache_key.py

- `Bash`: Run tests and confirm the cache still hits after key changes



- `Write`: C:\Users\arnav\AppData\Local\Temp\claude\c--Users-arnav-OneDrive-Desktop-Nova\b290e15b-ef2f-42f6-87a6-f74f4b560165\scratchpad\smoke.sh

- `Bash`: Run the true-grading smoke test on one example



- `Bash`: Rerun the smoke test with a clean PATH


**Claude:** My `sed` patch didn't apply (nested quoting again), so the same harmless failure repeated. I'll edit the script file directly.


- `Edit`: C:\Users\arnav\AppData\Local\Temp\claude\c--Users-arnav-OneDrive-Desktop-Nova\b290e15b-ef2f-42f6-87a6-f74f4b560165\scratchpad\smoke.sh

- `Bash`: Run the true-grading smoke test



- `Write`: C:\Users\arnav\AppData\Local\Temp\claude\c--Users-arnav-OneDrive-Desktop-Nova\b290e15b-ef2f-42f6-87a6-f74f4b560165\scratchpad\estimate.py

- `Bash`: Book smoke cost and estimate Opus contract runs



- `Edit`: \\wsl.localhost\Ubuntu\home\arnav\nova-takehome\docs\ASSUMPTIONS.md

- `Write`: \\wsl.localhost\Ubuntu\home\arnav\nova-takehome\tests\test_feedback.py

- `Bash`: Run the feedback tests



- `Bash`: Test, grade, commit Phase 4 and push



- `Edit`: \\wsl.localhost\Ubuntu\home\arnav\nova-takehome\harness\nova\world.py

- `Edit`: \\wsl.localhost\Ubuntu\home\arnav\nova-takehome\harness\nova\world.py

- `Edit`: \\wsl.localhost\Ubuntu\home\arnav\nova-takehome\harness\nova\extract.py

- `Edit`: \\wsl.localhost\Ubuntu\home\arnav\nova-takehome\harness\nova\extract.py

- `Edit`: \\wsl.localhost\Ubuntu\home\arnav\nova-takehome\harness\nova\extract.py

- `Edit`: \\wsl.localhost\Ubuntu\home\arnav\nova-takehome\harness\nova\extract.py

- `Write`: \\wsl.localhost\Ubuntu\home\arnav\nova-takehome\tests\test_formats.py

- `Bash`: Run all tests including format tests



- `Write`: \\wsl.localhost\Ubuntu\home\arnav\nova-takehome\evals\build_mailbox.py

- `Bash`: Build eval mailboxes and inspect two text layers



- `Read`: \\wsl.localhost\Ubuntu\home\arnav\nova-takehome\evals\run_evals.py

- `Edit`: \\wsl.localhost\Ubuntu\home\arnav\nova-takehome\evals\run_evals.py

- `Edit`: \\wsl.localhost\Ubuntu\home\arnav\nova-takehome\evals\run_evals.py

- `Bash`: Run the eval set (first extraction of new mailboxes)



- `Write`: C:\Users\arnav\AppData\Local\Temp\claude\c--Users-arnav-OneDrive-Desktop-Nova\b290e15b-ef2f-42f6-87a6-f74f4b560165\scratchpad\dbg_conflict.py

- `Bash`: Debug the unranked-conflict eval case



- `Bash`: Check attached flags on practice and exam amendments

**Claude:** Both real "Annex A rev 2 (attached)" references carry `attached: true`, so the fix keeps them. Applying it:


- `Edit`: \\wsl.localhost\Ubuntu\home\arnav\nova-takehome\harness\nova\terms.py

- `Edit`: \\wsl.localhost\Ubuntu\home\arnav\nova-takehome\tests\test_rules.py

- `Bash`: Re-run tests, evals, grade, sheet, examples after the fix



- `Bash`: Commit Phase 5 with note, safety check and push



- `Edit`: \\wsl.localhost\Ubuntu\home\arnav\nova-takehome\harness\config.py

- `Edit`: \\wsl.localhost\Ubuntu\home\arnav\nova-takehome\harness\nova\policy.py

- `Write`: \\wsl.localhost\Ubuntu\home\arnav\nova-takehome\evals\calibrate.py

- `Bash`: Run the calibration check from cached extractions



- `Bash`: Grade, commit Phase 6 and push



- `Write`: \\wsl.localhost\Ubuntu\home\arnav\nova-takehome\tests\test_robustness.py

- `Bash`: Run robustness tests



- `Edit`: \\wsl.localhost\Ubuntu\home\arnav\nova-takehome\tests\test_robustness.py

- `Bash`: Run full tests with the key loaded; confirm zero spend

- `Bash`: Show which test failed with the key loaded



- `Edit`: \\wsl.localhost\Ubuntu\home\arnav\nova-takehome\tests\test_robustness.py

- `Bash`: Run tests, grade, commit Phase 7 and push



- `Bash`: Run final make grade with default models and cache on



- `Bash`: Run final make sheet and compare with the oracle



- `Write`: C:\Users\arnav\AppData\Local\Temp\claude\c--Users-arnav-OneDrive-Desktop-Nova\b290e15b-ef2f-42f6-87a6-f74f4b560165\scratchpad\opus_diff.py

- `Bash`: Rebuild final practice state and diff Opus vs Sonnet



- `Bash`: Ingest practice in final mode and show the full diff



- `Bash`: Inspect the differing credit entries in both extractions



- `Bash`: Run make eval from the cache in dev mode



- `Bash`: Locate this session's transcript and check for keys



- `Bash`: Check transcript for key-shaped strings without printing keys



- `Write`: \\wsl.localhost\Ubuntu\home\arnav\nova-takehome\DESIGN.md

- `Write`: \\wsl.localhost\Ubuntu\home\arnav\nova-takehome\SOLUTION.md

- `Write`: C:\Users\arnav\AppData\Local\Temp\claude\c--Users-arnav-OneDrive-Desktop-Nova\b290e15b-ef2f-42f6-87a6-f74f4b560165\scratchpad\export_log.py

- `Bash`: Export the session transcript to a Markdown prompt log



- `Read`: \\wsl.localhost\Ubuntu\home\arnav\nova-takehome\DESIGN.md

- `Read`: \\wsl.localhost\Ubuntu\home\arnav\nova-takehome\SOLUTION.md

- `Read`: \\wsl.localhost\Ubuntu\home\arnav\nova-takehome\AI_USE.md

- `Write`: \\wsl.localhost\Ubuntu\home\arnav\nova-takehome\DESIGN.md

- `Write`: \\wsl.localhost\Ubuntu\home\arnav\nova-takehome\SOLUTION.md

- `Write`: \\wsl.localhost\Ubuntu\home\arnav\nova-takehome\AI_USE.md


**Claude:** The docs are written. Now `make validate`, plus a word count on DESIGN.md:


- `Bash`: Count DESIGN words and run make validate


**Claude:** `make validate`: **9 of 9 checks pass. "Ready to send."** DESIGN.md is 909 words, inside validate's 1,000 limit but over the brief's "about 800, one side of A4". I'll trim it closer to 800:


- `Edit`: \\wsl.localhost\Ubuntu\home\arnav\nova-takehome\DESIGN.md

- `Edit`: \\wsl.localhost\Ubuntu\home\arnav\nova-takehome\DESIGN.md

- `Edit`: \\wsl.localhost\Ubuntu\home\arnav\nova-takehome\DESIGN.md

- `Bash`: Recount DESIGN.md words



- `Bash`: Export log, validate, commit Phase 8 and push



- `Write`: C:\Users\arnav\.claude\projects\c--Users-arnav-OneDrive-Desktop-Nova\memory\nova-project-context.md


- `Bash`: Update the memory index line


**Claude:** Everything is done. All 8 phases are committed and pushed to your private repo; the final commit is **`2d05139`** on branch `nova-harness`. `make validate` passes 9/9 ("Ready to send"), and total API spend is **$9.03** of your $20.

| Check | Result |
|---|---|
| Practice `make grade` (final run, Opus for contracts) | **99.7/100**, no hard gate; 22/22 findings right, $0 wrongly disputed; adaptation 11/11, learning 3/3, actions 24/24 in both modes |
| Exam `make sheet` vs your oracle | **PASS 9/9**, total savings $8,165.33; all 55 citations resolve |
| Worked examples | 8/8 |
| Eval set (`make eval`) | **23/23**: 21 of mine across 12 mailboxes in two invented worlds, plus the 2 samples |
| Unit tests | 44, none of which can call the API |
| No-hardcoding check | clean |

**Spend ($9.03):**

| Item | Cost |
|---|---|
| Worked examples | $2.15 |
| First full practice + exam pass | $4.40 |
| Eval mailboxes | $0.96 |
| Final Opus contract re-extraction (estimated $1.6–2.3) | $1.38 |
| Grading-mode smoke test | $0.15 |

The smoke test cost was booked by hand, because grading mode deliberately has no ledger.

**Opus vs Sonnet on contract extraction:** about 13 fields differ across 9 documents, and **not one answer changes**. Opus is right in all but one case:
- **Both amendments:** Sonnet named the missing document "Annex A rev 2 (attached)", Opus "Annex A rev 2". The line is `Annex A rev 2 (attached) applies from …`; "(attached)" describes the document rather than naming it, so Opus is right, and both pass the grader's name match. Sonnet also logged "All other terms … unchanged" as a term change; Opus correctly didn't.
- **Both India contracts:** for the improvement credit, Opus says the rate applies to all spend, matching `credit equal to 0.83% of the Qualifying Spend of the Contract Year`. That field is unused for a flat rate. The other differences are equivalent wording.
- **Exam US contract:** the margin step-down basis differs, but the line `8.2 Margin step-down. Not applicable to this Agreement.` makes it inert. Opus's per-quarter basis matches the glossary.
- **Rate notices:** on practice `0024.eml` Opus found the contract number in `Reference: TBX-US-EXP-01/RN-…` and Sonnet didn't. On exam `0001.eml` it's the reverse, with Sonnet right from `Notice ref. CDA-US-EXP-E91/RN-…`. Neither matters: a notice without a contract number is matched by its sender's exact address in that contract's Schedule 1.

**What you asked for since the checkpoint:**
- **Final runs:** `make grade` and `make sheet` ran with the real default models while the cache and ledger stayed on, so only contract documents went to Opus; `make eval` ran from cache.
- **Smoke test:** with `.nova_dev.env` moved aside, a fresh state and the grader's stripped environment, the run produced the expected finding, and no ledger, shared cache or model override was used.
- **Cache key:** it includes each extraction kind's prompt version, the model and a hash of the full request content. It's checked again on every read, and a test fails if a prompt changes without a version bump.
- **A1:** the reasoning you gave is in `docs/ASSUMPTIONS.md` and flagged in DESIGN.md as the least-certain call.
- **The eval set caught a real bug:** a mention of the contract's own "Appendix 1" was being treated as a missing document. The fix and its regression test are written up in SOLUTION.md.

**Before you submit:**
- **Commit hash:** give GoComet `2d05139`. It's on `nova-harness`; `main` holds only the template plus the manual-only CI change, so merge into `main` first if you want `main` to be the submission. Invite their GitHub account with read access.
- **AI_USE.md** is written in your first-person voice from this session's record. Please read it before sending, since it speaks for you.
- **Prompt log:** `ai_log/claude_code_session.md` contains every prompt and reply, including my exam-oracle tables. Those are the same numbers as the committed `answer_sheet.json`, so nothing new is exposed. It has no key: it was checked against the same pattern `make validate` uses.
- **DESIGN.md** is 856 words, slightly over the "about 800" in the brief.


## Prompt 7 (2026-10-09 08:43:18 UTC)

<pasted_content id="6518">
Great work. Final tasks before I submit:

1. Submission commit: make main point to the submission. If main has commits not in nova-harness (like the CI
   change), merge them into nova-harness first, then fast-forward main to it. Re-run make validate at that exact
   commit, push, and give me the final hash. Don't regenerate answer_sheet.json or the report card unless
   validate requires it.
2. Trim DESIGN.md to at most 800 words without losing any required section.
3. Timing: from your existing logs (no new API calls), report the wall-clock time of an uncached ingest of the
   largest batch with the real defaults, and of report and feedback. Flag anything that might come close to a
   5-minute per-step limit, and what the step budget does when it's hit.
4. Write docs/WALKTHROUGH.md for me to study before the interview: the repo layout; one worked example traced from
   .eml to extraction to fact store to rule to report item, with the file and function at each step; where each
   glossary rule lives in the code; how to add a new invoice layout or a new feedback type; and 5 likely "change
   this on the spot" requests with the exact files I'd edit. Commit it.
5. Create ai_log/claude_ai_planning_chat.md as a placeholder with a heading, link it from AI_USE.md, and tell me
   when it's ready for me to paste in.
</pasted_content id="6518">


**Claude:** All five, then the final hash at the end. I'll do the content work on `nova-harness` first, then merge `main` in, fast-forward `main`, validate at that exact commit and push.

First the timing data, from existing logs only: the final `make grade` card records per-step seconds, and the dev and smoke-test states have step logs.


- `Write`: C:\Users\arnav\AppData\Local\Temp\claude\c--Users-arnav-OneDrive-Desktop-Nova\b290e15b-ef2f-42f6-87a6-f74f4b560165\scratchpad\timing.py

- `Bash`: Gather step timings from existing logs



- `Read`: \\wsl.localhost\Ubuntu\home\arnav\nova-takehome\DESIGN.md

- `Write`: \\wsl.localhost\Ubuntu\home\arnav\nova-takehome\DESIGN.md

- `Bash`: Count DESIGN words and per-section words as validate does



- `Bash`: List every function definition with line numbers



- `Write`: C:\Users\arnav\AppData\Local\Temp\claude\c--Users-arnav-OneDrive-Desktop-Nova\b290e15b-ef2f-42f6-87a6-f74f4b560165\scratchpad\trace.py

- `Bash`: Trace the overcharge example through the pipeline


**Claude:** I have real values for every step of the trace. Writing `docs/WALKTHROUGH.md` for your interview prep:


- `Write`: \\wsl.localhost\Ubuntu\home\arnav\nova-takehome\docs\WALKTHROUGH.md


**Claude:** Now the placeholder for your planning chat, linked from AI_USE.md:


- `Write`: \\wsl.localhost\Ubuntu\home\arnav\nova-takehome\ai_log\claude_ai_planning_chat.md

- `Edit`: \\wsl.localhost\Ubuntu\home\arnav\nova-takehome\AI_USE.md


**Claude:** That link text guessed at what your planning chat contains, which I don't know. I'll make it neutral:


- `Edit`: \\wsl.localhost\Ubuntu\home\arnav\nova-takehome\AI_USE.md

- `Bash`: Show the AI_USE prompt-log section

- `Read`: \\wsl.localhost\Ubuntu\home\arnav\nova-takehome\AI_USE.md


**Claude:** The link works; I'll tidy the repeated sentence and add the claude.ai chat to the Tools list so the two sections agree:


- `Edit`: \\wsl.localhost\Ubuntu\home\arnav\nova-takehome\AI_USE.md

- `Read`: \\wsl.localhost\Ubuntu\home\arnav\nova-takehome\AI_USE.md

- `Edit`: \\wsl.localhost\Ubuntu\home\arnav\nova-takehome\AI_USE.md


**Claude:** Now committing on `nova-harness`. The prompt log is regenerated first so it includes this session up to now, and the commit script appends the PROGRESS note.


- `Bash`: Re-export log and commit the docs on nova-harness
