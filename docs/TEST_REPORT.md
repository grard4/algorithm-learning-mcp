# 发布前测试报告

> 状态说明（2026-11-27）：仓库现已公开。Codex CLI 批准、拒绝及合成知识读写已实测；兼容性仍按实际覆盖范围标记为部分验证。下文阶段性失败、待办和“未发布”描述保留其历史时点，不代表当前发布状态。当前总览见 [发布验收](FINAL_RELEASE_ACCEPTANCE.md)，版本变化见 [变更记录](../CHANGELOG.md)。

日期：2026-11-27。实际环境：Windows 11、Python 3.14.7、MCP Python SDK 1.30.0、Codex CLI 0.171.0-alpha.13.2。

## 本轮执行结果

完整隔离测试 **16 项通过，0 失败，0 错误**，耗时 29.151 秒。命令：

```powershell
.\.venv\Scripts\python.exe -m pytest -q --basetemp=.release-audit/final-check/pytest-final --junitxml=.release-audit/final-check/pytest-final.xml
.\.venv\Scripts\python.exe -m pip check
```

临时数据库、归档和证据均在 E 盘独立副本内的忽略目录。未使用原业务数据库。pip check 返回 No broken requirements found。

| 测试函数 | 结果 | 秒 |
|---|---|---:|
| `test_blank_database_and_r3_journal` | 通过 | 1.64 |
| `test_concurrent_independent_topic_writes` | 通过 | 3.259 |
| `test_registration_idempotency_and_backup_restore` | 通过 | 1.923 |
| `test_streamable_http_initialization_and_tools` | 通过 | 3.082 |
| `test_stdio_initialization_discovery_preferences_and_updates` | 通过 | 2.996 |
| `test_missing_empty_invalid_and_reload` | 通过 | 0.058 |
| `test_aggregate_validation_and_no_partial_data` | 通过 | 1.901 |
| `test_missing_evidence_rejected` | 通过 | 1.736 |
| `test_update_replay_conflict_and_persistence` | 通过 | 2.051 |
| `test_mid_transaction_failure_rolls_back` | 通过 | 2.065 |
| `test_existing_mapping_reuse_and_conflict` | 通过 | 2.42 |
| `test_preference_size_boundary` | 通过 | 0.028 |
| `test_unselected_rollout_is_not_imported` | 通过 | 1.73 |
| `test_base_schema_upgrade_preserves_existing_topic` | 通过 | 3.672 |
| `test_discovery_cutoff_is_persisted_once` | 通过 | 0.036 |
| `test_invalid_discovery_cutoff_fails_closed` | 通过 | 0.037 |

## 覆盖范围

- 空库初始化、基础 Schema 升级、重复初始化与数据保留；不代表测试所有历史数据库版本的迁移。
- stdio/Streamable HTTP 初始化与调用，21 个工具的发现，全部参数 Schema 合法性，批量检索参数。
- 来源消息、进度、知识写入与检索；证据缺失拒写；多个字段错误一次返回。
- 相同请求重放、不同内容同请求拒绝、陈旧版本拒绝、事务中途异常全批回滚。
- 20 次并发注册、关联复用与冲突拒绝、备份恢复、重启持久化。
- 偏好缺失、变更、无效 UTF-8、空文件、64 KiB 边界及超限拒绝。
- 未选中的 Codex 日志不导入，发现起点持久化及无效起点拒绝。
- C2.3 空库返回 not_indexed，缺失 link 拒绝，不提供批准/导入工具，不自动改变掌握状态。

以上为 SDK 模拟客户端及本地集成测试；其他厂商真实客户端均未运行。公开测试明细见 `evidence/release-tests.json`，协议发现原文见 `evidence/stdio-tools-list.json`。

## 真实 Codex 验证

本轮先因测试命令的点分键名转义错误启动失败；只修正进程参数后重试，没有改持久配置、安全策略或模型路由。

第二次尝试时间为 2026-11-27 10:22:19—10:23:19（Asia/Shanghai）。Codex 发现发布副本工具，并尝试一次 `release_acceptance.get_learning_preferences({})`；被拒绝：

```text
MCP tool call requires approval, but approval policy is never
```

真实工具业务操作完成 0 次，真实写入测试 0 次。客户端退出码 0 仅表示正常结束，不能视为工具调用成功。Codex 状态仍为部分验证。持久 config.toml 前后哈希一致；这不是原业务数据库哈希验证。公开证据见 `evidence/codex-client-final.json`，私人原始运行日志不提交。

## 静态检查与局限

语法编译、JSON/TOML 配置示例、Markdown 链接与围栏单独核验。发现 Continue 教程代码围栏未闭合，已补齐并增加验证说明；YAML 示例仅人工结构核对，未安装对应客户端或增加 YAML 解析依赖。

本轮没有重生成课程，也没有安装其他 Agent。完整真实客户端兼容性、所有跨平台运行和安全渗透测试不在已通过范围。

最终静态复查：22 个 Python 文件可编译、43 份 Markdown 链接与围栏通过、6 段 JSON 和 3 段 TOML 通过解析，1 段 YAML 仅人工结构核对。27 个本轮隔离数据库的 integrity_check=ok、foreign_key_check 无错误。随后仅新增本次安全报告文档，不重跑未变更业务测试。

## 最新验收结论：真实读写门槛关闭（2026-11-27）

11:24:29—11:25:19（北京时间），真实 Codex CLI 中的五次工具调用均有用户 Accept 审批：update_learning 两次、read_knowledge 两次、get_update_history 一次，全部返回业务成功。专题版本 5→6→7，知识版本 1→2；中文标题及英文正文逐值核验正确。已有 Cancel 测试确认请求未到达服务器。原始数据与私人档案未访问。

合成知识现已通过本地专用 KB 事务清理，剩余记录为 0；创建、修改、清理三条审计保留，清理前证据库保存在本地忽略目录。清理不是一次真实 MCP 调用，不据此声称 MCP 删除接口已验证。学习进度未改变，integrity_check=ok，foreign_key_check 无错误。

核验脚本曾以 sqlite.Row 的 repr 生成 before-write 表摘要，该摘要无效，相关断言失败如实保留；已改用此前基于实际 tuple 值的 before-readonly 摘要确认 topic_progress 一致，不伪造修正历史摘要。测试启动时 PowerShell 的 JSON 引号问题已由参数数组启动修正，失败启动未发出工具调用。

用户明确要求停止管理员沙箱排查并继续发布准备。故将 provisioning service 不可用保留为已知限制，不作为当前业务发布阻塞；不声称 OS 隔离已验收。MCP 服务进程以宿主权限运行，固定测试数据路径与工具白名单不能替代操作系统访问控制。负向权限证据仅包括用户取消后零执行，以及测试连接不加载原业务 MCP；未对原业务库或私人档案实施访问探测。

Codex 兼容性整体仍为部分验证：真实 CLI 的以上能力已验证；Desktop 全场景、偏好读取真实调用、多用户安全隔离未验证。此限制已写入双语 README。真实读写及审批门槛关闭，不等于所有功能/安全边界都通过。公开发布仍需最终材料复核及独立发布授权；本任务不提交、建仓或 Push。

公开证据：evidence/codex-approval-write.json、evidence/codex-approval-rejection.json。本地详细证据：.release-audit/approval-interactive/write-call-evidence.json、write-approval-decisions.json、write-cleanup-evidence.json。
