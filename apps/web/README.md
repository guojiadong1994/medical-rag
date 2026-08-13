# 医疗保障大模型平台 Web

医生端前端采用 Vue 3、TypeScript、Vite、Vue Router、Pinia 与 Element Plus。

## 启动

```bash
npm install
npm run dev
```

默认访问：`http://127.0.0.1:5173`

前端通过 `/api/v1` 调用 FastAPI 服务，Vite 开发服务器已将 `/api` 代理到 `http://127.0.0.1:8000`。

## 页面

- 登录
- 系统首页
- 患者管理
- 患者详情与医疗知识辅助问答
- 知识库管理
- 医学知识问答
- 系统设置
