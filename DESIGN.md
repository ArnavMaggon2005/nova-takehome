# Design

## Fact model

Each email body and attachment is one document (`batch_NN/0007.eml#X.pdf`, received time from the Date header).
Its text is the grader's own text layer, shown to Claude with `[pN LM]` line numbers. Claude fills a type-specific
JSON schema: Sonnet for routine documents, Opus for contracts, amendments and rate notices. Every row cites its page
and line, and numbers are copied verbatim. Python checks that each number is printed on the line it cites, and
re-extracts once with the errors fed back if not. SQLite in `--state-dir` keeps documents and extractions only. Each
report rebuilds a typed world (contracts, rates, Schedule 1 people, invoice lines, ledger, tracking, waivers,
extensions, notices, amendments) from documents received by `as_of`. Charge labels map to the contract's own codes,
then to generic kinds, so no rule depends on one carrier's layout. Quotes are the exact cited lines, so they always
resolve.

## Conflicts

`terms.resolve_rate` gathers every candidate in force on the pickup date:
- the agreement's rate annex;
- signed amendments, where a later effective date wins. If an amendment incorporates a document we don't hold, the
  answer is cannot_determine;
- rate notices from the contract's Schedule 1 rates contact, matched by exact address;
- notices a person accepted in feedback.

Unauthorised, quoted or AI-directed text never counts. Notice against amendment follows the precedence the contract
states. It becomes a conflict only when the contract leaves them unranked and the two give different expected amounts;
the amount range comes from repricing the invoice under each.

## Confidence

The logit starts at about 0.93 for a clean, evidenced finding, plus a small class prior. Penalties apply for a pickup
date not from tracking, a scan, currency conversion, extraction gaps, a weight or date near a band, period or month
edge, many-invoice aggregates, conflict or cannot_determine, and unverified evidence. `evals/calibrate.py` labels 51
items with ground truth (practice by batch, examples, own evals): all right, Brier 0.017. With no wrong items, AUROC
can't be measured, so the weights are hand-set and hedged below practice accuracy for unseen data.

## People in the loop

Internal actions run on their own: alerts, payment reminders, credit tracking. Conflicts escalate. In supervised mode
outbound remedies are drafts, or human_review at $5,000 or more summed per invoice or cashback key. Autonomous mode
executes only when all five unattended checks pass:
- complete evidence, including a tracking pickup date for every shipment in the key;
- no open conflict on that contract, lane and period;
- under $5,000;
- reversible;
- level-1/2 terms and a Schedule 1 recipient.

Pay, settle and accept actions don't exist in the code. "Execute" writes an outbox record addressed only to a
Schedule 1 contact, and recipients never appear in the report.

## Feedback

Feedback is stored verbatim and split two ways. Scoped facts (sender_authority, rate_accepted, precedence) feed the
resolvers, but only where every `applies_to` filter matches within `valid_from` and `valid_to`. Key directives (close,
reject, override_amount, one_off_approval) change exactly one key. The rules run with and without feedback, and any key
whose verdict, amount or action differs carries `learned_at`. Tests cover every glossary kind, and also check that
nothing spreads to another person, lane, month or invoice.

## New documents

Ingest only adds documents; each report recomputes from the `as_of` view, so arrival order can't matter. Snapshots per
mode and date keep ids stable: an unchanged answer keeps its id, a changed one gets a new id with `supersedes`, and a
new key on an already-held invoice caused by a newly received term document is `retro`. Lapsed alerts and paid
invoices disappear because nothing is carried forward. New layouts need no code; the eval set's two invented worlds
test that.

## Cost

Measured cost was $4.40 for the 249 practice and exam documents with Sonnet throughout (about 1.55 calls per document,
3.4K input and 0.6K output tokens per call). With the defaults, which send the roughly 2% of documents that are
contracts to Opus, it was $5.14. That is about **$21 per 1,000 documents**. Time: 82 documents took 145 s with 4
parallel calls; the default is 12, giving about 10–30 minutes per 1,000. Each step works within a 300 s budget and
passes unfinished documents to the next step.

## What I'd do next

The least certain call is **A1**: a paid invoice re-sent under the same number counts once in rebate spend. The MSA
counts "invoices dated in the period", and a copy is the same invoice. The other reading changes the exam Q3 rebate
from 4,307.34 to 4,469.10. Other judgement calls are in `docs/ASSUMPTIONS.md`:
- check 1 applies to every shipment in a key;
- quantities are taken as printed;
- unverifiable lines are accepted;
- tax lines are never disputed.

Next steps:
- compute margin step-down (it's extracted but not computed) and marginal tiers;
- compare Opus with Sonnet on more unseen contracts;
- collect wrong items to fit the confidence weights;
- split very long invoices by page for faster extraction.
