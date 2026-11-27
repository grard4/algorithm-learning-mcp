# Roo Code setup

**Actual client test:** not installed here. This untested configuration follows the official Roo Code MCP JSON shape.

## Requirements and configuration location

Use a current Roo Code VS Code extension with MCP enabled. Open the Roo pane's MCP settings and choose **Edit Project MCP** to create `<workspace>/.roo/mcp.json`, or **Edit Global MCP** to open the user-level `mcp_settings.json`.

## Example

```json
{
  "mcpServers": {
    "algorithm-learning": {
      "command": "C:\\path\\to\\algorithm-learning-mcp\\.venv\\Scripts\\python.exe",
      "args": ["C:\\path\\to\\algorithm-learning-mcp\\server.py"],
      "cwd": "C:\\path\\to\\algorithm-learning-mcp",
      "env": {
        "ALGORITHM_KB": "C:\\Users\\you\\AppData\\Local\\algorithm-learning\\learning.sqlite3",
        "ALGORITHM_PREFERENCES": "C:\\Users\\you\\AppData\\Local\\algorithm-learning\\learning_preferences.md"
      },
      "disabled": false
    }
  }
}
```

Do not add `alwaysAllow` unless you deliberately choose Roo's per-tool auto-approval. Restart/reload the server through Roo's MCP settings. Verify the status panel and discovered tools, then call preferences, read a topic, and perform a write in a disposable database.

## Troubleshooting

Check Python executable, working directory, dependency install, file permissions, and Roo's server logs. Roo's global and project config have different precedence; inspect the active server configuration. A visible connection alone is not full compatibility.

Official reference: https://docs.roocode.com/features/mcp/using-mcp-in-roo


## 统一验收要求

本页配置与客户端实测是两个独立结论。除报告明确记录的 Codex 部分验证外，本机未安装这些客户端；未确认的版本、路径和字段均保留待确认，不保证示例直接可用。

服务端要求 Python 3.11+、本地 SQLite 和独立数据路径。偏好文件由服务器通过 `ALGORITHM_PREFERENCES` 读取；这不证明客户端自身拥有本地文件访问能力。未实测客户端的直接本地文件访问、偏好工具调用、进度写入和持久化均待验证。

验收顺序：初始化 → tools/list → get_learning_preferences → 临时数据库注册/读取 → 带证据更新 → 重启后读取。失败时保留错误，检查路径、解释器、权限、传输和当前客户端配置文档；不得绕过审批或用连接成功替代完整测试。所有写入验证只使用临时数据库。
