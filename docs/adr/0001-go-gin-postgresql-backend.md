---
status: accepted
date: 2026-10-05
---

# 后端改用 Go、Gin 和 PostgreSQL

当前 MVP 使用 FastAPI 和 SQLite；已确认的目标是 Go/Gin API 和 PostgreSQL，同时保留 Vue 3/TypeScript 前端及现有业务流程。API 契约允许重设计并同步修改前端，但不迁移旧 SQLite 数据；本地通过 Docker Compose 启动 API 和 PostgreSQL，Vite 在宿主机运行，Go 服务使用 `pgx` 和版本化 SQL 迁移。

本次从空数据库重建，因此普通用户需要重新注册，初始管理员从不提交到 Git 的 `.env` 配置中初始化。公网部署不属于当前实现阶段。
