> Historical September 14, 2026 baseline record. Current candidate changes and verification are in AUDIT.md and CHECK_RUNS.json; no original certification status is advanced by this release.

# Traceability — implemented artifacts to E01 v3.0.0 checklist areas

| Artifact | Checklist linkage (v3.0.0 / package sections) | Evidence |
|---|---|---|
| `docs/GRAMMAR.ebnf` | P1.9 "Define the EBNF grammar for the calculation language" (sections/05_phase_1) | grammar file; parser implements it; `tests/test_engine.py::Canonicalization` |
| `e01_calculator/engine.py` tokenizer/parser | P2 parser/validation items (sections/06_phase_2) | `tests/test_engine.py` parse/limit/error cases |
| `e01_calculator/engine.py` exact evaluator | P3 math engine items (sections/07_phase_3); orchestrator "exact arithmetic" domain check | ExactArithmetic tests; 200-case Fraction oracle in `tests/test_gates_and_oracle.py` |
| Canonicalization | P1 canonicalization items incl. cross-notation vectors | `test_cross_notation` (`2**3` = `2^3`) |
| Zero-side-effect kernel + spy test | D0.2.05 "Add side-effect conformance tests" (provisional D0.2 definition) | `tests/test_side_effects_and_server.py::ZeroSideEffectConformance` |
| `e01_calculator/server.py` | D0.3 "local 127 server" contract (provisional); D0.3.03 loopback mandate; D0.3.06 exposure tests | `LoopbackServer` tests incl. non-loopback refusal |
| `e01_calculator/receipts.py` | D0.2.03/D0.2.04 receipt boundary and fail-closed egress (provisional); P5 audit-sink adjacency | `test_receipts_written`; `E_AUDIT` path in server |
| Provisional limits in engine | P4 resource-governance adjacency — provisional values only | limit tests (`test_limits`) |
| `e01_calculator/gates.py` + vendor evaluator | G0-G9 readiness reporting without certification; package rule 7 | `GateReadiness` test asserts no PASS claims |
| `docs/CHECK_RUNS.json` | Orchestrator evidence rules: environment identity, capture time, unrun checks | file content |

Implemented items proceed under recorded provisional assumptions
(`docs/PROVISIONAL_ASSUMPTIONS.md`) and are therefore IN PROGRESS, not
COMPLETE WITH EVIDENCE, per the orchestrator's D0 rule.
