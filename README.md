# DLD 产品查询器

对 DLD Smart Watch 的「产品 2026-1.xlsx」报价表做关键词模糊拼配（关键词包含匹配 + 命中打分），快速定位产品条目。

## 运行环境

- Python 3.8+
- `openpyxl`（首次读取 xlsx 生成缓存时需要）

```powershell
pip install -r requirements.txt
```

## 用法

```powershell
python query.py 曲面
python query.py 曲面 gps          # 多词 AND，空结果自动降级 OR
python query.py -n 20 5691        # 显示条数上限
python query.py --list            # 列出全部产品
python query.py 产品2026-2.xlsx 曲面  # 显式指定数据源
```

默认取脚本同目录下最新的「产品*.xlsx」。首次运行会解析 xlsx 并生成 `products.cache.json`（已 gitignore），之后直接读缓存；xlsx 修改时间变化时自动重建。

## 测试

```powershell
python -m unittest discover -v
```

## WebUI

双击 `启动WebUI.bat` 会自动启动本地 Web 服务并打开浏览器；也可以在命令行运行：

```powershell
python webui.py --open
python webui.py --port 8080
```
