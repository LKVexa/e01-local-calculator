> Original source decisions remain provisional. Version 0.1.2a1 adds the engineering limits and HTTP controls documented in README.md; this does not certify D0 decisions.

# Provisional assumptions (unapproved D0 decisions)

Per the package orchestrator rule, downstream prototype work may proceed
against explicitly provisional assumptions but cannot be certified until
the owner approves the corresponding D0 decision and compatibility is
re-verified. Every entry below is **BLOCKED on owner approval**.

| D0 item | Provisional value used by this build |
|---|---|
| D0.1 (n=0 vs n=1 boundary) | The protected boundary is the evaluation kernel `engine.evaluate` (single level). No layer reconciliation is claimed. |
| D0.2 (zero side effects) | Prohibited inside the kernel: file, network, environment, clock, randomness, spawn, and host-state mutation. Authorized effects: none inside the kernel. |
| D0.2.03 (receipt boundary) | Audit/receipt emission happens in the server layer, outside the protected boundary. |
| D0.2.04 (audit egress failure) | Fail closed: the result is withheld with error `E_AUDIT` when a receipt cannot be recorded. |
| D0.3 (local 127 server contract) | HTTP/1.1 + JSON on IPv4 loopback `127.0.0.1` only; IPv6 not bound; loopback-only exposure mandatory; port configurable, default ephemeral; no caller authentication (any process/user able to reach loopback can connect). |
| D0.4 (performance boundary) | Not frozen. No performance claims are made. |
| D0.5 (execution topology) | Parser, evaluator, and receipt sink modeled in-process; QAM adapters and external ledger not integrated. |
| Numeric limits (P4-adjacent) | MAX_EXPRESSION_LENGTH=4096, MAX_TOKENS=1024, MAX_DEPTH=64, MAX_EXPONENT=4096, MAX_NUMBER_DIGITS=400, precision 1..200 (default 50). These are provisional engineering values, not source-approved constants. |

QAM-R(Z8, A20, q0)[2|4|2] alignment (A1.1) is **BLOCKED**: the QAM-deepML
reference framework is defined outside this carrier and no approved
integration contract was available to this build.
