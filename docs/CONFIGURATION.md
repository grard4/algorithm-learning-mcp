# 配置说明

| 环境变量 | 用途与默认值 |
|---|---|
| ALGORITHM_KB | SQLite 路径；默认项目 data/learning.sqlite3 |
| ALGORITHM_PREFERENCES | UTF-8 私人偏好文件；默认 config/learning_preferences.md，上限 64 KiB |
| ALGORITHM_MCP_TRANSPORT | stdio（默认）或 streamable-http |
| ALGORITHM_MCP_HOST | HTTP 默认 127.0.0.1；只允许回环 IP 或 localhost，非回环报 UNSAFE_HTTP_BIND |
| ALGORITHM_MCP_PORT | HTTP 默认 8000 |
| ALGORITHM_LEGACY_TOOLS | 设为 1 暴露兼容工具；默认使用 21 个核心/管理接口 |

客户端配置以 clients/ 下文档为入口，使用绝对路径。各客户端复用同一 server.py，不为每个厂商维护服务器分支。默认不启用 Codex 日志监测；同步方式与范围见 SYNC_AND_DISCOVERY.md。

偏好模板是 config/learning_preferences.example.md，复制到私人路径后自行编辑。不要将学习偏好或客户端凭据提交到仓库。
