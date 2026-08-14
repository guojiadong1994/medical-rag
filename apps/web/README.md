# 智护医疗 Web V1

本目录是 `medical-rag` 项目的前端 V1，继续采用 Vue 3 + TypeScript + Vite + Vue Router + Pinia + Element Plus。

## 当前产品结构

统一登录入口根据账号身份进入不同服务空间：

- 个人用户：
  - 首页
  - 我的健康
  - 医疗记录
  - AI 健康助手
  - 设置
- 管理员：
  - 医疗知识库管理

个人医疗数据在界面中统一体现为来自已关联医疗机构的数据，不提供个人上传医疗资料入口。

## 登录账号

页面已经自动预填账号与密码，可直接点击登录。

### 个人用户

- 账号：`user001`
- 密码：`123456`

### 管理员

- 账号：`admin`
- 密码：`admin123`

## 启动

```bash
npm install
npm run dev
```

浏览器访问：

```text
http://127.0.0.1:5173
```

## 构建

```bash
npm run build
```

## 后续接后端

当前前端已完成角色路由、页面结构与交互闭环。正式接入 FastAPI 后，建议依次替换：

1. 登录会话与角色信息
2. `/api/v1/me/profile`
3. `/api/v1/me/records`
4. `/api/v1/me/indicators`
5. `/api/v1/me/assistant/chat`
6. `/api/v1/admin/knowledge/documents`

现有 Vite 配置继续保留 `/api` 到 `http://127.0.0.1:8000` 的代理。
