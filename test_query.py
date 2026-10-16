#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""query.py 的单元测试（仅标准库；xlsx 缓存用例在缺少 openpyxl 时跳过）。"""

import os
import tempfile
import unittest

import query

query.configure_console()


def make_product(**overrides):
    p = {
        "model": "T2\n曲面超薄",
        "features": "1. 超薄9mm曲面屏；",
        "specs": "1.93英寸 AMOLED",
        "colors": "黑色\n银色",
        "app": "GloryFit",
        "price": 95,
        "remark": "量产出货中",
    }
    p.update(overrides)
    p["_l"] = {k: p[k].lower() for k in query.SEARCH_COLUMNS}
    return p


class NormalizeCellTests(unittest.TestCase):
    def test_none_and_whitespace(self):
        self.assertEqual(query.normalize_cell(None), "")
        self.assertEqual(query.normalize_cell("  曲面  "), "曲面")

    def test_preserves_inner_text(self):
        self.assertEqual(query.normalize_cell(95), "95")


class SearchTests(unittest.TestCase):
    def setUp(self):
        self.t2 = make_product(
            model="T2\n曲面超薄",
            features="1. 超薄9mm曲面屏；\n2. 支持GPS定位",
            specs="1.93英寸 AMOLED 曲面屏",
            colors="黑色",
        )
        self.t1 = make_product(
            model="T1\n曲面超薄",
            features="1. 超薄外观；",
            specs="1.91英寸 TFT",
            colors="粉色",
        )
        self.products = [self.t2, self.t1]

    def test_and_mode_requires_every_term(self):
        results = query.search(self.products, ["曲面", "gps"], "and")
        self.assertEqual([p["model"] for _s, p, _f in results], ["T2\n曲面超薄"])

    def test_or_mode_returns_any_hit(self):
        results = query.search(self.products, ["曲面", "gps"], "or")
        self.assertEqual(len(results), 2)

    def test_model_weight_outranks_feature_hit(self):
        gps_model = make_product(model="GPS\n运动款", features="普通功能", specs="")
        results = query.search([self.t2, gps_model], ["gps"], "and")
        self.assertEqual([p["model"] for _s, p, _f in results],
                         ["GPS\n运动款", "T2\n曲面超薄"])

    def test_tie_breaks_by_model(self):
        a = make_product(model="A1", features="曲面")
        b = make_product(model="B1", features="曲面")
        results = query.search([b, a], ["曲面"], "and")
        self.assertEqual([p["model"] for _s, p, _f in results], ["A1", "B1"])

    def test_case_insensitive(self):
        results = query.search(self.products, ["Gps"], "and")
        self.assertTrue(results)


class ColorizeTests(unittest.TestCase):
    def test_returns_original_when_color_off(self):
        self.assertEqual(query.colorize("支持GPS定位", ["gps"]), "支持GPS定位")

    def test_highlights_and_merges_overlapping_spans(self):
        old = query._USE_COLOR
        query._USE_COLOR = True
        try:
            result = query.colorize("GPSGPS定位", ["gps"])
            self.assertEqual(result.count("\033"), 2)  # 一个合并区间 = 起止两个转义
        finally:
            query._USE_COLOR = old


class ContextLineTests(unittest.TestCase):
    def test_context_line_uses_non_model_field(self):
        p = make_product(features="1. 曲面屏；\n2. GPS定位")
        fields = {"gps": ["features"]}
        self.assertIn("GPS定位", query.context_line(p, fields))

    def test_context_line_empty_for_model_only_hit(self):
        p = make_product(model="曲面T9", features="普通功能", specs="", colors="")
        fields = {"曲面": ["model"]}
        self.assertEqual(query.context_line(p, fields), "")


class LoadProductsTests(unittest.TestCase):
    @unittest.skipUnless(
        __import__("importlib").util.find_spec("openpyxl"),
        "需要 openpyxl 才能构造测试 xlsx",
    )
    def test_load_products_builds_and_reuses_cache(self):
        from openpyxl import Workbook

        with tempfile.TemporaryDirectory() as tmp:
            source = os.path.join(tmp, "产品测试.xlsx")
            wb = Workbook()
            ws = wb.active
            header = ["序号", "型号", "产品图", "功能特点说明", "参数规格",
                      "APP", "标准颜色", "未税价格", "备注"]
            ws.append(header)
            ws.append(header)  # 数据从第 3 行开始读
            ws.append(["1", "X1", "", "功能", "参数", "GloryFit", "黑色", 99, "备注"])
            wb.save(source)

            cache_path = os.path.join(tmp, "products.cache.json")
            old_cache = query.CACHE_PATH
            query.CACHE_PATH = cache_path
            try:
                products, rebuilt = query.load_products(source)
                self.assertTrue(rebuilt)
                self.assertEqual(len(products), 1)
                self.assertEqual(products[0]["model"], "X1")

                products_again, rebuilt_again = query.load_products(source)
                self.assertFalse(rebuilt_again)
                self.assertEqual(products_again, products)
            finally:
                query.CACHE_PATH = old_cache


if __name__ == "__main__":
    unittest.main()
