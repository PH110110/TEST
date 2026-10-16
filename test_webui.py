#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""webui.py 的单元测试：API 逻辑契约 + 真实 HTTP 端点冒烟。"""

import json
import threading
import unittest
import urllib.request

import webui

from test_query import make_product


class SearchResponseTests(unittest.TestCase):
    def setUp(self):
        self.products = [
            make_product(
                model="T2\n曲面超薄",
                features="1. 曲面屏；\n2. GPS定位",
                specs="1.93英寸 AMOLED",
                colors="黑色",
            ),
            make_product(model="T1\n曲面超薄", features="普通款", specs="", colors=""),
        ]

    def test_and_mode_and_contract_shape(self):
        payload = webui.build_search_response(self.products, "曲面 gps")
        self.assertEqual(payload["mode"], "AND")
        self.assertEqual(payload["query"], "曲面 gps")
        self.assertEqual(len(payload["results"]), 1)
        item = payload["results"][0]
        self.assertEqual(item["model"], "T2 / 曲面超薄")
        self.assertEqual(item["price"], 95)
        self.assertIn("曲面屏", item["context"])
        self.assertIn("score", item)

    def test_or_fallback_for_multi_keywords(self):
        payload = webui.build_search_response(self.products, "曲面 不存在词")
        self.assertEqual(payload["mode"], "OR")
        self.assertEqual(len(payload["results"]), 2)

    def test_empty_query_returns_empty(self):
        payload = webui.build_search_response(self.products, "   ")
        self.assertEqual(payload["results"], [])


class HttpApiTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.old_products = webui.PRODUCTS
        webui.PRODUCTS = [
            make_product(model="X1", features="曲面屏", specs="", colors=""),
            make_product(model="X2", features="GPS定位", specs="", colors=""),
        ]
        cls.server = webui.make_server(("127.0.0.1", 0))
        cls.port = cls.server.server_address[1]
        cls.thread = threading.Thread(target=cls.server.serve_forever, daemon=True)
        cls.thread.start()

    @classmethod
    def tearDownClass(cls):
        cls.server.shutdown()
        cls.server.server_close()
        cls.thread.join(timeout=5)
        webui.PRODUCTS = cls.old_products

    def fetch_json(self, path):
        with urllib.request.urlopen(f"http://127.0.0.1:{self.port}{path}") as resp:
            return json.load(resp)

    def test_search_endpoint(self):
        payload = self.fetch_json("/api/search?q=%E6%9B%B2%E9%9D%A2")
        self.assertEqual(payload["mode"], "AND")
        self.assertEqual([r["model"] for r in payload["results"]], ["X1"])

    def test_products_endpoint(self):
        payload = self.fetch_json("/api/products")
        self.assertEqual(len(payload["products"]), 2)

    def test_unknown_route_returns_404(self):
        with self.assertRaises(urllib.error.HTTPError) as ctx:
            self.fetch_json("/api/nope")
        self.assertEqual(ctx.exception.code, 404)


if __name__ == "__main__":
    unittest.main()
