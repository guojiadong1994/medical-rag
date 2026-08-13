# Doctor Web V0.1

JD 特定人群生理孪生与医疗保障大模型平台中的医生 PC Web 第一版。

## 当前页面

1. 医生登录页
2. 患者列表页
3. 患者详情页
4. 患者详情左侧：概览、时间线、用药、检查/报告占位
5. 患者详情右侧：医学知识库 RAG 问答界面
6. 回答中区分“患者依据”和“知识库依据”

当前为了先完成界面和流程，默认使用模拟患者数据与模拟 RAG 回答，不调用真实后端业务接口。

## 技术栈

- Vue 3
- TypeScript
- Vite
- Vue Router
- Pinia
- Element Plus

前端继续保留在仓库的 `apps/web/`，FastAPI 后端继续保留在 `src/medical_rag/`。二者位于同一 Git 仓库，但运行时通过 HTTP API 解耦，属于前后端分离的单仓库结构。

## 启动

```bash
cd apps/web
cp .env.example .env
npm install
npm run dev
```

浏览器打开：

```text
http://127.0.0.1:5173
```

演示账号：

```text
账号：doctor
密码：123456
```

## 模拟/真实接口切换

`.env`：

```bash
VITE_USE_MOCK=true
VITE_API_BASE_URL=/api/v1
```

完成 FastAPI 登录、患者和 RAG 接口后，把：

```bash
VITE_USE_MOCK=false
```

前端将按以下接口请求：

```text
POST /api/v1/auth/login
GET  /api/v1/patients
GET  /api/v1/patients/{patient_id}
POST /api/v1/rag/ask
```

Vite 开发服务器已经把 `/api` 代理到 `http://127.0.0.1:8000`。

## 第一版设计边界

- 患者数据目前为模拟数据，不声称来自真实医院。
- RAG 回答目前为结构占位，不声称来自真实医学指南。
- 下一阶段重点是后端模拟患者数据库与真实医学知识库 RAG。
