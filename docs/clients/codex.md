# OpenAI Codex setup

**客户端状态：部分验证。** Windows 上的真实 Codex CLI 已完成初始化、工具发现、用户批准/取消，以及合成知识创建、读取、更新和审计。早期非交互调用失败已由独立交互会话验证闭环；不代表 Desktop 全场景、偏好工具或 OS 隔离已验证。详见 [真实调用验收](../CODEX_INTEGRATION_TEST.md)。

## Requirements

- Codex CLI/Desktop with MCP support (this environment reported CLI 0.171.0-alpha.13.2 on Windows 11).
- Python environment with the project requirements installed.
- Writable, learner-owned SQLite and preferences paths.

## Configure with Codex CLI

The local CLI documents `codex mcp add <name> --env KEY=VALUE -- <command> ...`. From PowerShell, replace the paths:

```powershell
codex mcp add algorithm-learning `
  --env ALGORITHM_KB='C:\Users\you\AppData\Local\algorithm-learning\learning.sqlite3' `
  --env ALGORITHM_PREFERENCES='C:\Users\you\AppData\Local\algorithm-learning\learning_preferences.md' `
  -- 'C:\path\to\algorithm-learning-mcp\.venv\Scripts\python.exe' `
     'C:\path\to\algorithm-learning-mcp\server.py'
```

The command changes the Codex user's configuration. Review it before running. For project-specific configuration, add a table to `.codex/config.toml` in the project:

```toml
[mcp_servers.algorithm_learning]
command = "C:\\path\\to\\algorithm-learning-mcp\\.venv\\Scripts\\python.exe"
args = ["C:\\path\\to\\algorithm-learning-mcp\\server.py"]
cwd = "C:\\path\\to\\algorithm-learning-mcp"
[mcp_servers.algorithm_learning.env]
ALGORITHM_KB = "C:\\Users\\you\\AppData\\Local\\algorithm-learning\\learning.sqlite3"
ALGORITHM_PREFERENCES = "C:\\Users\\you\\AppData\\Local\\algorithm-learning\\learning_preferences.md"
```

## Verify

Run `codex mcp list`; in an active Codex session inspect `/mcp` or the MCP server panel. Ask it to call `get_learning_preferences`, then make a read, registration, and disposable evidence-backed update. A server-list entry or tool discovery alone is not full compatibility.

## Troubleshooting

Use absolute paths and the project venv's Python. If the server fails, run `python server.py` from the project directory to inspect stderr, confirm write access to `ALGORITHM_KB`, and check dependency installation. Do not expose credentials in logs or share a learner DB with unrelated users.

Official reference: https://developers.openai.com/codex/mcp


## 统一验收要求

本页配置与客户端实测是两个独立结论。除报告明确记录的 Codex 部分验证外，本机未安装这些客户端；未确认的版本、路径和字段均保留待确认，不保证示例直接可用。

服务端要求 Python 3.11+、本地 SQLite 和独立数据路径。偏好文件由服务器通过 `ALGORITHM_PREFERENCES` 读取；这不证明客户端自身拥有本地文件访问能力。未实测客户端的直接本地文件访问、偏好工具调用、进度写入和持久化均待验证。

验收顺序：初始化（确认完整固定规则） → tools/list（默认 22 工具） → get_course_rules（核对版本 `2`、哈希与正文） → get_learning_preferences → 临时数据库注册/读取 → 带证据更新 → 重启后读取。失败时保留错误，检查路径、解释器、权限、传输和当前客户端配置文档；不得绕过审批或用连接成功替代完整测试。所有写入验证只使用临时数据库。

升级后重新连接以接收新版初始化指令。上述查询是验收流程；日常已有固定规则正文时无需重复获取。私人偏好不能修改固定层，迁移与回滚见 [内置课程规则](../COURSE_RULES.md)。
