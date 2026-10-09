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
