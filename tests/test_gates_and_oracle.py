import math
import unittest

from e01_calculator import engine
from e01_calculator.gates import evaluate_gate_readiness
from e01_calculator.vendor.gate_condition_evaluator import (ExpressionError,
                                                            evaluate_condition)


class DonorConditionEvaluator(unittest.TestCase):
    """Adapted from the donor repo's own test suite (MIT,
    amplifier-collection-recipes/modules/tool-recipes/tests/test_expression_evaluator.py)."""

    def test_equality(self):
        self.assertTrue(evaluate_condition("{{status}} == 'success'", {"status": "success"}))
        self.assertFalse(evaluate_condition("{{status}} == 'success'", {"status": "failed"}))

    def test_boolean_ops(self):
        ctx = {"a": "x", "b": "y"}
        self.assertTrue(evaluate_condition("{{a}} == 'x' and {{b}} == 'y'", ctx))
        self.assertTrue(evaluate_condition("{{a}} == 'zz' or {{b}} == 'y'", ctx))
        self.assertFalse(evaluate_condition("{{a}} == 'zz' and {{b}} == 'y'", ctx))

    def test_undefined_variable(self):
        with self.assertRaises(ExpressionError):
            evaluate_condition("{{missing}} == '1'", {})

    def test_empty_condition_rejected(self):
        with self.assertRaises(ExpressionError):
            evaluate_condition("", {})


class GateReadiness(unittest.TestCase):
    def test_gate_readiness_never_claims_pass(self):
        gates = {"gates": [
            {"id": "G1", "condition": "{{engine_tests}} == 'pass' and {{server_tests}} == 'pass'"},
            {"id": "G9", "condition": "{{release_signed}} == 'true'"},
        ]}
        results = {"engine_tests": "pass", "server_tests": "pass", "release_signed": "false"}
        rep = evaluate_gate_readiness(gates, results)
        self.assertTrue(rep["G1"]["condition_met"])
        self.assertFalse(rep["G9"]["condition_met"])
        for g in rep.values():
            self.assertNotIn("PASSED", str(g.get("condition_met")))
            self.assertIn("not claimed", g.get("note", "") or "")


class IndependentNumericalOracle(unittest.TestCase):
    """Cross-check the Decimal engine against CPython's libm-based math
    module as an independent implementation, within float tolerance."""

    CASES = [
        ("sqrt(2)", math.sqrt(2)),
        ("sin(1)", math.sin(1)),
        ("cos(2)", math.cos(2)),
        ("tan(0.5)", math.tan(0.5)),
        ("ln(10)", math.log(10)),
        ("log10(7)", math.log10(7)),
        ("exp(3)", math.exp(3)),
        ("pi", math.pi),
        ("e", math.e),
    ]

    def test_against_libm(self):
        for expr, expected in self.CASES:
            r = engine.evaluate(expr, precision=30)
            self.assertAlmostEqual(float(r.value), expected, places=12, msg=expr)

    def test_exact_oracle_fractions(self):
        from fractions import Fraction
        import random
        rng = random.Random(20260914)
        for _ in range(200):
            a, b = rng.randint(-999, 999), rng.randint(1, 999)
            c, d = rng.randint(-999, 999), rng.randint(1, 999)
            expr = f"({a}/{b}) + ({c}/{d})"
            self.assertEqual(engine.evaluate(expr).value,
                             Fraction(a, b) + Fraction(c, d), expr)


if __name__ == "__main__":
    unittest.main()
