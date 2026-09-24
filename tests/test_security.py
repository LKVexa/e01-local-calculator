import concurrent.futures
import http.client
import json
import math
import os
import tempfile
import threading
import unittest
from decimal import Inexact, ROUND_DOWN, localcontext
from unittest.mock import patch

from e01_calculator import engine, server
from e01_calculator.gates import evaluate_gate_readiness
from e01_calculator.receipts import ReceiptWriter
from e01_calculator.vendor.gate_condition_evaluator import ExpressionError, evaluate_condition


class EngineRegressions(unittest.TestCase):
    def test_nested_power_bounded_before_allocation(self):
        for expression in ("(2^4096)^4096", "(1e400)^4096", "(2^-4096)^4096"):
            with self.subTest(expression=expression), self.assertRaises(engine.LimitError):
                engine.evaluate(expression)

    def test_long_flat_tree_has_stable_limit_error(self):
        with self.assertRaises(engine.LimitError):
            engine.evaluate("+".join(["1"] * 400))

    def test_canonical_fraction_preserves_power_meaning(self):
        for expression in ("0.4^2", "0.25^-2", "2^0.5", "0.4(1+2)"):
            canonical = engine.canonicalize(engine.parse(expression))
            if expression == "2^0.5":
                with self.assertRaises(engine.DomainError):
                    engine.evaluate(canonical)
            else:
                self.assertEqual(engine.evaluate(expression), engine.evaluate(canonical))

    def test_decimal_negation_keeps_requested_precision(self):
        positive = engine.evaluate("sqrt(2)", 100).value
        self.assertEqual(engine.evaluate("-sqrt(2)", 100).value, positive.copy_negate())

    def test_global_decimal_settings_do_not_change_result(self):
        expected = engine.evaluate("-sin(1)+sqrt(2)+pi/7", 70)
        with localcontext() as context:
            context.prec = 3
            context.rounding = ROUND_DOWN
            context.Emax = 2
            context.Emin = -2
            context.traps[Inexact] = True
            result = engine.evaluate("-sin(1)+sqrt(2)+pi/7", 70)
            self.assertEqual(result, expected)
            self.assertEqual(context.prec, 3)
            self.assertTrue(context.traps[Inexact])

    def test_exact_render_ignores_global_context(self):
        expected = engine.evaluate("1/3").as_strings()
        with localcontext() as context:
            context.prec = 2
            context.traps[Inexact] = True
            self.assertEqual(engine.evaluate("1/3").as_strings(), expected)

    def test_noninteger_exact_exponent_cannot_round_to_integer(self):
        with self.assertRaises(engine.DomainError):
            engine.evaluate("pi^(1+1e-100)", 10)

    def test_zero_to_nonpositive_power_is_consistent(self):
        for expression in ("0^0", "0^-1", "(pi-pi)^0", "(pi-pi)^-1"):
            with self.subTest(expression=expression), self.assertRaises(engine.DomainError):
                engine.evaluate(expression)

    def test_decimal_overflow_returns_limit_error(self):
        with self.assertRaises(engine.LimitError):
            engine.evaluate("exp(1e400)")

    def test_decimal_underflow_returns_limit_error(self):
        with self.assertRaises(engine.LimitError):
            engine.evaluate("exp(-1e400)")

    def test_trig_magnitude_limit(self):
        with self.assertRaises(engine.LimitError):
            engine.evaluate("sin(1e101)")

    def test_large_exact_trig_argument_keeps_reduction_digits(self):
        result = engine.evaluate("sin(100000000000000000001)", 40)
        # Precision-stability check using the same algorithm at higher precision;
        # this is not an independent numerical oracle.
        shifted = engine.evaluate("sin(100000000000000000001)", 80)
        self.assertAlmostEqual(float(result.value), float(shifted.value), places=14)

    def test_tangent_near_pole_fails_closed(self):
        with self.assertRaises(engine.DomainError):
            engine.evaluate("tan(pi/2)", 50)

    def test_inexact_operations_do_not_change_global_flags(self):
        with localcontext() as context:
            context.clear_flags()
            before = dict(context.flags)
            engine.evaluate("pi+sqrt(2)", 50)
            self.assertEqual(context.flags, before)

    def test_exact_output_remains_serializable_near_budget(self):
        result = engine.evaluate("2^4096").as_strings()
        self.assertEqual(int(result["integer"]), 2 ** 4096)

    def test_large_scientific_literals_canonicalize_within_literal_limits(self):
        for expression in ("1e400", "1e-400", "9" * 397 + "e400"):
            with self.subTest(expression=expression):
                canonical = engine.canonicalize(engine.parse(expression))
                self.assertEqual(engine.evaluate(expression), engine.evaluate(canonical))

    def test_small_trig_argument_converges_without_underflow(self):
        self.assertEqual(engine.evaluate("sin(1e-400)", 50).value,
                         engine.Decimal("1e-400"))


class GateRegressions(unittest.TestCase):
    def test_operators_in_strings_are_data(self):
        self.assertTrue(evaluate_condition("{{x}} == 'a or b'", {"x": "a or b"}))
        self.assertTrue(evaluate_condition("{{x}} == 'a and b'", {"x": "a and b"}))

    def test_no_short_circuit_syntax_bypass(self):
        for expression in ("true or junk junk", "false and {{missing}}", "true or ("):
            with self.subTest(expression=expression), self.assertRaises(ExpressionError):
                evaluate_condition(expression, {})

    def test_quote_in_context_is_not_grammar(self):
        self.assertFalse(evaluate_condition("{{x}} == 'ok'", {"x": "a' or true"}))

    def test_empty_gate_is_error_with_boundary_note(self):
        report = evaluate_gate_readiness({"gates": [{"id": "G1"}]}, {})
        self.assertEqual(report["G1"]["condition_met"], "ERROR")
        self.assertIn("not claimed", report["G1"]["note"])

    def test_duplicate_gate_rejected(self):
        with self.assertRaises(ValueError):
            evaluate_gate_readiness({"gates": [{"id": "G1"}, {"id": "G1"}]}, {})

    def test_gate_input_shapes(self):
        for manifest in (None, [], {"gates": "bad"}, {"gates": [None]}):
            with self.subTest(manifest=manifest), self.assertRaises(ValueError):
                evaluate_gate_readiness(manifest, {})

    def test_large_gate_expression_bounded(self):
        report = evaluate_gate_readiness({"gates": [{"id": "G1", "condition": "true " * 1000}]}, {})
        self.assertEqual(report["G1"]["condition_met"], "ERROR")

    def test_large_context_scalar_error_contract(self):
        for value in ("x" * 65537, 10 ** 5000):
            with self.assertRaises(ExpressionError):
                evaluate_condition("{{value}} == 'x'", {"value": value})


class ReceiptRegressions(unittest.TestCase):
    def test_nonfinite_receipt_rejected(self):
        with tempfile.TemporaryDirectory() as directory:
            writer = ReceiptWriter(os.path.join(directory, "audit.jsonl"))
            with self.assertRaises(ValueError):
                writer.append({"value": float("nan")})
            self.assertFalse(os.path.exists(writer.path))

    def test_truncated_receipt_tail_blocks_append(self):
        with tempfile.TemporaryDirectory() as directory:
            path = os.path.join(directory, "audit.jsonl")
            with open(path, "wb") as stream:
                stream.write(b'{"incomplete":')
            with self.assertRaises(OSError):
                ReceiptWriter(path).append({"status": 200})
            with open(path, "rb") as stream:
                self.assertEqual(stream.read(), b'{"incomplete":')

    def test_multiple_writers_share_serialization(self):
        with tempfile.TemporaryDirectory() as directory:
            path = os.path.join(directory, "audit.jsonl")
            writers = [ReceiptWriter(path) for _ in range(4)]
            def append(index):
                writers[index % 4].append({"index": index})
            with concurrent.futures.ThreadPoolExecutor(max_workers=8) as pool:
                list(pool.map(append, range(40)))
            with open(path) as stream:
                rows = [json.loads(line) for line in stream]
            self.assertEqual({row["index"] for row in rows}, set(range(40)))

    def test_oversized_receipt_rejected(self):
        with tempfile.TemporaryDirectory() as directory:
            with self.assertRaises(ValueError):
                ReceiptWriter(os.path.join(directory, "audit")).append({"x": "x" * 65536})


class HTTPRegressions(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.directory = tempfile.TemporaryDirectory()
        cls.path = os.path.join(cls.directory.name, "receipts.jsonl")
        cls.httpd = server.create_server(0, cls.path)
        cls.port = cls.httpd.server_address[1]
        cls.thread = threading.Thread(target=cls.httpd.serve_forever, daemon=True)
        cls.thread.start()

    @classmethod
    def tearDownClass(cls):
        cls.httpd.shutdown()
        cls.httpd.server_close()
        cls.thread.join(timeout=5)
        cls.directory.cleanup()

    def request(self, body='{"expression":"1+1"}', headers=None):
        connection = http.client.HTTPConnection("127.0.0.1", self.port, timeout=5)
        try:
            connection.request("POST", "/v1/calculate", body,
                               {"Content-Type": "application/json", **(headers or {})})
            response = connection.getresponse()
            return response.status, json.loads(response.read()), dict(response.getheaders())
        finally:
            connection.close()

    def test_precision_is_not_coerced(self):
        for value in (True, "20", 12.5, None):
            with self.subTest(value=value):
                status, payload, _ = self.request(json.dumps({"expression": "1", "precision": value}))
                self.assertEqual(status, 400)
                self.assertEqual(payload["error"]["code"], "E_REQUEST")

    def test_precision_range_remains_engine_error(self):
        status, payload, _ = self.request('{"expression":"1","precision":201}')
        self.assertEqual(status, 422)
        self.assertEqual(payload["error"]["code"], "E_LIMIT")

    def test_duplicate_json_rejected(self):
        self.assertEqual(self.request('{"expression":"1","expression":"2"}')[0], 400)

    def test_json_nonfinite_rejected(self):
        self.assertEqual(self.request('{"expression":"1","precision":NaN}')[0], 400)

    def test_json_shapes_rejected(self):
        for body in ("[]", "null", '"text"', '{"expression":"1","extra":2}'):
            with self.subTest(body=body):
                self.assertEqual(self.request(body)[0], 400)

    def test_lone_surrogate_rejected(self):
        self.assertEqual(self.request('{"expression":"\\ud800"}')[0], 400)

    def test_cross_origin_rejected(self):
        self.assertEqual(self.request(headers={"Origin": "https://example.com"})[0], 403)

    def test_unexpected_host_rejected(self):
        self.assertEqual(self.request(headers={"Host": "example.com"})[0], 403)

    def test_same_origin_supported(self):
        self.assertEqual(self.request(headers={"Origin": f"http://127.0.0.1:{self.port}"})[0], 200)

    def test_plain_text_body_rejected(self):
        self.assertEqual(self.request(headers={"Content-Type": "text/plain"})[0], 415)

    def test_transfer_encoding_rejected(self):
        self.assertEqual(self.request(headers={"Transfer-Encoding": "chunked"})[0], 400)

    def test_response_caching_disabled(self):
        status, _, headers = self.request()
        self.assertEqual(status, 200)
        self.assertEqual(headers["Cache-Control"], "no-store")
        self.assertEqual(headers["X-Content-Type-Options"], "nosniff")

    def test_receipt_failure_withholds_result(self):
        with patch.object(self.httpd.receipt_writer, "append", side_effect=OSError("unavailable")):
            status, payload, _ = self.request()
        self.assertEqual(status, 500)
        self.assertEqual(payload["error"]["code"], "E_AUDIT")
        self.assertNotIn("result", payload)

    def test_receipt_records_precision_and_response_digest(self):
        self.request('{"expression":"sqrt(2)","precision":30}')
        with open(self.path) as stream:
            row = json.loads(stream.readlines()[-1])
        self.assertEqual(row["precision"], 30)
        self.assertEqual(row["engine_version"], "0.1.2a1")
        self.assertEqual(len(row["response_sha256"]), 64)
        self.assertNotIn("expression", row)

    def test_engine_resource_error_is_json(self):
        status, payload, _ = self.request('{"expression":"(2^4096)^4096"}')
        self.assertEqual(status, 422)
        self.assertEqual(payload["error"]["code"], "E_LIMIT")

    def test_servers_do_not_share_receipt_sink(self):
        other_path = os.path.join(self.directory.name, "other.jsonl")
        other = server.create_server(0, other_path)
        try:
            self.assertNotEqual(other.receipt_writer.path, self.httpd.receipt_writer.path)
            self.assertIsNot(other.receipt_writer, self.httpd.receipt_writer)
        finally:
            other.server_close()

    def test_non_loopback_factory_rejected(self):
        with self.assertRaises(SystemExit):
            server.create_server(0, self.path, "0.0.0.0")

    def test_invalid_port_rejected(self):
        for port in (-1, 65536, True, "8123"):
            with self.subTest(port=port), self.assertRaises(ValueError):
                server.create_server(port, self.path)

    def test_duplicate_length_header_rejected(self):
        connection = http.client.HTTPConnection("127.0.0.1", self.port, timeout=5)
        try:
            connection.putrequest("POST", "/v1/calculate")
            connection.putheader("Content-Type", "application/json")
            connection.putheader("Content-Length", "18")
            connection.putheader("Content-Length", "18")
            connection.endheaders(b'{"expression":"1"}')
            response = connection.getresponse()
            self.assertEqual(response.status, 400)
            self.assertEqual(json.loads(response.read())["error"]["code"], "E_REQUEST")
        finally:
            connection.close()

    def test_body_limit_rejected_before_read(self):
        connection = http.client.HTTPConnection("127.0.0.1", self.port, timeout=5)
        try:
            connection.putrequest("POST", "/v1/calculate")
            connection.putheader("Content-Type", "application/json")
            connection.putheader("Content-Length", str(server.MAX_BODY_BYTES + 1))
            connection.endheaders()
            response = connection.getresponse()
            self.assertEqual(response.status, 413)
            response.read()
        finally:
            connection.close()

    def test_duplicate_host_rejected(self):
        connection = http.client.HTTPConnection("127.0.0.1", self.port, timeout=5)
        try:
            connection.putrequest("GET", "/v1/health")
            connection.putheader("Host", "example.com")
            connection.endheaders()
            response = connection.getresponse()
            self.assertEqual(response.status, 403)
            response.read()
        finally:
            connection.close()
