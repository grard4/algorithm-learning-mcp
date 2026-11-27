# 聊天注册与同步机制说明

## 各 Agent 共用的 MCP 接入方式

各客户端使用同一套 MCP 服务器实现；需要共享数据的客户端连接同一数据库。开始长期算法课程时，Agent 应从客户端取得真实聊天 ID，再调用 `register_conversation`。已有专题从该学习者自己的数据库解析；新专题须提供明确名称，服务器生成确定性的通用 canonical 值。服务器不能自动发现任意厂商的聊天 ID。单题聊天不应注册为长期专题。

学习记录不会由隐藏的服务器监听器自动捕获。形成值得持久保存的成果后，Agent 须携带来源消息 ID 调用 `update_learning`。这样可明确记录来源与证据，并适用于能够调用 MCP 工具的客户端。无法提供稳定聊天 ID 或无法调用工具的客户端，不能完成这种自动注册与更新。

## 可选的 Codex 会话日志导入

`sync.py` 仅适配 Codex 格式，在指定的 Codex 主目录中扫描 JSONL/Zstandard 会话日志。它不解析 Claude、Cursor 或 VS Code 历史。该功能须主动启用，并且仅指向目标学习者的 Codex 主目录。

- 一次性历史导入：将 `config/initial_threads.example.json` 复制为 `config/initial_threads.json`，用明确选定的 Codex 聊天 ID 和确认的专题名称替换占位内容，再执行 `python sync.py --initial`。每个 ID 必须恰好匹配一个会话日志文件，不能默认导入全部历史聊天。
- 增量发现：在 `config/topic_aliases.json` 中配置希望自动匹配的别名，再执行 `python sync.py --discover --watch --interval 120`。这是轮询，不是实时监听。首次运行时，worker 创建持久化的 `config/discovery_since.txt` 时间戳，将扫描范围限定为该 worker 首次启动后创建的会话；后续轮询沿用该时间。默认空别名模板会把不确定专题保留为发现候选，不能猜测 canonical ID 或自动合并有歧义的专题。
- 使用 Ctrl+C 或原启动进程管理器停止监测。服务器不会自动启动该进程。

`config/topic_aliases.example.json` 是空结构示例，`config/initial_threads.example.json` 说明导入格式。记录包含 `name`、`canonical` 和可选的 `aliases`，具体值由使用者定义。`initial_threads.json` 由 Git 忽略，因为其中的 ID、标题或路径可能暴露私人聊天历史。

## 能力边界

- Codex 专用日志导入不是 MCP 协议能力，也不是通用多 Agent 同步方案。
- 其他客户端可通过 MCP 注册、上下文读取和显式的证据校验更新实现共享；无人值守的历史导入需要另行提供受支持的导出适配器。
- 新聊天自动识别依赖客户端能力。没有客户端事件 API 或已配置的轮询适配器时，注册由当前聊天中的 Agent 调用工具触发。
- 120 秒轮询可能产生一个轮询周期的延迟，且可能无法识别不受支持的日志格式，不能称为实时监听。
- 接受映射前应审核发现候选与冲突。导入器不会把课程计划或助手讲解等同于学习者已经掌握。
