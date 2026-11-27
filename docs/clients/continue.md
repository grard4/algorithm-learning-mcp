# Continue setup

**Actual client test:** not installed. The Continue guide documents YAML `mcpServers`, and MCP availability in Agent mode; this project has not run in Continue.

Create `.continue/mcpServers/algorithm-learning.yaml` in the workspace. Standalone blocks require metadata:

```yaml
name: Algorithm Learning MCP
version: 0.1.0
schema: v1
mcpServers:
  - name: Algorithm Learning
    type: stdio
    command: C:\path\to\algorithm-learning-mcp\.venv\Scripts\python.exe
    args:
      - C:\path\to\algorithm-learning-mcp\server.py
    env:
      ALGORITHM_KB: C:\Users\you\AppData\Local\algorithm-learning\learning.sqlite3
      ALGORITHM_PREFERENCES: C:\Users\you\AppData\Local\algorithm-learning\learning_preferences.md
```

## 验证与限制

本机未安装 Continue，适用客户端版本未实测。以上按官方文档结构提供参考配置；请进入 Agent 模式，检查服务器工具列表，调用 `get_learning_preferences`，再在临时数据库上验证读写与重启持久化。配置中的路径必须替换为自己的绝对路径。

若无法连接，检查 Python 路径、环境变量、服务器标准错误及当前 Continue 版本支持的配置格式。配置语法或工具发现不能替代业务调用验证。

官方依据：https://docs.continue.dev/customize/deep-dives/mcp


## 统一验收要求

本页配置与客户端实测是两个独立结论。除报告明确记录的 Codex 部分验证外，本机未安装这些客户端；未确认的版本、路径和字段均保留待确认，不保证示例直接可用。

服务端要求 Python 3.11+、本地 SQLite 和独立数据路径。偏好文件由服务器通过 `ALGORITHM_PREFERENCES` 读取；这不证明客户端自身拥有本地文件访问能力。未实测客户端的直接本地文件访问、偏好工具调用、进度写入和持久化均待验证。

验收顺序：初始化 → tools/list → get_learning_preferences → 临时数据库注册/读取 → 带证据更新 → 重启后读取。失败时保留错误，检查路径、解释器、权限、传输和当前客户端配置文档；不得绕过审批或用连接成功替代完整测试。所有写入验证只使用临时数据库。
