# Medical RAG V1.0 成品冲刺版 —— 完整替换说明

这是一份直接替换包，基于你已经跑通的 Evaluation V3.1 版本继续整合。

## 1. 替换哪些内容

请把压缩包中的以下内容复制到项目根目录并覆盖同名内容：

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

## 2. 不要删除或覆盖这些目录/文件

```text
data/
apps/
deployment/
migrations/
.git/
.env
```

尤其不要删除 `data/`，因为你已经生成的 `chunks.json`、`embeddings.npy`、Milvus 数据库和评测结果都在里面。

`.env.example` 只是配置模板；你自己的 `.env` 不要被覆盖。

`apps/` 也不要删除，这样仓库里现有的 Vue 前端仍然保留。Vue 是网页前端开发框架。

## 3. 安装

```bash
pip install -e ".[product,dev]"
```

`product` 是本项目定义的完整成品依赖集合，包含：

- BGE-M3 所需的句向量模型库；
- 重排序模型依赖；
- Milvus 本地向量数据库依赖。

## 4. 配置

如果当前 `.env` 已经能够调用 qwen3.7-max，则保留你现有的大模型配置即可。

至少应存在：

```text
MEDICAL_RAG_LLM_BASE_URL
MEDICAL_RAG_LLM_MODEL
MEDICAL_RAG_LLM_API_KEY
```

默认正式向量检索后端：

```text
RAG_DENSE_BACKEND=milvus
```

如果 Milvus 暂时有问题，可以临时：

```bash
export RAG_DENSE_BACKEND=local
```

`local` 表示使用本地 NumPy 精确向量检索；NumPy 是 Python 的数值计算库。

## 5. 先检查

```bash
pytest -q
```

本包制作时结果：

```text
59 passed
```

然后：

```bash
python scripts/preflight_v1.py
```

它只检查配置和运行文件，不调用大模型。

## 6. 启动成品

```bash
python run.py
```

浏览器打开：

```text
http://127.0.0.1:8000/rag-demo
```

本地演示默认账号：

```text
账号：doctor
密码：123456
```

这是开发演示账号，不是生产安全方案。

## 7. 命令行也可以直接问

```bash
python scripts/ask_v1.py "2级高血压的收缩压和舒张压范围是多少？"
```

## 8. 这一版一次性完成的事情

```text
Safety Guardrail V1（安全防护规则）
+ 统一 MedicalRAGPipeline（完整问答处理流程）
+ Milvus 正式接入主链
+ FastAPI 真实问答接口
+ 来源和页码输出
+ 运行耗时与 Token 诊断
+ 零构建演示网页
+ 一键启动脚本
+ Docker 独立启动文件
```

## 9. 下一步只需要做一次真实回归

成品启动成功后，再用原来的：

```text
14 道正常问题
+ 9 道安全挑战问题
```

跑一次最终回归即可。

Safety Guardrail V1 的目标是修复之前 9 道挑战题里唯一真实失败的“自行停药”问题，同时保持原来正常问题不退化。
