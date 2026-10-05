# 拾光 · 杭电校园失物招领

一个本地优先的校园失物招领 Web 应用。访客可搜索已审核信息；注册用户可发布寻物/拾获信息、提交私密线索或认领并举报；管理员可审核内容、处理举报。当前使用本地账号，学号不经学校核验；暂不包含站内聊天、图片上传、消息推送或线上部署。

## 技术栈

- 前端：Vue 3、TypeScript、Vite
- API：FastAPI、SQLite
- 会话：HttpOnly Cookie；密码使用 PBKDF2-SHA256 哈希

## 本地运行

需要 Python 3.11+、Node.js 20+ 和 npm。

以下命令假设终端当前位于 `QOKIK/` 项目目录；若从整个仓库根目录开始，请先执行 `cd QOKIK`。

### 1. 启动 API

PowerShell：

```powershell
cd backend
python -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install -r requirements.txt
$env:HDUHELP_DB = "./data/hduhelp.sqlite3"
$env:HDUHELP_ADMIN_USERNAME = "moderator"
$env:HDUHELP_ADMIN_PASSWORD = "请换成至少 10 位的本地密码"
python -m uvicorn app.main:app --reload --host 127.0.0.1 --port 8000
```

数据库和管理员账号在 API 首次启动时初始化。管理员凭据通过进程环境变量传入；不要把真实密码提交到 Git。改密码时设置新密码不会自动覆盖已有管理员账号，请在数据库恢复或管理流程中处理。

### 2. 启动前端

另开终端：

```powershell
cd frontend
npm install
npm run dev
```

打开终端输出的本地地址（默认 `http://127.0.0.1:5173`）。Vite 会把 `/api` 请求转发到本机 FastAPI。OpenAPI 文档位于 `http://127.0.0.1:8000/docs`。

不要直接双击 `frontend/index.html` 打开；浏览器会以 `file://` 方式加载，无法运行 Vue 模块。请先启动上述 API 和前端服务，再访问 `http://127.0.0.1:5173`。

## 验证

```powershell
cd backend
python -m pytest -q
cd ..\frontend
npm run build
```

API 测试使用独立临时 SQLite 数据库。覆盖新内容审核、已通过版本修改、隐私边界、请求处理与检索权限。

完整浏览器流程脚本位于 `frontend/e2e/`。首次需安装 Python Playwright 和 Chromium：

```powershell
python -m pip install playwright
python -m playwright install chromium
```

启动 API（管理员环境变量和测试库只用于此演示）：

```powershell
cd frontend
$env:HDUHELP_DB = Join-Path $env:TEMP ("hduhelp-e2e-" + [guid]::NewGuid() + ".sqlite3")
$env:HDUHELP_ADMIN_USERNAME = "moderator"
$env:HDUHELP_ADMIN_PASSWORD = "e2e-moderator-password"
python e2e/serve_api.py
```

另开两个终端，在 `QOKIK/frontend` 目录分别运行：

```powershell
npm run dev -- --config e2e/vite.config.ts
```

```powershell
python e2e/journey.py
```

## 主要流程

1. 访客浏览公开信息，按失物/拾获、处理状态、地点或关键词检索。
2. 用户注册并提交内容；管理员通过审核后公开。修改已通过内容时保留旧版本，审批后再替换。
3. 失主可对拾获公告提交认领；知情者可对寻物启事发送线索。解释和联系方式仅对请求双方可见。
4. 发布者接受申请后，关联内容进入已找回/已归还状态，其他待处理申请关闭。
5. 用户可举报公开内容或自己参与的私密请求。管理员只有在请求参与者举报后，才会在该举报记录中看到私密请求详情。
6. 管理员账号必须通过环境变量预置；普通用户无法提升权限。

## API 概览

- `/api/auth/*`：注册、登录、退出、当前账号
- `/api/posts`：公开检索、查看、发布和更新
- `/api/my/posts`、`/api/my/requests`：个人内容与申请
- `/api/posts/{id}/requests`、`/api/requests/{id}/*`：私密申请处理
- `/api/admin/reviews`、`/api/admin/reports`：审核和举报工作台
- `/api/health`：本地健康检查

管理区不会提供用户自助赋予管理员身份的接口。部署、学校统一认证接入、ICP备案和生产运维均不在当前版本范围内。
