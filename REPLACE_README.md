# V1.1 安全更新说明

这次是完整项目代码包，但 **不要再整体删除旧项目后替换**。

你的本机运行数据包括：

```text
data/processed/
data/knowledge/
data/milvus/
.env
.git/
```

这些不应该由源码包覆盖。

## 推荐更新方式

解压本包后，在解压目录执行：

```bash
bash SAFE_UPDATE_EXISTING_PROJECT.sh "/Users/guojiadong/.../medical-rag"
```

脚本会更新：

```text
apps/
src/
scripts/
doc/
tests/
deployment/
migrations/
以及根目录代码和配置模板
```

脚本不会删除或覆盖：

```text
data/
.env
.git/
```

## 更新后

```bash
cd "/你的/medical-rag"
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

## V1.1 重点验收

1. AI 健康助手发送问题后立即出现“正在分析问题”的对话气泡；
2. 回答中的常见 Markdown 排版不再以原始符号直接显示；
3. 引用来源优先展示真正用于答案的证据，其余证据折叠；
4. 管理员上传新 PDF 后状态自动经过：解析 → 分块 → 向量化 → 已索引；
5. 新文档完成后，无需手工执行脚本即可参与后续问答。
