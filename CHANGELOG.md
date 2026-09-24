# 0.1.2a1 — 2026-09-23

- Bound exact growth and expression depth; isolate Decimal contexts and errors.
- Preserve canonical rational meaning and validate exponents before conversion.
- Improve bounded trigonometric reduction and numerical pole handling.
- Enforce strict loopback HTTP framing, JSON, origin and worker limits.
- Isolate receipt sinks, serialize writers and reject incomplete audit tails.
- Parse full gate conditions with safe data operands and retained MIT attribution.
- Add 50 regressions, packaging, CI, README and Apache 2.0 LICENSE/NOTICE.
- Original program certifications remain open.

# Changelog — E01 Local Calculator (JY-S020-P001)

## 0.1.1-partial — 2026-09-14 (A017 audit/hardening pass)

Baseline fingerprint: build-0001 `product.zip`
sha256 `db1e8ebd39a8a34c702a3c23d5807a6a683a4eb1349650da14537ed12fc25d41`
(24261 bytes), version `0.1.0-partial`, baseline suite 36/36 PASS.

Repairs only; no public API additions or removals. All findings were
reproduced on the baseline with live probes before fixing.

- **A017-F1** (high): `sqrt()` of integers >= ~1e308 raised a bare
  `OverflowError` (`int(n ** 0.5)` in `_isqrt_exact`); via the server this
  dropped the TCP connection with no JSON error. Observed:
  `sqrt(999...9 [400 digits])` -> OverflowError. Expected: inexact Decimal
  result. Fixed with `math.isqrt`.
- **A017-F2** (high): non-string expression (`engine.parse(["1+1"])`, or
  JSON body `{"expression": 123}`) escaped as a bare `TypeError`; the
  server dropped the connection without a JSON error. Fixed: `tokenize`
  type-checks (E_PARSE) and the server validates the field (400 E_REQUEST).
- **A017-F3** (high): gate-condition injection in
  `vendor/gate_condition_evaluator.py` — a context string value containing
  quotes spliced into the expression grammar; value
  `a' == 'a' or 'b' == 'b` forced `{{status}} == 'success'` to True.
  Fixed: values containing quote characters are refused (ExpressionError,
  fail closed; gates.py reports "ERROR", never a false pass).
- **A017-F4** (medium): scientific-notation exponents bypassed
  `MAX_NUMBER_DIGITS` — `1e999999` built a million-digit exact integer
  (unbounded memory/CPU for larger exponents). Fixed: |exponent| in a
  literal is bounded by `MAX_NUMBER_DIGITS` (400), raising `E_LIMIT`.
- **A017-F5** (low): non-integer `precision` argument to
  `engine.evaluate` leaked a bare `TypeError`. Fixed: `E_LIMIT` with a
  clear message; bool rejected as well.
- **A017-F6** (low): `MAX_EXPONENT` (4096) was enforced only on the exact
  Fraction path; the Decimal path accepted `pi^100000`. Fixed: same bound
  on both paths (contract consistency).

Compatibility: strictly narrowing — inputs that previously crashed,
disconnected, or bypassed documented limits now return typed
`CalcError`s / JSON errors. No previously-documented valid input changes
result. Rollback: restore build-0001 `product.zip`
(sha256 db1e8ebd...25d41); no data-format changes.
