# 校园失物招领系统需求规格

## Problem Statement

校园内失物信息分散，失主和拾获者难以通过统一入口查找、发布和跟进物品信息。未经管理的公开联系方式、虚假认领和不合适内容也会带来隐私与治理问题。项目需要提供一个可在本地运行、能支持校园用户与管理员完成失物招领流程的 Web 系统。

## Solution

构建响应式 Web 前端、API 服务和管理后台。访客可浏览和搜索已审核的失物报告与拾获公告；登录用户可发布和管理自己的内容、提交私密线索或认领请求并举报内容；管理员可审核新内容和修改、处理举报并下架违规内容。

本规格的主要验收边界：

1. 浏览器端走通主要用户流程，覆盖注册/登录、发布与审核、检索、线索/认领、举报及管理后台。
2. 在 API 边界验证访问权限、隐私隔离和关键状态转换，并通过隔离的测试数据库观察持久化后的外部行为。

## Go 后端重构（代码已实现，集成验收待运行）

Go/Gin API、PostgreSQL 迁移、Compose 配置和 Vue JWT 认证适配已落入工作树。现有 SQLite 数据不迁移，PostgreSQL 从空库初始化，普通用户需要重新注册。业务能力、权限和隐私边界沿用本规格。

本地使用 Docker Compose 启动 Go API 和 PostgreSQL；Vue 开发服务器继续在宿主机通过 `npm run dev` 启动。当前阶段只要求本地可运行，不包含公网部署。

### 迁移交付顺序

1. 建立 Go/Gin 服务、运行配置、PostgreSQL 版本化迁移和 Docker Compose；健康检查须能确认 API 与数据库可用。
2. 按现有业务规格重建账户、认证、失物/拾获、审核、线索/认领、举报和管理功能。
3. 更新 Vue API 客户端与界面认证流程，Access JWT 内存态须在页面刷新后通过 Refresh JWT 恢复。
4. 使用隔离 PostgreSQL 数据库运行 API 集成测试，并通过浏览器走通验收流程。
5. 在 Compose/PostgreSQL 与浏览器验收通过后，移除旧 FastAPI 后端及其专属依赖；迁移期间不让两个后端共同写同一数据。当前 Docker Engine 未运行，旧后端暂时保留，避免在验收前丢失回退路径。

### 迁移完成条件

- Docker Compose 能启动 Go API 和 PostgreSQL；按 README 启动 Vue 后，访客和登录用户主要流程可在浏览器完成。
- API 测试提供隔离 PostgreSQL schema 验收入口，目前覆盖注册、JWT 刷新令牌重放撤销、权限和审核公开流程；其余隐私、生命周期、请求与举报场景仍需扩充并实际运行。
- 浏览器 E2E 脚本已保留；需在 Docker Engine 可用后接入新 API 并实际走通访客搜索、注册登录、发布审核、认领与线索、举报及管理员处理。
- README 提供从空 PostgreSQL 开始的本地运行说明；真实密钥不写入仓库。

## User Stories

### 账户与身份

1. As a campus visitor, I want to browse approved lost reports and found notices without signing in, so that I can quickly see whether an item has been reported.
2. As a new user, I want to register with a username, password, nickname, and student number, so that I can use the platform and be associated with a campus identity.
3. As a user, I want my student number to be unique and private from other users, so that duplicate accounts can be discouraged without exposing my identity publicly.
4. As a user, I want to sign in with my username and local password and explicitly sign out, so that I can safely access my own content and requests.
5. As a user, I want the system to make clear that my student number is not verified by the school yet, so that I do not mistake local registration for campus SSO.

### 失物与拾获内容

6. As a user who lost an item, I want to create a lost report with a required item name and description and optional category, location, and event time, so that others can identify the item even when some details are unknown.
7. As a user who found an item, I want to create a found notice with the same shared item details, so that the owner can discover and claim it.
8. As a poster, I want every newly submitted post to enter moderation and remain hidden from public search until approved, so that unreviewed content is not presented as trusted information.
9. As a poster, I want to edit my own post, so that I can correct or update its public information.
10. As a poster, I want the currently approved version to remain visible while an edit is reviewed, so that pending changes do not replace trusted information prematurely.
11. As a poster, I want only one pending edit at a time and for a newer edit to replace the previous pending edit, so that moderation reviews the latest proposed version.
12. As a poster, I want to see the reason when a post or edit is rejected and be able to correct and resubmit it, so that I can address the review outcome.
13. As a poster, I want to delete a post with no related requests or reports, so that I can remove content that has no handling history.
14. As a poster, I want a post with related requests or reports to be withdrawn from public view while its history is retained, so that prior handling and moderation records remain understandable.
15. As a poster, I want to change the lifecycle status of my own post without another moderation cycle, so that I can reflect a recovery, return, or closure promptly.
16. As a poster, I want closing a post to close its outstanding claim or lead requests, so that users are not invited to act on an inactive case.

### 浏览与检索

17. As a visitor, I want to filter public posts by lost/found type, lifecycle status, and location, so that I can narrow results to relevant campus information.
18. As a visitor, I want a keyword to match item names and descriptions, so that I can find posts even when I do not know the exact title.
19. As a visitor, I want approved public posts sorted newest first and paginated, so that I can scan recent information without loading every result at once.

### 线索与认领

20. As a logged-in user who may know something about a lost item, I want to send a private lead to the lost-report author with an explanation and contact method, so that I can help without publishing contact details.
21. As a logged-in user who believes a found item is mine, I want to submit a private claim request with an explanation and contact method, so that I can establish a connection with the finder.
22. As a requester, I want to see and withdraw my own pending request, so that I can correct a mistake or stop pursuing an item.
23. As a post author, I want to review, accept, or reject requests associated with my post, so that I can coordinate with relevant people.
24. As a post author, I want request details and contact methods to be visible only to the requester and me, so that private coordination is not exposed to other users.
25. As a post author, I want accepting one request to resolve the related post and close its other outstanding requests, so that the case has one clear outcome.
26. As a user, I want to see request and moderation outcomes in the relevant post or request views, so that I can follow progress without email, SMS, or push notifications.
27. As a user, I want offline contact after acceptance and no in-app chat in the first version, so that the initial workflow stays focused on matching and return coordination.

### 管理与内容治理

28. As an administrator, I want to access a dedicated management area with a preconfigured administrator account, so that moderation is available without letting ordinary users grant themselves administrator privileges.
29. As an administrator, I want to approve or reject new posts and material edits with a reason, so that public content follows platform rules and users understand decisions.
30. As an administrator, I want to take down an already approved post with a reason, so that harmful or invalid content can be removed from public view.
31. As a logged-in user, I want to report a public post or a private claim/lead request, so that I can flag abuse for review.
32. As an administrator, I want to dismiss a report or remove the reported post/request with a reason, so that reports receive a documented outcome.
33. As an administrator, I want private claim/lead content to be revealed only when a participant reports it, so that routine moderation does not expose private coordination.
34. As a platform participant, I want reports, review reasons, and retained post/request history to remain associated with their target, so that moderation actions are auditable.
35. As a platform participant, I want account banning to remain out of the first version, so that the admin scope stays limited to content and request handling.

## Implementation Decisions

- Build a responsive full-stack Web system with a user-facing area and administrator area.
- Frontend remains Vue 3, TypeScript, and Vite. The approved backend target is Go with Gin and PostgreSQL; use `pgx` for PostgreSQL access and versioned SQL migrations. API routes and payloads may be redesigned, with corresponding frontend updates.
- Do not migrate the existing SQLite database. Initialize a fresh PostgreSQL schema; existing users and business records will not carry over, and users will register again.
- Authentication remains local username/password. Hash new passwords with Argon2id using at least OWASP's minimum configuration (19 MiB memory, 2 iterations, parallelism 1). A required, unique student number is stored for the planned campus SSO identifier, but there is no SSO integration or school-side verification in this version.
- Use a 15-minute access JWT held in frontend memory and sent as `Authorization: Bearer`. Use a 7-day refresh JWT in an HttpOnly cookie. Rotate refresh JWTs on use, track their token identifiers and families in PostgreSQL, revoke a family if a consumed token is reused, and revoke the current device's family on logout. Apply cookie `SameSite` and `Secure` settings appropriate to local HTTP and future HTTPS deployments, and validate request origin on refresh operations.
- Provision the initial administrator from credentials in an untracked `.env` file consumed by Docker Compose. Initialize the administrator when the new database is first created; regular users cannot grant themselves the administrator role.
- Use Docker Compose for the Go API and PostgreSQL. Run the Vue development server on the host. Public deployment and production operations remain deferred.
- Users have public-facing lost reports and found notices. Shared fields are item name, description, optional category, optional location, and optional event time. Location/time may be approximate or unknown.
- Public browsing/search returns approved and currently visible content only. Keyword search covers item name and description; filters cover type, status, and location; order is newest approved/published first with limit/offset pagination.
- Lifecycle and moderation are separate concerns. Lost report lifecycle labels are `寻找中 → 已找回 → 已结束`; found notice labels are `待认领 → 已归还 → 已结束`. New posts and material edits require review; lifecycle changes do not.
- An approved post remains public while its proposed edit is pending. Approval replaces the public version; rejection retains the approved version and supplies a reason. A newer edit replaces the one pending edit.
- Claim requests apply to found notices; leads apply to lost reports. Each has a private explanation and required contact method and uses `待处理 / 已接受 / 已拒绝 / 已撤回`. The post author sees the request; the administrator sees private request content only when a participant reports it. No in-app chat is included.
- Accepting a claim resolves the found notice as `已归还`; accepting a lead resolves the lost report as `已找回`. Other open requests on that post are closed. The author may also directly set the corresponding resolved or ended status without a request.
- A request or moderation result is shown in the corresponding post/request view. No email, SMS, or push notifications are sent.
- A logged-in user can report public posts and private requests. Administrators may dismiss the report or remove its target with a reason. The first version does not ban accounts.
- A post may be permanently deleted only when it has no related request or report. Otherwise it is removed from public view and its handling history remains.
- Administrators are provisioned in advance; regular users cannot assign themselves that role. The bootstrap mechanism is an implementation detail and must not expose a public self-service role escalation path.
- Work belongs in the `QOKIK/` folder of the fork, on the `dev` working branch; pushes go to the fork's `dev`. The assignment submission is a pull request to the official upstream repository following its README and CI checks.
- The application must first be runnable locally. No demo video is required.
- Alibaba Cloud is the selected future deployment target. Public deployment is not required by the assignment and is not part of the current implementation phase. A possible later arrangement is GitHub Pages for static frontend hosting and Alibaba Cloud for API/data services; production database topology and public-domain/ICP steps remain deployment-phase decisions.
- The user-facing product and project documentation should be in Chinese unless the assignment's submission format requires otherwise.

## Testing Decisions

- Tests should assert externally visible behavior and stored outcomes through application interfaces, not private functions or internal file structure.
- Browser-level end-to-end coverage is the highest-level seam for the principal paths: visitor search; account registration/login; post submission and moderation; approved post search; claim/lead handling; report submission and administrator action.
- API integration coverage uses an isolated PostgreSQL database and exercises authentication/authorization, privacy boundaries, lifecycle transitions, moderation revisions, request resolution, report handling, and deletion/retention rules.
- Authentication tests cover access JWT validation and expiry, refresh JWT rotation and replay revocation, logout, role-based authorization, and frontend refresh after a page reload.
- Verify that public responses never expose student numbers or private request/contact fields, including to another logged-in user; verify that administrators cannot read private request content absent a participant report.
- Verify pagination, filters, keyword behavior, newest-first order, moderation visibility, and old-approved-version visibility while a revision is pending.
- Keep the test seam at externally visible API and browser behavior; adapt the existing Python MVP coverage rather than carrying over its framework-specific internals.
- The previous Python implementation's behavior checks remain under `QOKIK/backend/tests/` and `QOKIK/frontend/e2e/` during transition. Port and run the full behavior-level coverage against the Go API and isolated PostgreSQL test database before removing the legacy backend.

## Out of Scope

- School SSO connection, student-number verification, and any claim that registration is institutionally verified.
- Image upload and AI matching.
- In-app chat, email/SMS/push notifications, and account banning.
- Public deployment, ICP filing, and production operations in this implementation phase.
- Production database topology, automated backup/restore policy, and media/object-storage integration.
- Demo video production.

## Further Notes

- The official assignment repository README requires the submitter's GitHub-username-named directory in the fork and a pull request for submission. Preserve that structure in the eventual implementation.
- The assignment does not require a publicly deployed website or ICP filing. If public access on a mainland-hosted service is later chosen, handle provider and filing requirements before opening public service.
- The target implementation in `QOKIK/` is Vue 3 with a Go/Gin API and PostgreSQL. Docker-backed integration and browser acceptance are still pending local Docker Engine availability; public deployment and production operations remain out of scope.
