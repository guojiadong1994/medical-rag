# Medical RAG V1.0.1 完整替换说明

这是 V1.0 成品冲刺版的启动修复完整包，修复 `python run.py` 的 Circular Import（循环导入）错误。

## 替换

请继续采用完整目录替换方式：

```text
src/
scripts/
doc/
tests/
pyproject.toml
README.md
run.py
.env.example
Dockerfile.rag-v1
docker-compose.rag-v1.yml
Makefile.v1
```

## 不要删除/覆盖自己的运行数据

保留：

```text
data/
.env
.git/
apps/
deployment/
migrations/
```

## 替换后验证

```bash
pip install -e ".[product,dev]"
pytest -q
python scripts/preflight_v1.py
python run.py
```

启动前检查应新增：

```text
api_importable: true
api_import_error: null
```

然后浏览器访问：

```text
http://127.0.0.1:8000/rag-demo
```
