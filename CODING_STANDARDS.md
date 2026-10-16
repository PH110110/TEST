# Coding Standards

These standards apply during code review and implementation.

## Single source of truth

- Matching logic lives in `query.py`. Other modules import and reuse `query.search`, `query.load_products`, `query.model_label`, and `query.context_line`; never reimplement them.
- Web layers stay thin: `webui.py` converts HTTP requests and JSON responses, and keeps pure logic in `build_search_response` so tests can call it without a server.
- Do not duplicate scoring or display formatting. Use the score returned by `query.search` and the label returned by `query.model_label` instead of recomputing them.

## Tests

- Test external behavior: API contracts, AND/OR fallback, parameter parsing, and JSON shape; avoid testing rendering details.
- Follow the existing `unittest` style in `test_query.py` and `test_webui.py`.
- New seams are expensive: prefer the highest existing seam (`query.search` / `query.load_products` / `build_search_response`) before adding another.

## Domain vocabulary

- Use the glossary terms from `CONTEXT.md` (`查询器`, `模糊拼配`, `型号`, `未税价格`, `备注`, ...). Avoid synonyms the glossary explicitly rejects, such as `商品` or `SKU`.

## Dependencies

- Prefer the Python standard library. Add third-party dependencies only when a spec requires them and the standard library cannot cover the need.
