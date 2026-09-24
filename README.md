# E01 Local Calculator

**0.1.2a1 — experimental partial candidate, JY-S020-P001**

A rational/Decimal expression library and optional local JSON service.
The evaluation function performs no file or network I/O; the service writes
audit receipts outside that arithmetic boundary.

## Install and use

Python 3.10 or newer; no third-party runtime dependencies.

~~~sh
python -m pip install .
python -m unittest discover -s tests -t .
python -m e01_calculator.server --port 8123 --receipts audit/receipts.jsonl
~~~

~~~python
from e01_calculator.engine import evaluate, parse, canonicalize

assert evaluate("0.1 + 0.2").as_strings()["rational"] == "3/10"
assert evaluate("sqrt(9/16)").exact
approximate = evaluate("-sqrt(2) + sin(1)", precision=50).as_strings()
canonical = canonicalize(parse("0.4^2"))
~~~

Operators: +, -, *, /, ^ and its ** alias, unary signs and implicit multiplication.
Powers associate right; -3^2 is -(3^2). Functions are abs, floor, ceil, sqrt,
sin, cos, tan, ln, log10 and exp; constants are pi and e. Only integer powers
are supported. Zero to a nonpositive power is a domain error.

Rational operations and perfect-square roots are exact within resource budgets.
Other results are explicitly inexact. precision (1..200, default 50) is a working
significant-digit setting, not a verified accuracy guarantee for an entire
expression. Cancellation, accumulated rounding and rounded intermediate
trigonometric inputs can lose accuracy. No interval/error-bound arithmetic is
provided. Rational decimal rendering is a 50-digit approximation; rational is
the authoritative exact representation.

Decimal contexts are explicitly configured and isolated from callers' precision,
rounding, exponent limits, flags and traps. Unary sign changes preserve the
computed digits. Rational atoms retain parentheses in canonical expressions.
This canonical form describes the parsed expression, not algebraic equivalence.

## Service contract

GET /v1/health and POST /v1/calculate are available at 127.0.0.1 only.
The POST body is UTF-8 JSON containing a string expression and optional integer
precision. For example: {"expression":"1/3 + 1/6","precision":50}.

Host must exactly match 127.0.0.1:<listening-port>. If Origin is present it must
match http://127.0.0.1:<listening-port>. The service rejects other origins,
duplicate Host/Content-Length, transfer encoding, duplicate JSON keys, nonfinite
JSON and unsupported fields. Content-Type must be application/json. Responses
disable caching, use nosniff and close the connection.

There is **no caller authentication**. Any process or user with access to the
loopback endpoint can submit work. Host/Origin checks reduce browser-driven
cross-origin and DNS-rebinding exposure; they do not authenticate local clients.
Do not expose it through forwarding, a proxy or a network bind.

The supported create_server/serve path limits active workers to eight and
applies a three-second socket inactivity timeout. Excess workers are disconnected.
Requests are capped at 64 KiB. This is not a complete hostile-client sandbox,
rate limiter or wall-clock computation deadline.

Malformed requests receive 400/403/413/415 as appropriate; supported calculation
errors use 422 with E_LEX, E_PARSE, E_DOMAIN or E_LIMIT. Audit failure uses
500/E_AUDIT and withholds the result.

## Audit receipts and gate readiness

Accepted calculation attempts append a JSONL receipt with timestamp, monotonic
duration, precision, engine version, expression hash and response hash. Raw
expressions/results are not stored in the receipt, though hashes are not
anonymization. Invalid transport/request shapes are rejected before calculation
and are not receipted.

Writers for the same normalized path serialize within one process, reject
nonfinite/oversized records and incomplete trailing lines, flush and fsync.
New Unix files use mode 0600; Windows permissions follow the containing directory.
Use a private, trusted receipt directory. Existing permissions are not changed.
Direct symlinks are refused, but path checks are not race-proof and cross-process
locking, hash-chained storage, rotation and retention are not supplied.
Appending does not make the underlying file tamper-proof. Receipt disk growth
needs external management.

The MIT donor gate evaluator is adapted to parse bounded conditions completely,
without substituting context values into syntax. Empty/malformed conditions are
errors; quoted operator words remain data. The harness validates gate IDs and
reports readiness only. No G0–G9 certification is granted.

## Resource limits and compatibility

Expressions: 4,096 characters, 1,024 tokens, 64 parser-call nesting levels and
200 AST levels. Numeric literals have a 400-digit budget (including exponent
digits), scientific exponents at most 400, and integer powers at most 4,096.
Exact numerator/denominator results are limited to 8,192 bits; power preflight
uses a conservative upper bound and can reject operations whose reduced result
would be smaller.

Decimal adjusted exponents are bounded to ±10,000. Trigonometric argument
adjusted exponents above 100 are rejected; argument reduction uses extra digits
for large exact inputs. Tangent is rejected near a numerically unresolved pole.
These are engineering limits, not source-approved performance certifications.

Version 0.1.1-partial -> 0.1.2a1 changes numeric limits, canonical rational
parentheses, zero-power behavior, HTTP validation and gate parsing. Clients must
send an integer precision, correct Host and JSON content type. Tests that
previously rejected quotes now confirm safe literal handling; empty conditions
no longer pass.

103 tests include 53 inherited checks and 50 regressions. Source and installed-
wheel results: [CHECK_RUNS](docs/CHECK_RUNS.json). See [AUDIT](docs/AUDIT.md) and
[SECURITY](SECURITY.md). CI covers Linux Python 3.10/3.12/3.14 and Windows Python
3.12. These checks do not establish formal Windows qualification or certification.

The original 1,187-item program, D0 approvals, G0–G9 certification, QAM integration,
formal error bounds, performance qualification and signed release provenance
remain open. Historical program records are retained in docs.

## License

Copyright 2026 **RUSSELL PHILIP SMITHSON**.
Original project code: [Apache License 2.0](LICENSE), with [NOTICE](NOTICE).
The adapted Microsoft gate evaluator and donor-derived tests retain MIT
licensing; see [THIRD-PARTY-NOTICES](THIRD-PARTY-NOTICES.md).
