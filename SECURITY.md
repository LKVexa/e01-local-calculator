# Security boundaries

The arithmetic kernel performs no file/network I/O. It runs inside the caller's
process, not an OS sandbox, and resource budgets are not comprehensive protection
against hostile Python objects or every computational denial of service.

The service is loopback-only and has no user authentication. All local processes
able to connect can submit work. Host/Origin validation reduces browser-origin
attacks; it does not identify or authorize clients. Do not forward or expose the
port. Worker and socket inactivity bounds do not provide total request deadlines.

Receipt writes occur outside the arithmetic boundary and fail closed. A trusted
private directory is required; directory traversal, concurrent replacement,
cross-process append coordination, disk quotas and retention are operator duties.
New Unix receipt files request mode 0600; Windows ACLs are inherited. The writer
does not change existing permissions, authenticate records or make the log
tamper-proof. Unsalted expression/response hashes can reveal predictable inputs.

HTTP payloads echo the submitted expression to its client. No secret redaction
is performed. Render all text with appropriate escaping. Invalid requests are
not included in calculation receipts.

Working Decimal precision is not a rigorous result-error bound. Do not infer
certified numerical accuracy, risk acceptance or gate certification from a
successful result. Independent numerical qualification remains outside this
candidate. The gate harness reports conditions, never certification.

No third-party runtime dependencies are installed. MIT donor code remains
vendored with attribution; no build-tool vulnerability scan is claimed.
Report defects privately using synthetic expressions and request samples.
