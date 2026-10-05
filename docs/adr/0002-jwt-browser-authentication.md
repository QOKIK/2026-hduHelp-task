---
status: accepted
date: 2026-10-05
---

# 浏览器认证采用短效 Access JWT 和轮换 Refresh JWT

保留本地用户名/密码登录，密码使用 Argon2id，参数至少达到 OWASP 的建议下限：19 MiB 内存、2 次迭代、并行度 1（[OWASP Password Storage Cheat Sheet](https://cheatsheetseries.owasp.org/cheatsheets/Password_Storage_Cheat_Sheet.html)）。Vue 将 15 分钟有效的 Access JWT 保存在内存中，通过 `Authorization: Bearer` 发送；7 天有效的 Refresh JWT 放在 HttpOnly Cookie 中，每次使用后轮换。PostgreSQL 记录令牌标识和所属令牌族；重放已消费令牌时撤销该令牌族，登出时撤销当前设备的令牌族。

API 必须校验令牌类型、签名算法、签发者、受众、有效期和用途；签名密钥通过运行时密钥配置提供。Refresh Cookie 使用适当的 `SameSite` / `Secure` 属性，刷新操作校验请求来源并采取 CSRF 防护。由于 Refresh JWT 可撤销，本方案并非完全无状态；未来若前后端跨站部署，可能需要同站自定义域名或调整刷新令牌传输方式。轮换设计参考了 [RFC 9700](https://www.rfc-editor.org/info/rfc9700/) 对公开客户端的安全方向；本应用本身不是 OAuth 部署。
