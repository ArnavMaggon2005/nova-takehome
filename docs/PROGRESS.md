# Progress log

One entry per phase (docs/PLAN.md section 13): what changed, the score, what broke.

- **Phase 0: harness skeleton, state dir, text layer, no-hardcoding check** (2026-10-09T06:13Z)
  - Changed: harness skeleton: nova package, SQLite state dir, vendored grader text layer (parity-tested), Decimal money, LLM wrapper/schemas/prompts/extractor written, check_no_hardcoding in make eval, assumptions file
  - Score: 0.0/100 practice (empty reports by design; all 5 hard gates clear); CLI + schema validate PASS; 7/7 unit tests
  - Broke / open: LLM extraction untested: no ANTHROPIC_API_KEY in WSL yet, documents stay pending

- **Phase 1: real extraction on examples, practice and exam** (2026-10-09T07:45Z)
  - Changed: real extraction validated: examples 8/8 match expected_finding.json; full practice + exam ingest (249 docs, 0 failures); contract sections merged 4->2 calls; no wasted cache writes; AP-register currency parsed from a shared cell; dev cache/ledger/spend cap; A1 settled (count once)
  - Score: practice make grade 99.9/100 (22/22 hits, 0 false, adaptation 11/11, learning 3/3, actions 24/24 both modes); exam sheet = oracle 9/9
  - Broke / open: AUROC not measurable on practice (every item right); first practice run missed one late-fee risk (parser bug, fixed)
  - API spend so far: $6.55

- **Phase 2: rules and exam gate** (2026-10-09T07:47Z)
  - Changed: rules polish for cases practice does not exercise: promised-credit due date counted from the anniversary, band/period/month-edge confidence feature on the shipment lane only, unpaid-invoice guard on not-owed fees, native-currency amounts carried for the late-fee-risk principal; tools/check_examples.py in the loop
  - Score: examples 8/8; practice 99.9/100; exam sheet = oracle 9/9; exam report 55/55 citations resolve
  - Broke / open: nothing new; confidence still flat (~0.96) so AUROC is not measurable yet (Phase 6)
  - API spend so far: $6.55

- **Phase 3: modes, unattended test, time budget** (2026-10-09T07:48Z)
  - Changed: modes and time verified: unattended 5-check test, summed 5k threshold, open-conflict index, outbox addressed to Schedule 1 contacts (no address in any outbound field), versioned ids/supersedes/retro, escalation log; cold ingest timings 65-145 s per batch at 4 threads (budget 300 s)
  - Score: practice 99.9/100 both modes (actions 24/24 supervised and autonomous, escalated 4%, no hard gate); exam sheet = oracle 9/9
  - Broke / open: none
  - API spend so far: $6.55

- **Phase 4: feedback** (2026-10-09T08:02Z)
  - Changed: feedback verified for every glossary kind (confirm sender_authority, close dispute_closed, close rate_accepted, one_off_approval, reject, resolve_conflict, override_amount, unknown) with no-spread checks; cache key made explicit (per-kind prompt version + model + content hash, checked on read, prompt fingerprints pinned by test); dev final mode NOVA_DEV_DEFAULT_MODELS; grading-mode smoke test (no dev file, stripped env) passed on an example mailbox
  - Score: practice 99.9/100, learning 3/3; exam sheet = oracle; 34/34 unit tests
  - Broke / open: nothing broken; smoke test spend booked by hand since grading mode has no ledger
  - API spend so far: $6.69

- **Phase 5: eval set and the bug it caught** (2026-10-09T08:14Z)
  - Changed: eval set: 21 cases over 12 generated mailboxes in two invented worlds (new carriers/customers/people, airport-pair routes, other invoice layouts and column orders, text and dd.mm.yyyy dates, lakh grouping, INR with no FX row, quoted-only waiver, one-off waiver + uncovered month, backdated amendment with interim report, AI-directed email and footer, feedback that applies / must not spread / closes, autonomous hold-backs); run_evals extended (interim reports, retro, learned_at, report_must_not_contain); format hardening (text dates, column date order, route separators, Schedule 1 category synonyms)
  - Score: evals 23/23 (21 mine); practice 99.9/100; exam sheet = oracle; examples 8/8; 40 unit tests
  - Broke / open: a_conflict_unranked caught a real bug: an amendment mention of the agreement own appendix was treated as a missing document (explicit rate lost to cannot_determine); fixed in terms.py with a regression test
  - API spend so far: $7.66

- **Phase 6: confidence and calibration** (2026-10-09T08:16Z)
  - Changed: confidence: base lowered to ~0.93 for a clean evidenced finding (hedge for unseen data), small class priors (cashback/waiver/late-fee lower, expiry higher); evals/calibrate.py labels every item with ground truth (practice by batch, worked examples, own eval keys) and reports Brier, AUROC, reliability bins
  - Score: calibration: 51 items, 51 right, Brier 0.0166, AUROC not measurable (no wrong item); practice 99.6-99.9 (confidence points slightly lower by design)
  - Broke / open: no wrong items exist to fit or test AUROC; weights stay hand-set (see DESIGN.md)
  - API spend so far: $7.66
