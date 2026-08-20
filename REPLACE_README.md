# 完整项目恢复说明

这不是只包含后端或临时演示页面的包。

本包包含：

- 原有 `apps/web/` 智护医疗完整前端；
- 当前最新 `src/` 医疗 RAG 后端；
- `scripts/`、`doc/`、`tests/`；
- `deployment/`、`migrations/`；
- 根目录配置与启动文件。

## 最安全的恢复方法

不要把旧项目整个删除，因为你的本地 `.env`、`data/processed/`、Milvus 数据库和 `.git/` 不在源码包里。

### 方法 A：推荐

把这个完整包解压到任意临时目录，然后在解压后的项目根目录运行：

```bash
bash SAFE_RESTORE_TO_EXISTING_PROJECT.sh "/你的/medical-rag/原项目路径"
```

它会：

- 恢复/覆盖 `apps/`、`src/`、`scripts/`、`doc/`、`tests/`、`deployment/`、`migrations/`；
- 恢复根目录源码配置；
- **不会删除或覆盖**目标项目中的 `.git/`、`.env` 和已有 `data/`。

### 方法 B：新建完整项目副本

解压本包后，把旧项目中的：

```text
.env
.git/
data/
```

复制进新目录，再运行安装与启动命令。

## 验证

```bash
pip install -e ".[product,dev]"
pytest -q
python scripts/preflight_v1.py
python run.py
```

另开终端：

```bash
cd apps/web
npm install
npm run dev
```

访问：

```text
http://127.0.0.1:5173
```
