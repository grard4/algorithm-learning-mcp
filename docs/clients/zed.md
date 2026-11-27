# Zed setup

**Actual client test:** not installed. Zed's official docs list MCP Tools and Prompts support; full MCP feature parity is not claimed.

Add a server in Settings > AI > MCP Servers. The JSON schema/path must follow the installed Zed version's settings UI; this guide does not assume a configuration file shape. Choose local stdio and enter the Python venv executable and `server.py`, then set `ALGORITHM_KB` and `ALGORITHM_PREFERENCES` in the server's supported environment field if offered. Verify tool discovery and call preferences plus a read/write test.

Official reference: https://zed.dev/docs/ai/mcp


## 统一验收要求

本页配置与客户端实测是两个独立结论。除报告明确记录的 Codex 部分验证外，本机未安装这些客户端；未确认的版本、路径和字段均保留待确认，不保证示例直接可用。

服务端要求 Python 3.11+、本地 SQLite 和独立数据路径。偏好文件由服务器通过 `ALGORITHM_PREFERENCES` 读取；这不证明客户端自身拥有本地文件访问能力。未实测客户端的直接本地文件访问、偏好工具调用、进度写入和持久化均待验证。

验收顺序：初始化（确认完整固定规则） → tools/list（默认 22 工具） → get_course_rules（核对版本 `2`、哈希与正文） → get_learning_preferences → 临时数据库注册/读取 → 带证据更新 → 重启后读取。失败时保留错误，检查路径、解释器、权限、传输和当前客户端配置文档；不得绕过审批或用连接成功替代完整测试。所有写入验证只使用临时数据库。

升级后重新连接以接收新版初始化指令。上述查询是验收流程；日常已有固定规则正文时无需重复获取。私人偏好不能修改固定层，迁移与回滚见 [内置课程规则](../COURSE_RULES.md)。
