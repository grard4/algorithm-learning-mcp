# 审计基线

核查日期：2026-11-27（Asia/Shanghai）。目标：grard4/algorithm-learning-mcp。

- 本地与 GitHub main：`42f593752c295bb2ef5d647a40c00bead19dde94`。
- GitHub HEAD 通过 GitHub 连接器 commits/main 核实；git ls-remote 直连失败（连接不可达），未改动网络或权限策略。
- 原 main 工作区无已跟踪修改和未跟踪文件；忽略的环境、缓存、旧发布材料均保留。
- 独立工作树：`algorithm-learning-mcp-audit-20261127`；分支 `audit/security-review-20261127`。原 main 不修改。
- `algorithm-learning-mcp-local-audit` 只有历史 source-manifest.json，不是 Git 仓库，不作为当前源码。
- Windows / Python 3.14.7 / SQLite 3.50.4 / MCP 1.30.0 / pytest 9.2.0 / Starlette 1.10.0 / uvicorn 0.54.0。另检测到 Python 3.12.15，尚未验证。
- 原仓库 data 仅有 .gitkeep；不连接原部署数据库，不读取私人聊天，不调用已连接生产 MCP 业务工具。
- 测试仅用临时数据库及合成日志。数据库完整性结论只针对隔离库。
- 本轮不安装第三方 Agent 客户端；协议/SDK 模拟/静态配置与真实客户端验证分开报告。跨平台 CI 未执行前一律 NOT VERIFIED。
- 既有 SECURITY_AUDIT 与 final-security-audit 主要检查发布隐私；其中历史测试结论不作为本轮安全证明。

## 审计范围与调用链

`server.tool → Context.update → contracts.validate_changes → KB.mutate → KB.change → SQLite triggers`；
`sync_file → read_bytes/parse/visible → KB.mutate → archives/messages/sync_state → finish_extraction`；
`server._concept_read → ReadCache → notifications.health → compact_api → concept_reader.project/inspect_link`；
`Context.search → search_engine.search`；CLI 初始化/备份/恢复；三份 SQL、所有测试、发布脚本、工作流、双语文档。

审计覆盖 A01—A05、B01—B05、C01—C03 及最后的性能基准；逐项复现后再修改业务代码。
