# Gemini CLI setup

**Actual client test:** not installed here. The following is an untested reference based on the official Gemini CLI MCP configuration documentation.

Add an `mcpServers` entry in the documented user or project `settings.json` scope:

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
      }
    }
  }
}
```

Use Gemini CLI's documented MCP status interface, then call `get_learning_preferences`, a read tool, and a disposable update. Official reference: https://github.com/google-gemini/gemini-cli/blob/main/docs/tools/mcp-server.md


## 统一验收要求

本页配置与客户端实测是两个独立结论。除报告明确记录的 Codex 部分验证外，本机未安装这些客户端；未确认的版本、路径和字段均保留待确认，不保证示例直接可用。

服务端要求 Python 3.11+、本地 SQLite 和独立数据路径。偏好文件由服务器通过 `ALGORITHM_PREFERENCES` 读取；这不证明客户端自身拥有本地文件访问能力。未实测客户端的直接本地文件访问、偏好工具调用、进度写入和持久化均待验证。

验收顺序：初始化 → tools/list → get_learning_preferences → 临时数据库注册/读取 → 带证据更新 → 重启后读取。失败时保留错误，检查路径、解释器、权限、传输和当前客户端配置文档；不得绕过审批或用连接成功替代完整测试。所有写入验证只使用临时数据库。
