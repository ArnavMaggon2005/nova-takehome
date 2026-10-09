# AI use

## Tools

- **Claude Code** (Opus 5.5, in VS Code, running in WSL). It did the heavy lifting: the plan, all of the harness code, the tests, the eval set and the first drafts of the docs.
- **Claude Opus 5.5 and Sonnet 5.5 through the API.** The harness itself calls these, but only to read documents into JSON. Every verdict, amount and action is plain Python.

## How I worked with them

I didn't let Claude Code write any code until there was a plan I agreed with. First it read the whole brief, the glossary, the grader and the data, and wrote `docs/PLAN.md`. I reviewed that before giving the go-ahead.

After that, my job was mostly making decisions and checking the work:

- **Cost.** I set a hard $20 limit on my API key. Claude Code kept a spend ledger and had to stop and ask me before going over $15. During development everything ran on Sonnet with a shared cache. For the final runs I had it use the real defaults (Opus for contracts) while keeping the cache, so only the contracts were re-extracted. Total spend was $9.03.
- **Not overfitting.** The brief warns that a harness tuned to the practice files scored about 11/100 on the hidden set. So I had Claude Code hand-calculate the exam answers as an oracle, kept it in a gitignored `local/` folder the harness can't read, and added a check that fails if any id, AWB, lane or name from `data/` appears in the harness code. When the harness and the oracle disagreed, the rule was to go back to the documents, never to special-case.
- **Ambiguities.** I decided not to email GoComet and to make assumptions instead, resolved in this order: the glossary, the worked examples, the practice key (as evidence of how a rule is read, never copied), and otherwise the conservative reading, since a wrong dispute costs double. Each assumption is a named constant with an entry in `docs/ASSUMPTIONS.md`. The one I'm least sure about is whether a re-sent paid invoice counts once or twice in the rebate's qualifying spend. I went with once, because the contract defines spend on "invoices dated in the period" and a re-sent copy is the same invoice.
- **Grading safety.** All the dev conveniences (cache, ledger, Sonnet override) live in a gitignored `.nova_dev.env`. I had Claude Code add a test proving none of them is active without that file, so nothing can change or block a call when GoComet runs the code.
- **Setup.** I worked in WSL rather than Windows, used a workspace-scoped API key, kept the repo private, and made CI manual only so it wouldn't spend my credit on every push. I also lowered the per-step time budget from 300 s to 240 s, since the real limit isn't stated.

Each phase ended with `make grade`, a commit, a push and a short note in `docs/PROGRESS.md`. I stopped it at two checkpoints: when the exam sheet was compared with the oracle (9/9 matched), and at the end.

## What went wrong along the way

- The first contract extraction paid for prompt-cache writes that were never read. We spotted it in the token usage and cut contracts from four calls to two.
- An AP register column map put the currency and the amount in the same cell, which silently dropped a late-fee risk. The practice report card caught it, and the parser was fixed.
- The eval set caught a real bug: a mention of the agreement's own appendix was being treated as a missing document. SOLUTION.md has the details.
- A unit test was passing only because the shared dev cache held an old fake reply. The tests are now isolated from the dev cache.
- Smaller things: `make` wasn't available on Windows (hence WSL), my first API key was organisation-level and needed a workspace, one push ran from the wrong folder and was refused, and a few shell-quoting mistakes ran nothing.

## Written without AI

No code or document text. My part was the direction and every decision listed above, plus reviewing each checkpoint.

## Prompt log

- [ai_log/claude_code_session.md](ai_log/claude_code_session.md): the full Claude Code session. It has every prompt I sent, every reply, and one line per tool call. Raw tool output, the model's internal reasoning and system messages are left out for length. No secrets appeared in the session: the API key was never printed, and the export refuses to write anything that looks like a key.
