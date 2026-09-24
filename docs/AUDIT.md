# Audit and hardening — 0.1.2a1

Date: 2026-09-23. Source: JY-S020-P001 / 0.1.1-partial / run-0001 / product.
Reviewed engine, server, receipt writer, gate harness and vendored evaluator.
Original source remains separate from the release checkout.

## Repaired findings

- Nested exact powers could allocate huge integers and exceed safe rendering
  limits. Bit-budget preflight, intermediate bounds and AST-depth limits now
  fail with structured E_LIMIT responses.
- Global Decimal settings influenced results; unary negation truncated long
  results. Explicit local contexts and context-free sign changes isolate caller
  state. Decimal exceptions now become stable domain/limit errors.
- Exact fractional exponents could round to integers on mixed Decimal paths.
  Exponent validation now precedes conversion. Zero to nonpositive powers has
  consistent domain behavior.
- Canonical rational atoms lacked parentheses and could change power meaning.
  Parenthesized rationals and bounded scientific canonical integers repair this.
- Trigonometric reduction lacked magnitude guard digits and near-pole handling.
  Bounded extra precision, convergence stopping and tangent rejection improve
  behavior without claiming rigorous accuracy bounds.
- HTTP accepted coerced precision, ambiguous headers, arbitrary origins and
  duplicate/nonfinite JSON. Strict shape/framing and loopback Host/Origin checks
  now reject these cases; responses disable caching.
- Service instances shared a mutable class receipt sink. The supported factory
  now binds sinks per server and limits active workers and socket inactivity.
- Receipt writes accepted nonfinite/oversized records, interleaved across writer
  instances and could append after a truncated line. Bounded strict JSON,
  shared in-process path locks and tail checks improve failure behavior.
  Receipts now bind precision/version/response hash and use monotonic duration.
- Gate string splitting confused operators inside values and skipped invalid
  short-circuit branches. A bounded parser treats context as data and validates
  the full expression; empty conditions fail and duplicate gate IDs are rejected.

## Verification and release

53 inherited tests passed before changes. 103 source and installed-wheel tests
pass afterward, including 50 regressions for numeric/context boundaries, canonical
meaning, hostile HTTP shapes, receipt failure/concurrency and gate parsing.
Three inherited tests changed for safe quote handling and empty-condition errors.
Existing independent libm and Fraction checks remain; high-precision stability
checks are not independent proofs of arbitrary-precision accuracy.

Python Decimal context and sign behavior were checked against the official
[Decimal documentation](https://docs.python.org/3/library/decimal.html).
CI covers Linux Python 3.10/3.12/3.14 and Windows Python 3.12. Historical check
evidence is retained separately. No formal platform qualification is claimed.

Version 0.1.1-partial -> 0.1.2a1. Numeric/HTTP/gate contracts are stricter; see
README for migration details. Added packaging, pinned-action CI, README, security
guidance and Apache 2.0 LICENSE/NOTICE naming RUSSELL PHILIP SMITHSON.

Microsoft's MIT donor notice is preserved. The parser adaptation reuses audited
work from the local R08 candidate and adds scalar limits. No third-party runtime
packages require upgrades; no build-tool vulnerability scan is claimed.
Original D0/G0–G9 decisions and the 1,187-item program remain open.
