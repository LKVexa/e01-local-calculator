import http.client
import json
import os
import socket
import subprocess
import sys
import tempfile
import threading
import time
import unittest

from e01_calculator import engine
from e01_calculator.server import CalculatorHandler, ThreadingHTTPServer
from e01_calculator.receipts import ReceiptWriter


class ZeroSideEffectConformance(unittest.TestCase):
    """Provisional D0.2.05 conformance: engine.evaluate performs no I/O."""

    def test_no_filesystem_or_network_effects(self):
        opened = []
        real_open = open
        real_socket = socket.socket

        def spy_open(*a, **k):
            opened.append(a[0] if a else k.get("file"))
            return real_open(*a, **k)

        def deny_socket(*a, **k):
            raise AssertionError("engine attempted to create a socket")

        import builtins
        builtins.open = spy_open
        socket.socket = deny_socket
        try:
            engine.evaluate("sqrt(2) + 1/3 + sin(1)", precision=40)
            engine.evaluate("2^100 * 3^50")
        finally:
            builtins.open = real_open
            socket.socket = real_socket
        self.assertEqual(opened, [], "engine opened files during evaluation")

    def test_determinism(self):
        a = engine.evaluate("sin(2) + sqrt(5) - pi/7", precision=45)
        b = engine.evaluate("sin(2) + sqrt(5) - pi/7", precision=45)
        self.assertEqual(str(a.value), str(b.value))


class LoopbackServer(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.tmp = tempfile.mkdtemp()
        cls.receipts = os.path.join(cls.tmp, "receipts.jsonl")
        CalculatorHandler.receipt_writer = ReceiptWriter(cls.receipts)
        cls.httpd = ThreadingHTTPServer(("127.0.0.1", 0), CalculatorHandler)
        cls.port = cls.httpd.server_address[1]
        cls.thread = threading.Thread(target=cls.httpd.serve_forever, daemon=True)
        cls.thread.start()

    @classmethod
    def tearDownClass(cls):
        cls.httpd.shutdown()
        cls.httpd.server_close()

    def post(self, body):
        conn = http.client.HTTPConnection("127.0.0.1", self.port, timeout=5)
        conn.request("POST", "/v1/calculate", json.dumps(body),
                     {"Content-Type": "application/json"})
        resp = conn.getresponse()
        data = json.loads(resp.read().decode())
        conn.close()
        return resp.status, data

    def test_health(self):
        conn = http.client.HTTPConnection("127.0.0.1", self.port, timeout=5)
        conn.request("GET", "/v1/health")
        resp = conn.getresponse()
        self.assertEqual(resp.status, 200)
        conn.close()

    def test_calculate_exact(self):
        status, data = self.post({"expression": "1/3 + 1/6"})
        self.assertEqual(status, 200)
        self.assertEqual(data["result"]["rational"], "1/2")
        self.assertTrue(data["result"]["exact"])

    def test_calculate_inexact(self):
        status, data = self.post({"expression": "sqrt(2)", "precision": 20})
        self.assertEqual(status, 200)
        self.assertFalse(data["result"]["exact"])
        self.assertTrue(data["result"]["decimal"].startswith("1.41421356"))

    def test_domain_error(self):
        status, data = self.post({"expression": "1/0"})
        self.assertEqual(status, 422)
        self.assertEqual(data["error"]["code"], "E_DOMAIN")

    def test_bad_request(self):
        status, data = self.post({"nope": 1})
        self.assertEqual(status, 400)

    def test_receipts_written(self):
        before = self._receipt_count()
        self.post({"expression": "2+2"})
        after = self._receipt_count()
        self.assertEqual(after, before + 1)
        with open(self.receipts) as fh:
            last = json.loads(fh.readlines()[-1])
        self.assertIn("expression_sha256", last)
        self.assertNotIn("expression", last)  # no raw input in receipts

    def _receipt_count(self):
        if not os.path.exists(self.receipts):
            return 0
        with open(self.receipts) as fh:
            return sum(1 for _ in fh)

    def test_loopback_only_binding(self):
        # The listening socket must be bound to 127.0.0.1, not wildcard.
        self.assertEqual(self.httpd.server_address[0], "127.0.0.1")
        # A connection attempt to a non-loopback local address must fail.
        host_ip = None
        try:
            probe = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
            probe.connect(("192.0.2.1", 9))  # RFC5737, no packets sent
            host_ip = probe.getsockname()[0]
            probe.close()
        except OSError:
            self.skipTest("no non-loopback interface available")
        if host_ip and host_ip != "127.0.0.1":
            with self.assertRaises(OSError):
                s = socket.create_connection((host_ip, self.port), timeout=1)
                s.close()

    def test_refuses_non_loopback_serve(self):
        from e01_calculator.server import serve
        with self.assertRaises(SystemExit):
            serve(0, os.path.join(self.tmp, "x.jsonl"), host="0.0.0.0")


if __name__ == "__main__":
    unittest.main()
