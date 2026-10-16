#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""DLD 产品查询器 WebUI —— 本地单页界面 + 轻量 HTTP API。

复用 query.py 的 load_products / search / context_line，不重写匹配逻辑。
仅依赖 Python 标准库；首次读取 xlsx 仍需 openpyxl。

用法：
  python webui.py                  # 127.0.0.1:8000
  python webui.py --port 8080      # 指定端口
  python webui.py --open           # 服务就绪后自动打开浏览器
"""

import argparse
import json
import os
import threading
import urllib.parse
import webbrowser
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

import query

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
WEBUI_PATH = os.path.join(SCRIPT_DIR, "webui.html")
PRODUCTS = None  # 测试可替换；正常启动时由 load_products() 填充


def load_products():
    global PRODUCTS
    if PRODUCTS is None:
        source = query.default_source()
        if source is None:
            raise FileNotFoundError("当前目录没有「产品*.xlsx」，请先放置报价表")
        PRODUCTS, _rebuilt = query.load_products(source)
    return PRODUCTS


def model_text(p):
    return " / ".join(x.strip() for x in p["model"].split("\n") if x.strip())


def result_item(p, fields, terms):
    return {
        "model": model_text(p),
        "price": p["price"],
        "remark": p["remark"],
        "context": query.context_line(p, fields),
        "score": sum(query.WEIGHTS[k] for t in terms for k in fields[t]),
    }


def build_search_response(products, raw_query):
    """API 逻辑缝：纯数据进、契约 JSON 出，便于单元测试。"""
    terms = [t.strip().lower() for t in raw_query.split() if t.strip()]
    if not terms:
        return {"query": raw_query, "mode": "AND", "results": []}
    results = query.search(products, terms, "and")
    mode = "AND"
    if not results and len(terms) > 1:
        mode = "OR"
        results = query.search(products, terms, "or")
    return {
        "query": raw_query,
        "mode": mode,
        "results": [result_item(p, fields, terms) for _score, p, fields in results],
    }


def build_products_response(products):
    return {
        "products": [
            {
                "model": model_text(p),
                "price": p["price"],
                "remark": p["remark"],
                "app": p["app"],
            }
            for p in products
        ]
    }


class WebHandler(BaseHTTPRequestHandler):
    def do_GET(self):
        parsed = urllib.parse.urlparse(self.path)
        if parsed.path == "/":
            self.serve_file(WEBUI_PATH, "text/html; charset=utf-8")
        elif parsed.path == "/api/search":
            qs = urllib.parse.parse_qs(parsed.query)
            raw_query = (qs.get("q") or [""])[0]
            self.serve_json(build_search_response(load_products(), raw_query))
        elif parsed.path == "/api/products":
            self.serve_json(build_products_response(load_products()))
        else:
            self.send_error(404)

    def serve_file(self, path, content_type):
        try:
            with open(path, "r", encoding="utf-8") as fh:
                data = fh.read().encode("utf-8")
        except OSError:
            self.send_error(500)
            return
        self.send_response(200)
        self.send_header("Content-Type", content_type)
        self.send_header("Content-Length", str(len(data)))
        self.end_headers()
        self.wfile.write(data)

    def serve_json(self, obj):
        data = json.dumps(obj, ensure_ascii=False).encode("utf-8")
        self.send_response(200)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(data)))
        self.end_headers()
        self.wfile.write(data)

    def log_message(self, fmt, *args):
        pass  # 终端保持安静，避免查询日志刷屏


def make_server(addr):
    return ThreadingHTTPServer(addr, WebHandler)


def main():
    query.configure_console()
    ap = argparse.ArgumentParser(prog="webui.py", description="DLD 产品查询器 WebUI")
    ap.add_argument("--host", default="127.0.0.1", help="监听地址（默认 127.0.0.1）")
    ap.add_argument("--port", type=int, default=8000, help="监听端口（默认 8000）")
    ap.add_argument("--open", action="store_true", help="启动后自动打开浏览器")
    args = ap.parse_args()

    load_products()
    server = make_server((args.host, args.port))
    url = f"http://{args.host}:{server.server_address[1]}/"
    print(f"DLD 产品查询器已启动：{url}（Ctrl+C 停止）")
    if args.open:
        threading.Timer(0.5, webbrowser.open, args=(url,)).start()
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        pass
    finally:
        server.server_close()


if __name__ == "__main__":
    main()
