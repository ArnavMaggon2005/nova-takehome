# AI use

## Tools

- **Claude Code** (Anthropic's CLI, in VS Code; model Claude Opus 5.5) wrote the plan, all of the harness code, the
  tests, the eval set and these documents, working in one session.
- **Claude Opus 5.5 and Claude Sonnet 5.5** are called by the harness itself through the `anthropic` SDK. They only
  read documents into JSON; no decision is made by a model.

## How you worked with them

I worked plan-first. Claude Code read the whole brief, grader and data, then wrote `docs/PLAN.md`. Nothing was coded
until I approved it. I made the calls that were mine:
- **Budget:** a hard $20 limit, a spend ledger, and a stop before $15. Actual spend was $9.03.
- **Models:** Sonnet for development; Opus for contracts in the final runs.
- **The exam oracle:** kept in a gitignored `local/` folder that the harness may not read, plus a tool that fails if
  any id or name from `data/` appears in the harness.
- **Ambiguities:** settled in the order glossary, worked examples, practice key as evidence, then the conservative
  reading. Each one is a constant and an entry in `docs/ASSUMPTIONS.md`.
- **The eval set:** invented worlds that must not look like the practice files.
- **The repo:** private, with CI manual only.

Each phase ended with `make grade`, a commit, a push and a note in `docs/PROGRESS.md`. I reviewed two checkpoints: the
exam sheet against my hand-derived oracle, and the end.

Where it went wrong, and how it was caught:
- **Contracts:** the first contract extraction paid prompt-cache writes that were never read. Found in the token usage;
  contracts are now two calls instead of four.
- **AP register:** a column map put the currency and the amount in the same cell, which dropped a late-fee risk.
  Found by the practice card and fixed in the parser.
- **Missing documents:** the eval set found that a mention of the agreement's own appendix was treated as a missing
  document (SOLUTION.md).
- **Shell slips:** one push ran from the wrong folder and was refused harmlessly; a few shell-quoting slips ran nothing
  and spent nothing.
- **Environment:** `make` was missing on Windows (we work in WSL), and the first API key needed a workspace header.

## Written without AI

No code or document text. My part was the direction and every decision listed above, plus reviewing each checkpoint.

## Prompt log

The session is exported in [ai_log/claude_code_session.md](ai_log/claude_code_session.md). It holds every prompt I
sent, every reply, and one line per tool call. Raw tool output (file and command dumps), the model's internal thinking
and system messages are left out for length. No secret appeared in the session; the API key was never printed, and
the export refuses to write anything key-shaped.
