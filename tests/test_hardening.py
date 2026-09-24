"""Focused regression tests for the A017 hardening findings (v0.1.1-partial)."""

import json
import threading
import unittest
from fractions import Fraction
from http.server import ThreadingHTTPServer
import http.client
import os
import tempfile

from e01_calculator import engine
from e01_calculator import server as srv
from e01_calculator.receipts import ReceiptWriter
from e01_calculator.vendor.gate_condition_evaluator import (
    ExpressionError, evaluate_condition)


class TestF1SqrtOverflow(unittest.TestCase):
    def test_sqrt_of_huge_int_no_overflow(self):
        # 400-digit non-square: previously raised bare OverflowError
        r = engine.evaluate("sqrt(" + "9" * 400 + ")")
        self.assertFalse(r.exact)

    def test_sqrt_of_huge_perfect_square_exact(self):
        n = 10 ** 150
        r = engine.evaluate(f"sqrt({n * n})")
        self.assertTrue(r.exact)
        self.assertEqual(r.value, Fraction(n))

    def test_sqrt_small_still_works(self):
        self.assertEqual(engine.evaluate("sqrt(9)").value, Fraction(3))


class TestF2NonStringExpression(unittest.TestCase):
    def test_parse_non_string_raises_calcerror(self):
        for bad in (123, ["1+1"], None, {"a": 1}):
            with self.assertRaises(engine.CalcError):
                engine.parse(bad)

    def test_evaluate_non_string_raises_calcerror(self):
        with self.assertRaises(engine.ParseError):
            engine.evaluate(123)


class TestF3ConditionInjection(unittest.TestCase):
    def test_quote_splice_rejected(self):
        ctx = {"status": "a' == 'a' or 'b' == 'b"}
        self.assertFalse(evaluate_condition("{{status}} == 'success'", ctx))

    def test_double_quote_splice_rejected(self):
        ctx = {"status": 'x" == "x'}
        self.assertFalse(evaluate_condition('{{status}} == "success"', ctx))

    def test_legitimate_values_still_work(self):
        self.assertTrue(evaluate_condition("{{s}} == 'ok'", {"s": "ok"}))
        self.assertFalse(evaluate_condition("{{s}} == 'ok'", {"s": "no"}))


class TestF4ExponentLiteralBound(unittest.TestCase):
    def test_huge_scientific_exponent_rejected(self):
        with self.assertRaises(engine.LimitError):
            engine.evaluate("1e999999")
        with self.assertRaises(engine.LimitError):
            engine.evaluate("1e-999999")

    def test_reasonable_scientific_exponent_ok(self):
        r = engine.evaluate("1e400")
        self.assertTrue(r.exact)
        self.assertEqual(r.value, Fraction(10) ** 400)


class TestF5PrecisionType(unittest.TestCase):
    def test_non_int_precision_raises_limit_error(self):
        for bad in ("50", 12.5, None, True):
            with self.assertRaises(engine.LimitError):
                engine.evaluate("sqrt(2)", precision=bad)

    def test_int_precision_still_works(self):
        r = engine.evaluate("sqrt(2)", precision=10)
        self.assertFalse(r.exact)
        self.assertEqual(r.precision, 10)


class TestF6DecimalPathExponentBound(unittest.TestCase):
    def test_decimal_path_exponent_bounded(self):
        with self.assertRaises(engine.LimitError):
            engine.evaluate("pi^100000")

    def test_decimal_path_exponent_within_bound_ok(self):
        r = engine.evaluate("pi^2")
        self.assertFalse(r.exact)


class TestServerErrorContract(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.tmp = tempfile.mkdtemp()
        srv.CalculatorHandler.receipt_writer = ReceiptWriter(
            os.path.join(cls.tmp, "receipts.jsonl"))
        cls.httpd = ThreadingHTTPServer(("127.0.0.1", 0), srv.CalculatorHandler)
        cls.port = cls.httpd.server_address[1]
        threading.Thread(target=cls.httpd.serve_forever, daemon=True).start()

    @classmethod
    def tearDownClass(cls):
        cls.httpd.shutdown()
        cls.httpd.server_close()

    def _post(self, body):
        c = http.client.HTTPConnection("127.0.0.1", self.port, timeout=5)
        try:
            c.request("POST", "/v1/calculate", json.dumps(body),
                      {"Content-Type": "application/json"})
            r = c.getresponse()
            return r.status, json.loads(r.read().decode())
        finally:
            c.close()

    def test_non_string_expression_gets_json_400(self):
        for bad in (123, ["1+1"], None, {"x": 1}):
            status, payload = self._post({"expression": bad})
            self.assertEqual(status, 400)
            self.assertEqual(payload["error"]["code"], "E_REQUEST")

    def test_huge_sqrt_gets_json_error_not_disconnect(self):
        status, payload = self._post({"expression": "sqrt(" + "9" * 400 + ")"})
        self.assertEqual(status, 200)
        self.assertFalse(payload["result"]["exact"])

    def test_normal_request_unaffected(self):
        status, payload = self._post({"expression": "1+1"})
        self.assertEqual(status, 200)
        self.assertEqual(payload["result"]["integer"], "2")


if __name__ == "__main__":
    unittest.main()
