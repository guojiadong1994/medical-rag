# Medical RAG V1.0.1 启动修复说明

## 现象

`python scripts/preflight_v1.py` 显示数据、Milvus（向量数据库）和大模型配置均正常，但 `python run.py` 在导入阶段报：

```text
ImportError: cannot import name 'OpenAICompatibleChatClient' from partially initialized module ...
most likely due to a circular import
```

## 根因

这是 Circular Import（循环导入）：模块 A 导入模块 B，同时 B 的导入链又回头导入尚未完成初始化的 A。

实际链路是：

```text
generation.client
→ generation.models
→ rag.context
→ Python 先执行 rag/__init__.py
→ rag/__init__.py 以前会立即导入 rag.pipeline
→ rag.pipeline 又导入 generation.client
→ generation.client 尚未初始化完成
→ ImportError
```

问题不是 Milvus、MPS（苹果 GPU 加速后端）、模型权重或 API Key。

## V1.0.1 修复

1. `rag/__init__.py` 不再启动时立即导入 `rag.pipeline`。
2. Pipeline（完整问答处理流程）相关类改成 Lazy Import（延迟导入）：只有代码真正访问 `MedicalRAGPipeline` 等对象时才加载。
3. 保留 `from medical_rag.rag import MedicalRAGPipeline` 的兼容性，不要求其他代码大面积改 import。
4. `preflight_v1.py` 增加 API Import Smoke Test（接口导入冒烟测试），以后启动前即可发现类似导入错误。
5. 新增循环导入回归测试，避免这个问题再次出现。

## 修复后验证顺序

```bash
pytest -q
python scripts/preflight_v1.py
python run.py
```

新的启动前检查中应看到：

```json
"api_importable": true,
"api_import_error": null
```

然后访问：

```text
http://127.0.0.1:8000/rag-demo
```
