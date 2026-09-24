"""Gate-condition harness for the E01 verification workflow.

Evaluates declarative gate conditions from ``docs/gates.json`` against the
recorded check results, using the safe (no eval/exec) condition evaluator
retrieved from the GitHub Junkyard donor repository
``amplifier-collection-recipes`` (MIT; see vendor/ and
THIRD-PARTY-NOTICES.md). This harness only *reports* gate readiness; it
never marks a certification gate G0-G9 as PASSED — those remain
independent human evidence decisions per the source package.
"""

from __future__ import annotations

import json
from typing import Any

from .vendor.gate_condition_evaluator import ExpressionError, evaluate_condition


def evaluate_gate_readiness(gates_manifest: dict, check_results: dict[str, Any]) -> dict:
    """Return {gate_id: {"condition": ..., "condition_met": bool|"ERROR"}}."""
    if type(gates_manifest) is not dict or type(check_results) is not dict:
        raise ValueError("manifest and check results must be objects")
    gates = gates_manifest.get("gates")
    if type(gates) is not list or len(gates) > 100:
        raise ValueError("manifest must contain at most 100 gates")
    try:
        encoded = json.dumps([gates_manifest, check_results], allow_nan=False)
        if len(encoded) > 1048576:
            raise ValueError("gate input exceeds 1 MiB")
    except (TypeError, ValueError, RecursionError) as exc:
        raise ValueError("invalid gate input") from exc
    out = {}
    note = "condition readiness only; gate certification requires an independent human evidence decision (not claimed)"
    for gate in gates:
        if type(gate) is not dict or type(gate.get("id")) is not str or not gate["id"].strip() or len(gate["id"]) > 128:
            raise ValueError("invalid gate identifier")
        gate_id = gate["id"]
        if gate_id in out:
            raise ValueError("duplicate gate identifier")
        condition = gate.get("condition", "")
        try:
            met = evaluate_condition(condition, check_results)
        except ExpressionError as exc:
            out[gate_id] = {"condition": condition, "condition_met": "ERROR",
                            "error": str(exc), "note": note}
            continue
        out[gate_id] = {
            "condition": condition,
            "condition_met": met,
            "note": "condition readiness only; gate certification requires an "
                    "independent human evidence decision (not claimed)",
        }
    return out


def main(gates_path: str, results_path: str) -> int:
    with open(gates_path, encoding="utf-8") as fh:
        gates = json.load(fh)
    with open(results_path, encoding="utf-8") as fh:
        results = json.load(fh)
    report = evaluate_gate_readiness(gates, results)
    print(json.dumps(report, indent=2))
    return 0


if __name__ == "__main__":
    import sys
    sys.exit(main(sys.argv[1], sys.argv[2]))
