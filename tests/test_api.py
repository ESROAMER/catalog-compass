import json
import threading
import unittest
from urllib.error import HTTPError
from urllib.request import build_opener, ProxyHandler, Request
from http.server import ThreadingHTTPServer
from app import Handler
from catalog_check.samples import supplier_demo


class ApiTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.server = ThreadingHTTPServer(("127.0.0.1", 0), Handler)
        cls.thread = threading.Thread(target=cls.server.serve_forever, daemon=True)
        cls.thread.start()
        cls.base = f"http://127.0.0.1:{cls.server.server_port}"
        cls.opener = build_opener(ProxyHandler({}))

    @classmethod
    def tearDownClass(cls):
        cls.server.shutdown()
        cls.server.server_close()

    def post(self, path, data, origin=None):
        headers = {"Content-Type": "application/json"}
        if origin:
            headers["Origin"] = origin
        req = Request(self.base + path, json.dumps(data).encode(), headers)
        return self.opener.open(req)

    def payload(self):
        return {"csv": supplier_demo(), "mapping": {"sku": "Item ref", "name": "Display label", "regular_price": "List amount", "sale_price": "Deal amount", "currency": "Money", "stock": "Units available", "barcode": "GTIN", "product_type": "Kind"}}

    def test_sample_to_report_and_export(self):
        with self.post("/api/profile", self.payload()) as response:
            self.assertEqual(json.load(response)["row_count"], 10)
        with self.post("/api/check", self.payload()) as response:
            result = json.load(response)
        self.assertEqual(result["summary"]["total_rows"], 10)
        self.assertGreater(result["summary"]["error_count"], 0)
        with self.post("/api/export", {**self.payload(), "kind": "issues"}) as response:
            self.assertIn("attachment", response.headers["Content-Disposition"])
            self.assertIn("00083", response.read().decode())

    def test_unknown_sample_and_path_traversal(self):
        for route in ["/api/samples/unknown", "/../app.py"]:
            with self.assertRaises(HTTPError) as error:
                self.opener.open(self.base + route)
            self.assertIn(error.exception.code, (400, 404))

    def test_cross_origin_write_denied(self):
        with self.assertRaises(HTTPError) as error:
            self.post("/api/check", self.payload(), "https://example.com")
        self.assertEqual(error.exception.code, 403)

    def test_unmapped_required_field_denied(self):
        data = self.payload()
        data["mapping"].pop("regular_price")
        with self.assertRaises(HTTPError) as error:
            self.post("/api/check", data)
        self.assertEqual(error.exception.code, 400)

    def test_reusing_source_column_denied(self):
        data = self.payload()
        data["mapping"]["sale_price"] = "List amount"
        with self.assertRaises(HTTPError) as error:
            self.post("/api/check", data)
        self.assertEqual(error.exception.code, 400)


if __name__ == "__main__":
    unittest.main()
