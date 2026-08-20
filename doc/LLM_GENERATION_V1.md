# LLM Generation V1

## 1. 本阶段目标

本阶段第一次把已经验证过的检索链真正闭环到生成层：

```text
Query
  -> Dense(BGE-M3) + BM25
  -> RRF
  -> Cross-Encoder Reranker
  -> Context Builder
  -> Grounded Prompt
  -> OpenAI-compatible Chat LLM
  -> Citation Validation
  -> Answer + Trace
```

V1 的重点不是追求“回答多聪明”，而是确保模型只能看到我们构建出的证据，并且回答结果可追踪、可审计。

## 2. 为什么先做 OpenAI-compatible 接口

生成层被封装成标准 Chat Completions 风格 HTTP 接口，核心代码不绑定单一厂商。后续可以把相同 generation layer 指向：

- 托管的 OpenAI-compatible 模型服务；
- 内网 OpenAI-compatible gateway；
- 后续部署的本地 vLLM OpenAI-compatible server。

因此“RAG 业务逻辑”和“具体 LLM 服务”被解耦。

## 3. 配置

推荐把配置放进环境变量，不把密钥写进源码：

```bash
export MEDICAL_RAG_LLM_BASE_URL="<your-openai-compatible-base-url>/v1"
export MEDICAL_RAG_LLM_MODEL="<your-model-name>"
export MEDICAL_RAG_LLM_API_KEY="<your-api-key>"
```

本地无鉴权服务可以不设置 API key。

## 4. 运行

```bash
python scripts/generate_rag_answer.py \
  data/processed/hypertension_2024/chunks.json \
  --query "2级高血压的收缩压和舒张压范围是多少？" \
  --context-top-k 5 \
  --max-context-chars 6000
```

也可以通过参数覆盖：

```bash
python scripts/generate_rag_answer.py \
  data/processed/hypertension_2024/chunks.json \
  --query "2级高血压的收缩压和舒张压范围是多少？" \
  --llm-base-url "<base-url>/v1" \
  --llm-model "<model-name>"
```

## 5. 生成后的三个产物

### `rag_generation_v1.json`
完整结构化运行结果，包括 Context、Prompt、Answer、Citation Validation、Usage。不会保存 API key。

### `rag_answer_v1.md`
人类可读的最终问题、回答和来源摘要。

### `rag_generation_trace_v1.md`
调试用端到端 Trace：System Prompt、User Prompt、模型回答、引用状态、Token Usage。

## 6. Citation Validation V1

V1 可以检测两类最基础的引用错误：

1. **unknown citation**：模型输出 `[S9]`，但上下文只有 `[S1]~[S5]`；
2. **missing citation**：有检索证据，但模型完全没有输出任何 `[Sx]`。

如果没有任何可用检索证据，系统不会调用 LLM，而是直接返回：

```text
现有检索证据不足以回答该问题。
```

这是一个重要的成本与安全控制。

## 7. V1 还不能证明什么

`citation_valid = true` 只说明：

> 模型引用的 `[Sx]` 确实存在。

它暂时不能证明：

> 回答中的每个医学 claim 都真的被它引用的 `[Sx]` 支持。

下一阶段的评估会进入 Claim-to-Evidence Grounding / Faithfulness，而不是把“编号存在”误当成“事实一定正确”。

## 8. 为什么 temperature 默认 0

医疗知识问答的第一目标是稳定、可重复和忠实于证据。V1 因此默认 `temperature=0.0`，降低不必要的随机表达，为后续评价提供稳定基线。

## 9. 面试知识点

这一阶段直接命中：

- RAG 如何减少幻觉？
- 如何做引用和来源追踪？
- Context 与 Prompt 如何组织？
- LLM API 如何与业务逻辑解耦？
- 什么是 OpenAI-compatible API？
- 为什么医疗问答倾向低 temperature？
- 检索为空时为什么应该 abstain？
- 如何记录 Token Usage / Trace 做可观测性？
- Citation correctness 和 Faithfulness 有什么区别？
