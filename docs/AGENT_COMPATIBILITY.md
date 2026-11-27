# MCP 多 Agent 兼容性报告

> 当前协议基线为 22 工具、内置规则版本 `2`。stdio/HTTP SDK 验证见 [规则验收](COURSE_RULES_VERIFICATION.md)；客户端是否把初始化指令完整交给模型仍需真实客户端验证。下文旧协议证据和真实客户端结果保留各自版本边界。

> 状态说明（2026-11-27）：仓库现已公开。Codex CLI 批准、拒绝及合成知识读写已实测；兼容性仍按实际覆盖范围标记为部分验证。下文阶段性失败、待办和“未发布”描述保留其历史时点，不代表当前发布状态。当前总览见 [发布验收](FINAL_RELEASE_ACCEPTANCE.md)，版本变化见 [变更记录](../CHANGELOG.md)。

原审计日期：2026-11-26；本轮复核日期：2026-11-27。本机系统为 Windows 11，用户确认仅安装 Codex，未安装或运行其他客户端。

本报告区分文档调研、静态检查、协议层测试、模拟客户端测试与真实客户端测试。服务器当前提供 Tools，不实现 MCP Resources 或 Prompts。

## 状态定义

- **已实际验证**：在真实安装的客户端完成连接与工具调用测试。
- **部分验证**：真实客户端已完成部分测试，尚未覆盖全部核心能力。
- **协议层适配，待客户端验证**：已检查标准协议或配置结构，或完成 SDK 握手；未完成对应客户端真实测试。
- **理论兼容，待验证**：具备 MCP 接入可能，但证据不完整。
- **仅供测试**：仅提供实验性示例。
- **不支持**：已确认存在限制。

## 客户端兼容性矩阵

服务器的 SDK 测试协商得到 MCP 协议 `2025-11-25`；这不是任何厂商客户端的实测协议版本。“未测试”表示未在本环境连接对应客户端，配置语法检查与真实客户端运行必须分别记录。

| Agent | 客户端版本 / 系统 | 客户端协商的 MCP 版本 | 传输或配置依据 | 配置示例 | 真实测试 | 状态 |
|---|---|---|---|---|---|---|
| OpenAI Codex | CLI 0.171.0-alpha.13.2 / Windows 11 | 2025-06-18（客户端初始化请求） | 本地 stdio | 已提供 | CLI 批准、拒绝及合成知识读写/审计已验证；偏好及 Desktop 全面验证未完成 | 部分验证 |
| Claude Desktop | 未安装 | 未测试 | 官方 Desktop Extensions / MCPB；本仓库未提供扩展包 | 未提供；打包待完成 | 未运行 | 理论兼容，待验证 |
| Claude Code | 未安装 | 未测试 | 原教程缺失；本轮官方页面 403，当前配置待确认 | 暂不提供 | 未运行 | 理论兼容，待验证 |
| Cursor | 未安装 | 未测试 | 官方已说明 MCP 功能；当前具体配置细节未确认 | 未提供 | 未运行 | 理论兼容，待验证 |
| VS Code + GitHub Copilot | 未安装 | 未测试 | 官方 Copilot MCP 配置（`mcpServers`） | 已提供 | 未运行 | 协议层适配，待客户端验证 |
| Cline | 未安装 | 未测试 | 当前官方 Schema 未确认 | 未提供 | 未运行 | 理论兼容，待验证 |
| Roo Code | 未安装 | 未测试 | 官方本地 stdio 设置与 JSON Schema | 仅参考 | 未运行 | 协议层适配，待客户端验证 |
| DeepSeek Harness | 未安装 | 未测试 | 该产品的官方 MCP 文档未确认 | 未提供 | 未运行 | 理论兼容，待验证 |
| 腾讯 WorkBuddy | 未安装 | 未测试 | 官方客户端 MCP 细节未确认 | 未提供 | 未运行 | 理论兼容，待验证 |
| Windsurf | 未安装 | 未测试 | 具体官方 MCP 配置未确认 | 未提供 | 未运行 | 理论兼容，待验证 |
| Gemini CLI | 未安装 | 未测试 | 官方 `mcpServers` 配置指南 | 已提供 | 未运行 | 协议层适配，待客户端验证 |
| Continue | 未安装 | 未测试 | 官方 `mcpServers` YAML 与传输字段 | 已提供 | 未运行 | 协议层适配，待客户端验证 |
| Goose | 未安装 | 未测试 | 当前官方客户端配置未确认 | 未提供 | 未运行 | 理论兼容，待验证 |
| OpenCode | 未安装 | 未测试 | 官方本地 `mcp.servers` 配置；stdio | 已提供 | 未运行 | 协议层适配，待客户端验证 |
| Google Antigravity | 未安装 | 未测试 | 官方 MCP 客户端配置未确认 | 未提供 | 未运行 | 理论兼容，待验证 |
| Qwen Code | 未安装 | 未测试 | 官方 MCP 配置 Schema 未确认 | 未提供 | 未运行 | 理论兼容，待验证 |
| JetBrains AI Assistant | 未安装 | 未测试 | 官方 MCP 客户端支持范围未确认 | 未提供 | 未运行 | 理论兼容，待验证 |
| Kiro | 未安装 | 未测试 | 官方 MCP 设置文档 | 仅参考 | 未运行 | 协议层适配，待客户端验证 |
| LM Studio | 未安装 | 未测试 | 客户端 MCP 支持与传输方式未确认 | 未提供 | 未运行 | 理论兼容，待验证 |
| LibreChat | 未安装 | 未测试 | 当前配置未验证 | 未提供 | 未运行 | 理论兼容，待验证 |
| Cherry Studio | 未安装 | 未测试 | 当前官方设置未验证 | 未提供 | 未运行 | 理论兼容，待验证 |
| OpenHands | 未安装 | 未测试 | 当前 MCP 工作流未确认 | 未提供 | 未运行 | 理论兼容，待验证 |
| Zed | 未安装 | 未测试 | 官方文档列出 MCP Tools/Prompts；本次未验证配置路径 | 未提供 | 未运行 | 理论兼容，待验证 |
| Gemini Code Assist | 未安装 | 未测试 | 官方入口已列出，具体 MCP 配置待确认 | 未提供 | 未运行 | 理论兼容，待验证 |
| AnythingLLM | 未安装 | 未测试 | 官方入口已列出，具体 MCP 配置待确认 | 未提供 | 未运行 | 理论兼容，待验证 |

### 原审计查阅的官方依据

- [MCP 协议规范](https://modelcontextprotocol.io/specification/2025-11-25)：生命周期、工具和传输。服务器固定使用 MCP Python SDK 1.30.0；这是 SDK 软件包版本，不代表每个客户端均协商得到同一协议版本。
- [OpenAI Codex MCP 指南](https://developers.openai.com/codex/mcp)及本机 `codex mcp --help` (Codex CLI 0.171.0-alpha.13.2).
- [Claude Code MCP](https://code.claude.com/docs/en/mcp), [Claude Desktop 本地 MCP](https://support.claude.com/en/articles/10949351-getting-started-with-local-mcp-servers-on-claude-desktop).
- [Cursor MCP](https://docs.cursor.com/context/mcp).
- [VS Code MCP 配置](https://code.visualstudio.com/docs/agents/reference/mcp-configuration).
- [Gemini CLI MCP servers](https://github.com/google-gemini/gemini-cli/blob/main/docs/tools/mcp-server.md).
- [Continue MCP 配置](https://docs.continue.dev/customize/deep-dives/mcp).
- [OpenCode MCP servers](https://opencode.ai/docs/mcp-servers/).
- [Kiro MCP](https://kiro.dev/docs/mcp/).
- [Zed MCP](https://zed.dev/docs/ai/mcp).
- [Roo Code MCP 配置](https://docs.roocode.com/features/mcp/using-mcp-in-roo).


对于 Cursor 的具体配置，以及 Cline、Windsurf、Goose、DeepSeek Harness、腾讯 WorkBuddy、Antigravity、Qwen Code、JetBrains AI Assistant、LM Studio、LibreChat、Cherry Studio、OpenHands 和 Zed，原审计未确认足够精确的当前官方配置细节，因此未发布其专用配置。这些客户端仍为理论兼容、待验证。未猜测配置字段、文件路径或命令。

上述链接来自原审计，本次翻译未重新开展文档调研。

## 分层测试记录

1. **文档调研**：按以上依据检查协议和配置要求，不能据此证明配置已在本机运行成功。
2. **静态实现检查**：检查共用 Python 实现和客户端示例；各客户端使用同一服务器实现。
3. **协议层测试**：MCP Python SDK 协商得到 `2025-11-25`；`tools/list` 返回 21 个工具。stdio 测试覆盖初始化、学习偏好、注册、带证据的进度与知识更新、检索、并发、备份和发现时间边界持久化；Streamable HTTP 测试覆盖初始化、工具发现和偏好读取。原始工具 Schema 见 `evidence/stdio-tools-list.json`。这些结果属于模拟 MCP 客户端测试，不是 Codex 产品测试。
4. **模拟客户端测试**：使用 MCP Python SDK `ClientSession`，未运行其他厂商的客户端界面或运行时。
5. **真实客户端测试**：Windows 11 上的 Codex CLI 0.171.0-alpha.13.2 启动隔离 MCP 服务器并发现工具。首次 `get_learning_preferences` 调用被当时的 Codex 审批策略阻止，错误为 `MCP tool call requires approval, but approval policy is never`，因此没有完成真实工具操作。测试在任何注册或写入调用前停止，未修改原 Codex 配置。状态为部分验证，不能认定完全兼容。用户确认其他客户端均未安装。证据见 `codex-client-attempt.json`。

## 多客户端数据共享与并发

- 同一使用者的多个本地客户端可指向本地磁盘上的同一 SQLite 文件。事务使用 `BEGIN IMMEDIATE`、外键、忙等待超时与 WAL；多线程注册测试覆盖写入串行化。
- 不同学习者应使用独立数据库。本地服务器没有用户认证与租户隔离。
- 不应通过网络文件系统共享 SQLite，也不应直接向公网暴露 Streamable HTTP。HTTP 默认仅绑定本机回环地址；远程多用户使用前，须由安全部署层提供认证与 TLS。
- stdio 通常由每个客户端启动独立服务器进程。同一使用者的多个进程可以受 SQLite 锁约束共用本地数据库，但不保证远程多写入服务能力。

## 模型独立性

服务器不调用模型 API，也不要求特定模型。README 中 GPT-6-Astra Medium/High 仅是教学质量建议。模型会影响课程质量与工具选择，不影响服务器启动。

## 贡献兼容性测试证据

提交可复现报告时，请提供客户端名称与版本、操作系统与构建版本、实际观察到的 MCP 协议版本、传输方式、脱敏配置、服务器与客户端日志、`tools/list`、临时数据库上的成功读取和写入结果、偏好行为、重启后持久化情况及已知限制。删除秘密信息与私人路径，不得仅凭连接成功宣称完全兼容。

本次中文整理没有重跑客户端测试，也没有提高任何客户端的兼容性等级。


## 2026-11-27 本轮复核

- Codex 在隔离配置下再次发现工具，但一次真实偏好调用仍被审批策略拒绝。证据见 `evidence/codex-client-final.json`；状态不升级。
- 完整隔离测试 16 项通过。stdio 和 HTTP 由 SDK 模拟客户端验证，21 个 Schema 通过检查；不能记为其他 Agent 的真实结果。
- 本轮成功取得 Codex、VS Code、Gemini CLI、Continue、Kiro、Roo Code 官方文档。Claude Code 与 OpenCode 页面返回 403，保留原审计参考但不声称本轮重新验证其配置。其余客户端本轮未重新逐一核实，不扩大支持声明。
- VS Code 当前官方页面明确采用 Copilot harness 的 mcpServers 配置；未将旧 Local harness 格式混用。Continue 文档中缺失的代码围栏已修复。
- 新增 Gemini Code Assist、AnythingLLM 为候选入口。所有未安装客户端的版本与客户端协商协议、直接本地文件访问、偏好读取、写入及持久化结果均未知；服务端读取偏好不等于客户端具有本地文件访问权限。
- 所有客户端教程增加统一验收要求，避免以配置示例或连接指示代替业务验证。

模型推荐仅为使用建议，未做模型横向教学质量测评。社区提交真实版本、系统、脱敏配置、工具结果和持久化证据后才能更新对应状态。

文档完整性补充：原 Claude Code 教程链接目标缺失，现补齐待确认入口；其配置适配状态由原“协议层适配”降为“理论兼容，待验证”。不以不可访问的官方文档或旧文字声明冒充可复核配置证据。

## 最新验收结论：真实读写门槛关闭（2026-11-27）

11:24:29—11:25:19（北京时间），真实 Codex CLI 中的五次工具调用均有用户 Accept 审批：update_learning 两次、read_knowledge 两次、get_update_history 一次，全部返回业务成功。专题版本 5→6→7，知识版本 1→2；中文标题及英文正文逐值核验正确。已有 Cancel 测试确认请求未到达服务器。原始数据与私人档案未访问。

合成知识现已通过本地专用 KB 事务清理，剩余记录为 0；创建、修改、清理三条审计保留，清理前证据库保存在本地忽略目录。清理不是一次真实 MCP 调用，不据此声称 MCP 删除接口已验证。学习进度未改变，integrity_check=ok，foreign_key_check 无错误。

核验脚本曾以 sqlite.Row 的 repr 生成 before-write 表摘要，该摘要无效，相关断言失败如实保留；已改用此前基于实际 tuple 值的 before-readonly 摘要确认 topic_progress 一致，不伪造修正历史摘要。测试启动时 PowerShell 的 JSON 引号问题已由参数数组启动修正，失败启动未发出工具调用。

用户明确要求停止管理员沙箱排查并继续发布准备。故将 provisioning service 不可用保留为已知限制，不作为当前业务发布阻塞；不声称 OS 隔离已验收。MCP 服务进程以宿主权限运行，固定测试数据路径与工具白名单不能替代操作系统访问控制。负向权限证据仅包括用户取消后零执行，以及测试连接不加载原业务 MCP；未对原业务库或私人档案实施访问探测。

Codex 兼容性整体仍为部分验证：真实 CLI 的以上能力已验证；Desktop 全场景、偏好读取真实调用、多用户安全隔离未验证。此限制已写入双语 README。真实读写及审批门槛关闭，不等于所有功能/安全边界都通过。公开发布仍需最终材料复核及独立发布授权；本任务不提交、建仓或 Push。

公开证据：evidence/codex-approval-write.json、evidence/codex-approval-rejection.json。本地详细证据：.release-audit/approval-interactive/write-call-evidence.json、write-approval-decisions.json、write-cleanup-evidence.json。
