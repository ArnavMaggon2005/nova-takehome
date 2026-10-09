# Design

## Fact model

Each email body and attachment is one document (`batch_NN/0007.eml#X.pdf`, received time from the Date header). Its
text is the grader's own text layer, shown to Claude with `[pN LM]` line numbers. Claude fills a type-specific JSON
schema: Sonnet for routine documents, Opus for contracts, amendments and rate notices. Every row cites its page and
line; numbers are copied verbatim. Python checks each number is printed on the cited line, else re-extracts once with
the errors fed back. SQLite in `--state-dir` keeps documents and extractions only. Each report rebuilds a typed world
(contracts, rates, Schedule 1 people, invoice lines, ledger, tracking, waivers, notices, amendments) from documents
received by `as_of`. Charge labels map to the contract's own codes, then generic kinds, so no rule depends on one
carrier's layout. Quotes are the exact cited lines, so they always resolve.

## Conflicts

`terms.resolve_rate` gathers candidates in force on the pickup date:
- the agreement's rate annex;
- signed amendments, a later effective date winning (a document they incorporate that we don't hold makes it
  cannot_determine);
- rate notices from the Schedule 1 rates contact, matched by exact address;
- notices accepted in feedback.

Unauthorised, quoted or AI-directed text never counts. Notice against amendment follows the contract's stated
precedence; it's a conflict only when they're unranked and give different expected amounts. The range comes from
repricing the invoice under each.

## Confidence

The logit starts at about 0.93 for a clean, evidenced finding, plus a small class prior. Penalties: pickup date not
from tracking, scan, currency conversion, extraction gaps, a weight or date near a band, period or month edge,
many-invoice aggregates, conflict or cannot_determine, unverified evidence. `evals/calibrate.py` labels 51 items with
ground truth (practice by batch, examples, own evals): all right, Brier 0.017. With no wrong items AUROC can't be
measured, so the weights are hand-set and hedged below practice accuracy for unseen data.

## People in the loop

Alerts, payment reminders and credit tracking run on their own; conflicts escalate. In supervised mode outbound
remedies are drafts, or human_review at $5,000 or more summed per invoice or cashback key. Autonomous mode executes
only when all five unattended checks pass:
- complete evidence, including a tracking pickup date for every shipment in the key;
- no open conflict on that contract, lane and period;
- under $5,000;
- reversible;
- level-1/2 terms and a Schedule 1 recipient.

Pay, settle and accept actions don't exist in the code. "Execute" writes an outbox record addressed only to a
Schedule 1 contact; recipients never appear in the report.

## Feedback

Feedback is stored verbatim and split two ways. Scoped facts (sender_authority, rate_accepted, precedence) feed the
resolvers only where every `applies_to` filter matches within `valid_from`–`valid_to`. Key directives (close, reject,
override_amount, one_off_approval) change exactly one key. Rules run with and without feedback; any key whose
verdict, amount or action differs carries `learned_at`. Tests cover every glossary kind and check nothing spreads to
another person, lane, month or invoice.

## New documents

Ingest only adds documents; each report recomputes from the `as_of` view, so arrival order can't matter. Snapshots
keep ids stable: an unchanged answer keeps its id, a changed one gets a new id with `supersedes`, and a new key on an
already-held invoice caused by a newly received term document is `retro`. Lapsed alerts and paid invoices disappear
because nothing is carried forward. New layouts need no code; the eval set's two invented worlds test that.

## Cost

Measured: $4.40 for the 249 practice and exam documents with Sonnet throughout (about 1.55 calls per document, 3.4K
input and 0.6K output tokens per call). With the defaults (Opus for the roughly 2% that are contracts) it was $5.14,
about **$21 per 1,000 documents**. Time: 82 documents took 145 s with 4 parallel calls; the default is 12, so about
10–30 minutes per 1,000. Each step works within a 300 s budget and passes unfinished documents to the next.

## What I'd do next

Least certain is **A1**: a paid invoice re-sent under the same number counts once in rebate spend, because the MSA
counts "invoices dated in the period" and a copy is the same invoice. The other reading moves the exam Q3 rebate from
4,307.34 to 4,469.10. Other calls are in `docs/ASSUMPTIONS.md`: check 1 covers every shipment in a key; quantities as
printed; unverifiable lines accepted; tax lines never disputed.

Next: compute margin step-down (extracted, not computed) and marginal tiers; compare Opus with Sonnet on more unseen
contracts; collect wrong items to fit confidence; split very long invoices by page.
