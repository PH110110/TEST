#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
DLD 产品快速查询器 —— 对报价表 xlsx 做关键词「模糊拼配」。

语义（见 CONTEXT.md「模糊拼配」）：关键词包含匹配 + 命中打分。
- 参与匹配字段：型号(权重2) + 功能特点说明/参数规格/标准颜色(权重1)
- 多关键词默认 AND（全部命中）；无结果显示时自动降级 OR（任一命中）并提示
- 排序：命中得分降序 → 型号字典序；默认显示前 8 条
- 忽略大小写（gps == GPS）；空行/残行自动跳过

用法：
  python query.py 曲面                # 单个关键词
  python query.py 曲面 gps            # 多词 AND，空结果自动降级 OR
  python query.py -n 20 5691          # 显示条数上限
  python query.py --list              # 列出全部产品
  python query.py 产品2026-2.xlsx 曲面 # 显式指定数据源文件
  python query.py --no-color ...      # 关闭高亮（NO_COLOR=1 同理）

数据源：默认取脚本同目录下最新的「产品*.xlsx」；也可用参数显式指定。
缓存：首次读取用 openpyxl 解析并生成 products.cache.json（匹配本身零第三方依赖）；
      xlsx 修改时间变化时自动重建缓存。
"""

import argparse
import glob
import json
import os
import sys

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
CACHE_PATH = os.path.join(SCRIPT_DIR, "products.cache.json")
SEARCH_COLUMNS = ("model", "features", "specs", "colors")  # 参与匹配（Q2b）
WEIGHTS = {"model": 2, "features": 1, "specs": 1, "colors": 1}  # 型号加权
DEFAULT_MAX = 8

_USE_COLOR = False


# ---------------- 控制台编码 ----------------

def configure_console():
    """Windows 控制台默认 GBK 打不出 ¥ 等字符，统一改用 UTF-8 输出。"""
    if os.name != "nt":
        return
    for stream in (sys.stdout, sys.stderr):
        try:
            stream.reconfigure(encoding="utf-8", errors="replace")
        except (AttributeError, ValueError):
            pass


# ---------------- ANSI 高亮 ----------------

def init_color(force_off=False):
    global _USE_COLOR
    if force_off or os.environ.get("NO_COLOR") or not sys.stdout.isatty():
        return
    if os.name == "nt":  # 启用 Windows 终端 VT 转义
        try:
            os.system("")
        except Exception:
            pass
    _USE_COLOR = True


def hl(text):
    return f"\033[1;33m{text}\033[0m" if _USE_COLOR else text


def dim(text):
    return f"\033[2m{text}\033[0m" if _USE_COLOR else text


# ---------------- 数据加载（xlsx → 缓存 JSON） ----------------

def normalize_cell(v):
    return "" if v is None else str(v).strip()


def read_xlsx(source):
    """用 openpyxl 解析报价表（只首次/失效时调用）。"""
    try:
        import openpyxl
    except ImportError:
        sys.exit("缺少 openpyxl（首次生成缓存需要）：pip install openpyxl")
    wb = openpyxl.load_workbook(source, read_only=True, data_only=True)
    ws = wb.active
    products = []
    for row in ws.iter_rows(min_row=3, values_only=True):
        # 列位：0序号 1型号 2产品图 3功能特点 4参数规格 5APP 6标准颜色 7未税价格 8备注
        model = normalize_cell(row[1]) if len(row) > 1 else ""
        price = row[7] if len(row) > 7 else None
        if not model and price is None:
            continue  # 空行 / 残行（如表尾仅序号23的行）自动跳过
        p = {
            "model": model,
            "features": normalize_cell(row[3]) if len(row) > 3 else "",
            "specs": normalize_cell(row[4]) if len(row) > 4 else "",
            "colors": normalize_cell(row[6]) if len(row) > 6 else "",
            "app": normalize_cell(row[5]) if len(row) > 5 else "",
            "price": int(price) if isinstance(price, (int, float)) else price,
            "remark": normalize_cell(row[8]) if len(row) > 8 else "",
        }
        p["_l"] = {k: p[k].lower() for k in SEARCH_COLUMNS}  # 预构建小写搜索文本
        products.append(p)
    wb.close()
    return products


def load_products(source):
    mtime = os.path.getmtime(source)
    try:
        with open(CACHE_PATH, "r", encoding="utf-8") as fh:
            cache = json.load(fh)
        if (cache.get("source") == source and cache.get("mtime") == mtime
                and cache.get("products")):
            return cache["products"], False
    except (OSError, ValueError):
        pass
    products = read_xlsx(source)
    tmp = CACHE_PATH + ".tmp"
    with open(tmp, "w", encoding="utf-8") as fh:
        json.dump({"source": source, "mtime": mtime, "products": products},
                  fh, ensure_ascii=False)
    os.replace(tmp, CACHE_PATH)
    print(dim(f"[缓存] 已从 {os.path.basename(source)} 重建 products.cache.json"
              f"（{len(products)} 条）"), file=sys.stderr)
    return products, True


def default_source():
    """取脚本同目录下最新的「产品*.xlsx」作为默认数据源。"""
    cands = glob.glob(os.path.join(SCRIPT_DIR, "产品*.xlsx"))
    if not cands:
        return None
    return max(cands, key=os.path.getmtime)


# ---------------- 匹配与打分 ----------------

def hit_fields(p, term):
    return [k for k in SEARCH_COLUMNS if term in p["_l"][k]]


def search(products, terms, mode):
    """mode: 'and' 全部命中 / 'or' 任一命中。返回 [(score, p, fields_map), ...]"""
    terms = [t.lower() for t in terms]
    results = []
    for p in products:
        fields = {t: hit_fields(p, t) for t in terms}
        if mode == "and" and not all(fields.values()):
            continue
        if mode == "or" and not any(fields.values()):
            continue
        score = sum(WEIGHTS[k] for t in terms for k in fields[t])
        results.append((score, p, fields))
    results.sort(key=lambda x: (-x[0], x[1]["model"]))
    return results


# ---------------- 展示 ----------------

def colorize(orig, terms):
    """把 terms 在 orig 中出现的片段高亮（假设 lower() 等长偏移，本数据成立）。"""
    if not _USE_COLOR:
        return orig
    low = orig.lower()
    spans = []
    for t in terms:
        start = 0
        while True:
            j = low.find(t, start)
            if j < 0:
                break
            spans.append((j, j + len(t)))
            start = j + len(t)
    spans.sort()
    merged = []  # 合并重叠区间
    for s, e in spans:
        if merged and s <= merged[-1][1]:
            merged[-1] = (merged[-1][0], max(merged[-1][1], e))
        else:
            merged.append((s, e))
    out, i = [], 0
    for s, e in merged:
        out.append(orig[i:s])
        out.append(hl(orig[s:e]))
        i = e
    out.append(orig[i:])
    return "".join(out)


def context_line(p, fields):
    """命中在型号之外的字段时，摘一行带命中的上下文展示。"""
    for t in fields:
        for f in fields[t]:
            if f == "model":
                continue
            txt, low = p[f], p["_l"][f]
            j = low.find(t)
            if j < 0:
                continue
            line_start = txt.rfind("\n", 0, j) + 1
            line_end = txt.find("\n", j)
            if line_end < 0:
                line_end = len(txt)
            line = txt[line_start:line_end].strip()
            if len(line) > 48:
                s = max(0, j - line_start - 20)
                line = ("…" if s > 0 else "") + line[s:s + 48]
                if s + 48 < len(line):
                    line = line[:48] + "…"
            return "↳ ({fld}) {text}".format(
                fld="功能" if f == "features" else ("参数" if f == "specs" else "颜色"),
                text=colorize(line, [t]))
    return ""


def render(p, fields, terms, prefix=None):
    model_text = " / ".join(x.strip() for x in p["model"].split("\n") if x.strip())
    parts = [colorize(model_text, terms)]
    if p["price"] is not None:
        parts.append(f"¥{p['price']}")
    remark = "·".join(x.strip() for x in p["remark"].split("\n") if x.strip())
    if remark:
        parts.append(dim(remark[:24] + ("…" if len(remark) > 24 else "")))
    line = "  ".join(parts)
    print(("  " + line) if prefix else line)
    ctx = context_line(p, fields)
    if ctx:
        print(dim("    " + ctx))


# ---------------- 主流程 ----------------

def main():
    configure_console()
    init_color()
    ap = argparse.ArgumentParser(
        prog="query.py",
        description="DLD 产品快速查询器：对报价表做关键词模糊拼配")
    ap.add_argument("keywords", nargs="*", help="空格分隔的关键词（首个 .xlsx 参数视为数据源）")
    ap.add_argument("-n", "--max", type=int, default=DEFAULT_MAX,
                    metavar="N", help=f"最多显示条数（默认 {DEFAULT_MAX}）")
    ap.add_argument("-l", "--list", action="store_true", help="列出全部产品")
    ap.add_argument("--no-color", action="store_true", help="关闭高亮")
    args = ap.parse_args()

    keywords = list(args.keywords)
    explicit = None
    for k in keywords:
        if k.lower().endswith(".xlsx") and os.path.isfile(k):
            explicit = k
    if explicit:
        keywords.remove(explicit)
    source = (
        os.path.abspath(explicit) if explicit
        else None
    )
    if not explicit:
        source = default_source()
        if source is None:
            sys.exit("当前目录没有「产品*.xlsx」，请用参数指定数据源（python query.py 路径/产品xxx.xlsx …）")

    products, _rebuilt = load_products(source)
    terms = [t.strip().lower() for t in keywords if t.strip()]

    if args.list:
        print(f"共 {len(products)} 个产品（{os.path.basename(source)}）：")
        for i, p in enumerate(products, 1):
            render(p, {}, terms, prefix=True)
        return

    if not terms:
        print("请输入关键词，例如：python query.py 曲面 gps")
        print("或 python query.py --list 查看全部产品。")
        return

    results = search(products, terms, "and")
    mode = "AND"
    if not results and len(terms) > 1:
        results = search(products, terms, "or")
        mode = "OR"
        print(dim("[提示] 没有同时包含全部关键词的条目，已放宽为任一命中。"))
    if not results:
        print("未命中任何产品。试试更短的关键词，或 --list 查看全部。")
        sys.exit(1)

    print(f"命中 {len(results)} 条（{mode}）: ")
    for _score, p, fields in results[:args.max]:
        render(p, fields, terms)
    if len(results) > args.max:
        print(dim(f"… 还有 {len(results) - args.max} 条，用 -n {len(results)} 看全部"))


if __name__ == "__main__":
    main()
