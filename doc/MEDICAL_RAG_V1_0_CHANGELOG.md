# Medical RAG V1.0 变更记录

## 本版新增

- 将实验脚本能力整合为统一 `MedicalRAGPipeline`（医疗 RAG 完整处理流程）。
- Milvus（向量数据库）正式作为默认向量检索后端，同时保留本地 NumPy 精确检索回退。
- FastAPI（Python 网页接口框架）的 `/api/v1/rag/ask` 从 503 占位接口升级为真实问答接口。
- 新增 `/api/v1/me/assistant/chat`，便于连接现有网页前端。
- 新增 `/rag-demo` 零构建演示页面。
- 新增运行状态、来源页码、引用使用情况、Token 数和分阶段耗时。
- 新增 Safety Guardrail V1（安全防护规则）：禁止用模型自身知识补充当前证据没有支持的药物后果、风险和因果关系。
- 明确证据不足的拒答不再强制要求无意义的 `[Sx]` 引用。
- 新增 `run.py`、`.env.example`、`scripts/preflight_v1.py` 和 `scripts/ask_v1.py`。
- 新增独立 Docker 成品启动文件，不覆盖仓库现有 Docker 配置。
- 项目版本更新为 `1.0.0`。

## 保留

- 之前的 PDF 解析、清洗、表格解析、Chunk（文本切块）、BGE-M3、BM25、RRF、重排序、Milvus、上下文构建、大模型生成、引用、Grounding（证据绑定）和 V1/V2/V3/V3.1 评测代码与文档均保留。

## 自动测试

制作时：

```text
59 passed
```
