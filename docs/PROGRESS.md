# Progress log

One entry per phase (docs/PLAN.md section 13): what changed, the score, what broke.

- **Phase 0: harness skeleton, state dir, text layer, no-hardcoding check** (2026-10-09T06:13Z)
  - Changed: harness skeleton: nova package, SQLite state dir, vendored grader text layer (parity-tested), Decimal money, LLM wrapper/schemas/prompts/extractor written, check_no_hardcoding in make eval, assumptions file
  - Score: 0.0/100 practice (empty reports by design; all 5 hard gates clear); CLI + schema validate PASS; 7/7 unit tests
  - Broke / open: LLM extraction untested: no ANTHROPIC_API_KEY in WSL yet, documents stay pending
