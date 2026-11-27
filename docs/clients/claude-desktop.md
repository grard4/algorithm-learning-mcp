# Claude Desktop setup

**Actual client test:** not installed here. Current Anthropic guidance recommends Desktop Extensions / MCP Bundles (`.mcpb`) for local MCP servers; the simpler user flow installs a bundle from Settings > Desktop app > Extensions. Custom bundles are installed with Settings > Desktop app > Manage Extensions > Advanced settings > Install Extension.

This repository currently ships a Python MCP server but does not yet ship a validated MCPB manifest/bundle. Do not use a guessed manual JSON path. To make a tested/portable Desktop package, the project needs an MCPB manifest with declared Python runtime/dependencies and user-configurable database/preferences paths, then `mcpb pack`; this packaging step is not complete.

If testing a locally packaged variant later, verify server status in Settings > Developer or the Extensions page; inspect tool list, call preferences, then run read/write tests with a disposable database. Official references: [Claude Desktop local servers](https://support.claude.com/en/articles/10949351-getting-started-with-local-mcp-servers-on-claude-desktop) and [MCP Bundles](https://github.com/modelcontextprotocol/mcpb).


## 统一验收要求

本页配置与客户端实测是两个独立结论。除报告明确记录的 Codex 部分验证外，本机未安装这些客户端；未确认的版本、路径和字段均保留待确认，不保证示例直接可用。

服务端要求 Python 3.11+、本地 SQLite 和独立数据路径。偏好文件由服务器通过 `ALGORITHM_PREFERENCES` 读取；这不证明客户端自身拥有本地文件访问能力。未实测客户端的直接本地文件访问、偏好工具调用、进度写入和持久化均待验证。

验收顺序：初始化 → tools/list → get_learning_preferences → 临时数据库注册/读取 → 带证据更新 → 重启后读取。失败时保留错误，检查路径、解释器、权限、传输和当前客户端配置文档；不得绕过审批或用连接成功替代完整测试。所有写入验证只使用临时数据库。
