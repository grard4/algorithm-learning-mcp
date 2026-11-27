# 算法学习 MCP 服务器

2026-11-27 第三轮：CLI 失败退出码与动态业务错误脱敏已修复；8 MiB Zstandard 窗口按固定版本实测保留字节传参。Windows 双 Python 各 176 项通过，A04 仍为 PARTIAL；本轮未部署、未合并、未执行远程 CI。详见 [第三轮报告](THIRD_ROUND_REMEDIATION_REPORT.md)。

简体中文（默认） | [English](README.en.md)

> **非商业源码公开：允许非商业学习、研究、修改和分享；禁止未经许可的商业利用及非法倒卖。**
>
> 本项目采用 [PolyForm Noncommercial License 1.0.0](LICENSE)，版权署名为 `grard4`。许可范围以正式条款为准，包括其中明确列出的机构使用条款；本说明不增加“只能学习”等额外限制，也不改变合理使用等法定权利。这不是 OSI 意义上的开源许可证。

本项目为算法竞赛学习提供模型无关的 MCP 服务。不同客户端使用同一套业务实现，通过 SQLite 共享专题树、学习进度、带来源的知识、任务、变更历史、备份和概念关联审计事件。

## 架构与功能

客户端通过标准 MCP Tools 调用 `server.py`，业务层负责证据校验、事务与检索，SQLite 负责数据持久化。不要求特定模型服务，不为不同 Agent 单独维护服务器源码。

- 独立专题组成统一逻辑会话树，支持真实聊天 ID 关联和跨专题知识检索。
- L0 索引、L1 本专题摘要、L2 相关知识、L3 指定历史分页读取，支持版本游标与增量读取。
- 学习更新要求来源证据，支持原子事务、幂等请求、乐观版本检查与审计历史。
- 可选 Codex 会话日志导入，只有主动执行才启用；其他 Agent 使用标准注册和更新工具。详见 [同步边界](docs/SYNC_AND_DISCOVERY.md)。
- 固定课程规则版本 `2` 随初始化下发；按需读取可编辑的个人学习偏好，两者独立。
- 数据库备份、恢复与完整性验证。
- 支持 stdio 和 Streamable HTTP；当前不实现 MCP Resources 或 Prompts。

## 系统要求与安装

需要 Python 3.11 或更新版本（三平台 CI 已覆盖 3.11–3.14，范围见 [测试矩阵](TEST_MATRIX.md)），以及支持 JSON1、FTS5 的 SQLite。客户端须支持选定的传输方式和工具 Schema，协议能力不等于真实客户端兼容性已验证。

公开仓库：[grard4/algorithm-learning-mcp](https://github.com/grard4/algorithm-learning-mcp)。版本说明与下载见 [GitHub Releases](https://github.com/grard4/algorithm-learning-mcp/releases)。

```powershell
git clone https://github.com/grard4/algorithm-learning-mcp.git
cd algorithm-learning-mcp
py -3.11 -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install -r requirements.txt
Copy-Item config\learning_preferences.example.md config\learning_preferences.md
python server.py
```

首次启动创建空数据库 `data/learning.sqlite3`，可用 `ALGORITHM_KB` 覆盖路径；不会预置私人课程或学习记录。开发测试依赖不是运行服务的必要条件。

## 客户端配置

每个使用者应配置自己的数据库和偏好文件。同一学习者、同一主机上的多个客户端可共享本地 SQLite 文件，写入由 SQLite 串行化。无关学习者应分开数据库，不使用网络共享盘存放共用 SQLite。

Codex 配置示例（绝对路径替换为自己的路径）：

```toml
[mcp_servers.algorithm_learning]
command = "C:\\path\\to\\algorithm-learning-mcp\\.venv\\Scripts\\python.exe"
args = ["C:\\path\\to\\algorithm-learning-mcp\\server.py"]
cwd = "C:\\path\\to\\algorithm-learning-mcp"
[mcp_servers.algorithm_learning.env]
ALGORITHM_KB = "C:\\Users\\you\\AppData\\Local\\algorithm-learning\\learning.sqlite3"
ALGORITHM_PREFERENCES = "C:\\Users\\you\\AppData\\Local\\algorithm-learning\\learning_preferences.md"
```

配置位置与步骤见 [Codex 接入](docs/clients/codex.md)。其他客户端入口见 [客户端目录](docs/clients/README.md)，未实测的示例仅供参考，不保证复制即用。

设置 `ALGORITHM_MCP_TRANSPORT=streamable-http` 可启用 HTTP，默认地址为 `127.0.0.1:8000/mcp`。入口拒绝非回环绑定（UNSAFE_HTTP_BIND），保留本地 HTTP；无内置认证或多租户隔离。远程单用户访问方案是经过独立认证的 SSH 隧道，部署未实测；禁止无认证端口转发。本地使用优先选 stdio，详见 [安全说明](docs/SECURITY.md)。

## 自定义学习偏好

将 `config/learning_preferences.example.md` 复制为 `config/learning_preferences.md`，使用自然语言填写教学要求。`get_learning_preferences` 按需读取并在文件变化后重新加载；缺失或为空时使用通用默认值。私人偏好文件已由 `.gitignore` 排除，不应提交。

课程写作与排版的固定规则由 `course_rules.py` 提供，随 MCP 初始化指令直接下发，也可通过只读 `get_course_rules` 查询；不属于个人偏好，删除、清空或修改偏好文件不会改变它们。规则的适用范围及明确例外保持有效。升级迁移和执行边界见 [内置课程规则](docs/COURSE_RULES.md)。

## 推荐模型与课程质量

推荐主要教学模型为 **GPT-6-Astra（High 或 Medium 思考强度）**。这是维护者的使用建议，不是服务器硬性依赖，也不是课程质量保证。

算法教学涉及知识体系构建、数学推导、正确性与复杂度证明和代码实现，对推理与上下文理解有较高要求。使用者可选择其他模型，但讲解深度、推导严谨性、知识准确性和代码质量可能不同，应自行核验输出并承担相关质量风险。

## MCP 工具

| 工具 | 用途 |
|---|---|
| `register_conversation` | 将真实聊天 ID 关联到已有或新专题。 |
| `get_context_manifest` | 读取轻量索引或单个聊天的专题映射。 |
| `get_topic_context`、`get_context_delta`、`get_topic_version` | 读取专题摘要、版本与增量变化。 |
| `search_knowledge`、`read_knowledge` | 跨专题检索，再按需读取详情。 |
| `update_learning` | 在同一事务中更新有证据支持的进度、知识、任务和关联。 |
| `get_global_overview` | 读取精简概览；详细概览按需获取。 |
| `get_learning_preferences` | 读取学习偏好。 |
| `get_course_rules` | 读取代码内置、版本化的课程规则；无写接口。 |
| `search_concept_knowledge`、`read_concept_link`、`get_concept_changes` | 读取已存在的批准概念关联及来源失效信息。 |
| `get_conversation_history` | 分页读取指定原始消息。 |
| `rollback_update`、`get_update_history`、`detect_knowledge_conflicts` | 审计、回滚与冲突检查。 |

默认提供 22 个工具，完整参数以 `tools/list` 返回的 Schema 为准。旧读取兼容工具可通过 `ALGORITHM_LEGACY_TOOLS=1` 暴露；六个不安全旧写接口在 MCP、CLI 和直接调用中均已停用，使用 `update_learning` 替代。兼容变化与导入上限见 [输入预算](docs/INPUT_BUDGETS.md)。

使用顺序示例：先取得真实聊天 ID，通过 `get_context_manifest` 查询已有映射；需要时才注册。授课前按需读取专题上下文，遇到相关概念再搜索，形成持久成果后携带来源证据调用 `update_learning`。不能猜测聊天 ID 或把讲授自动等同于掌握。

## 兼容性与测试状态

本机只安装 Codex。独立 Codex CLI 已真实验证用户批准、拒绝及合成知识创建、读取、更新和审计；Desktop 全部场景、偏好工具和 OS 隔离仍未完整验证，因此整体标记为部分验证。其他客户端的说明依据协议或文档，未完成对应客户端运行验证。

| Agent | 适配状态 | 真实客户端测试 |
|---|---|---|
| OpenAI Codex | 部分验证 | CLI 批准/拒绝及知识读写已实测；其他能力见验收报告 |
| Claude Desktop | 理论兼容，待验证 | 未运行 |
| Claude Code | 理论兼容，待验证 | 未运行 |
| Cursor | 理论兼容，待验证 | 未运行 |
| VS Code + GitHub Copilot | 协议层适配，待客户端验证 | 未运行 |
| Cline | 理论兼容，待验证 | 未运行 |
| Roo Code | 协议层适配，待客户端验证 | 未运行 |
| DeepSeek Harness | 理论兼容，待验证 | 未运行 |
| Tencent WorkBuddy | 理论兼容，待验证 | 未运行 |
| Windsurf | 理论兼容，待验证 | 未运行 |
| Gemini CLI | 协议层适配，待客户端验证 | 未运行 |
| Continue | 协议层适配，待客户端验证 | 未运行 |
| Goose | 理论兼容，待验证 | 未运行 |
| OpenCode | 协议层适配，待客户端验证 | 未运行 |
| Google Antigravity | 理论兼容，待验证 | 未运行 |
| Qwen Code | 理论兼容，待验证 | 未运行 |
| JetBrains AI Assistant | 理论兼容，待验证 | 未运行 |
| Kiro | 协议层适配，待客户端验证 | 未运行 |
| LM Studio | 理论兼容，待验证 | 未运行 |
| LibreChat | 理论兼容，待验证 | 未运行 |
| Cherry Studio | 理论兼容，待验证 | 未运行 |
| OpenHands | 理论兼容，待验证 | 未运行 |
| Zed | 理论兼容，待验证 | 未运行 |
| Gemini Code Assist | 理论兼容，待验证 | 未运行 |
| AnythingLLM | 理论兼容，待验证 | 未运行 |


详见 [兼容性报告](docs/AGENT_COMPATIBILITY.md)。连接或工具发现成功不等于完整兼容。欢迎提交可复现测试证据，不能将模拟客户端测试当作厂商客户端测试。

## C2.3 与同步限制

C2.3 是高级只读概念接口，只读取已有的批准关联。本副本没有附带经过审核的概念导入与管理工作流，新空数据库可能返回 `not_indexed`。不能通过这些只读接口创建批准关联，不能把 link 当作掌握状态。

服务器不会实时监听所有 Agent 聊天。新聊天注册依赖 Agent 工具调用或特定客户端适配器；Codex 轮询导入不是通用实时同步。

## 数据隔离与安全

仓库从空数据库开始。数据库、归档、备份、私人偏好、运行配置和日志不得提交。不要将含学习记录的数据库用于公开测试。服务器不会自行调用模型 API；客户端如何将工具结果送入模型取决于客户端设置。

## 备份与恢复

```powershell
python cli.py backup backups\backup-2026-01-01.sqlite3
python cli.py verify
python cli.py restore backups\backup-2026-01-01.sqlite3 data\restored.sqlite3
```

恢复写入新目标，拒绝覆盖。切换 `ALGORITHM_KB` 到经过验证的恢复数据库前停止服务。原数据库的只读访问记录不能代替前后哈希验证；本次开源任务没有原业务数据库的前后哈希对照。

## 测试、常见问题与贡献

开发测试先执行 `python -m pip install -r requirements-dev.txt`，再执行 `python -m pytest`。当前结果与验证边界见 [测试矩阵](TEST_MATRIX.md)，早期记录见 [历史测试报告](docs/TEST_REPORT.md)。

- 查不到概念关联：新数据库没有经过审核的概念索引，不代表普通知识检索不可用。
- 工具调用被审批阻止：遵循客户端正常授权流程，不降低安全策略；工具发现不能代替调用验证。
- 偏好没有生效：检查 `ALGORITHM_PREFERENCES` 指向的 UTF-8 文件，并调用偏好读取工具。
- 多客户端共享失败：确认是同一使用者的本地数据库，检查路径与 SQLite 锁错误，不改用未经验证的网络共享库。

贡献前阅读 [贡献说明](CONTRIBUTING.md)。兼容性反馈需提供版本、系统、传输、脱敏配置和真实工具结果。变更记录见 [CHANGELOG.md](CHANGELOG.md)。

## 版权与许可证

采用 [PolyForm Noncommercial License 1.0.0](LICENSE)，版权署名为 `grard4`。分发软件副本时须传递许可证文本或其链接，以及 [COPYRIGHT](COPYRIGHT) 中的 Required Notice。许可允许符合条款的修改和再分发，但不授予被许可人再许可或转让其许可的权利。

该许可允许所有非商业目的，并明确允许其中列出的慈善、教育、公共研究等机构使用，不论资金来源。它不是强 Copyleft，不要求所有修改版公开源码。不得把合规非商业分享称为非法倒卖。

第三方组件保留各自版权与许可证；未来贡献者保留自身贡献版权，不自动转让给维护者。项目名称、Logo 和商标不因代码公开自动获得授权。详见 [贡献规则](CONTRIBUTING.md)、[版权审计](docs/COPYRIGHT_AUDIT.md) 和 [许可决策](docs/LICENSING_DECISION.md)。

正式 LICENSE 保留官方英文原文；本页中文说明不替代或修改许可证条款。仓库已公开发布；已验证能力与仍未验证的范围见下方验收说明。

## 发布验收与更多文档

第二轮审计修复在独立分支完成：Windows Python3.12/3.14各154项通过，10个隔离资源探针符合预期；旧写停用、错误脱敏、导入和同步预算及恢复已验证。固定规则内容不变，Schema演进仅作设计。当前CI及未验证事项见 [第二轮测试矩阵](ROUND2_TEST_MATRIX.md) 和 [发布准备](RELEASE_READINESS.md)；不宣称支持公网部署。下段为PR #2历史交付。

2026-11-27：PR #1 审计修复已合并；PR #2 交付内置课程规则版本 `2`，最新功能提交通过本地 88 项测试与 13 个 CI 作业。当前安全边界、兼容性和验证范围见 [测试矩阵](TEST_MATRIX.md)、[规则验收](docs/COURSE_RULES_VERIFICATION.md) 与 [发布准备](RELEASE_READINESS.md)。既有 `v0.1.1` 标签不包含这些后续代码变更；下述 16 项及真实客户端记录属于早期发布验收。

首次发布阶段（2026-11-27）的隔离测试当时为 16 项通过，当前结果见页首第三轮报告；真实 Codex CLI 已通过用户控制的批准、拒绝及五步合成知识读写验收。第三方依赖不捆绑分发。偏好工具、Desktop 全部场景及 OS 隔离不在已验证范围；Windows 管理员沙箱运行时故障按用户决定保留为已知限制。详见 docs/CODEX_INTEGRATION_TEST.md。

- [安装与初始化](docs/INSTALLATION.md)
- [配置说明](docs/CONFIGURATION.md)
- [使用流程](docs/USER_GUIDE.md)
- [安全边界](docs/SECURITY.md)
- [第三方依赖](docs/THIRD_PARTY.md)
- [最终发布验收](docs/FINAL_RELEASE_ACCEPTANCE.md)
