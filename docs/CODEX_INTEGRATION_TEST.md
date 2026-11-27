# Codex 真实工具调用验收

日期：2026-11-27。客户端：真实 Codex CLI 0.171.0-alpha.13.2，Windows；不是 SDK 模拟，也不等同于 Desktop 全部场景验证。

| 检查 | 实际结果 |
|---|---|
| 专用 MCP 初始化及工具发现 | 成功；服务端日志有 initialize 和 tools/list |
| 用户审批界面 | 截图确认出现 Allow / Cancel |
| 批准后只读执行 | get_topic_context 与 get_global_overview 各执行成功一次；日志均为 Accept |
| 返回正确性 | 专题 ID 与测试 fixture 一致；全局概览仅有“审批验收合成专题”；专题摘要本身不包含专题名，非查询失败 |
| 拒绝后不执行 | 未通过：原计划第二次拒绝，但实际记录 Accept 且工具执行；需独立重测 |
| 真实写入/更新/清理 | 未执行；仅初始化合成测试 fixture，不计真实 MCP 写入成功 |
| 数据一致性 | 30 张测试库表前后逐表摘要一致；integrity_check=ok；foreign_key_check 无错误 |
| 操作系统级隔离 | 未通过：管理员沙箱初始化失败，不能用配置 read-only 冒充有效沙箱 |
| 业务数据路径 | 专用服务器固定 E 盘测试库和合成偏好；原业务库未访问；尚未完成完整负向边界验收 |

两次调用北京时间分别为 10:55:57 与 10:56:20。批准事件在服务端接收调用之前。第二项不能标记为拒绝成功，也不能仅凭模型汇总判定客户端故障。

证据：本地 `.release-audit/approval-interactive/approval-decisions.json`、`mcp-delivery.jsonl`、`before-readonly.json`、`after-readonly.json`；原始会话和路径信息不发布。完整诊断见 CODEX_APPROVAL_DIAGNOSIS.md。

当前仍为部分验证。待管理员沙箱故障定位、真实拒绝验证、明确批准后的写入验证及负向权限边界检查完成后再更新结论。未提交 Git、未创建公开仓库、未 Push。

## 操作澄清与重测状态

用户确认上一轮第二次实际选择 Allow，因此批准链一致，拒绝能力当时没有被测试。独立一次性拒绝重测已启动，等待真实 Cancel 和服务端未收到 tools/call 的联合证据，暂不标记通过。

沙箱官方管理员安装成功，但官方运行时初始化失败（app runtime provisioning service is unavailable; refusing helper fallback），readiness=updateRequired。写入与 OS 权限边界验收仍暂停；未降低保护。

## 独立拒绝重测结果（2026-11-27 11:12:14，北京时间）

本节覆盖前文“等待拒绝重测”的状态。客户端实际记录 `ResolveElicitation ... decision: Cancel`，界面返回 `user cancelled MCP tool call`。从重测前保存的服务端日志字节位置检查后续记录，没有任何 `tools/call` 到达服务器。测试库 30 张表摘要与重测前完全一致，integrity_check=ok，foreign_key_check 无错误。因此本次真实用户拒绝验收通过；没有重试或改用其他工具。

结合先前用户明确选择 Allow 的成功查询，已验证专用 Codex CLI 的“批准后执行、取消后不执行”。此结论不延伸到 Desktop 原会话、真实写入或操作系统级沙箱。后两项仍未通过完整验收，公开发布保持暂停。

可公开证据：`docs/evidence/codex-approval-rejection.json`（从 docs 阅读时路径为 `evidence/codex-approval-rejection.json`）；详细本地证据：`.release-audit/approval-interactive/reject-verification.json` 与客户端/服务端原始日志。

## 最新验收结论：真实读写门槛关闭（2026-11-27）

11:24:29—11:25:19（北京时间），真实 Codex CLI 中的五次工具调用均有用户 Accept 审批：update_learning 两次、read_knowledge 两次、get_update_history 一次，全部返回业务成功。专题版本 5→6→7，知识版本 1→2；中文标题及英文正文逐值核验正确。已有 Cancel 测试确认请求未到达服务器。原始数据与私人档案未访问。

合成知识现已通过本地专用 KB 事务清理，剩余记录为 0；创建、修改、清理三条审计保留，清理前证据库保存在本地忽略目录。清理不是一次真实 MCP 调用，不据此声称 MCP 删除接口已验证。学习进度未改变，integrity_check=ok，foreign_key_check 无错误。

核验脚本曾以 sqlite.Row 的 repr 生成 before-write 表摘要，该摘要无效，相关断言失败如实保留；已改用此前基于实际 tuple 值的 before-readonly 摘要确认 topic_progress 一致，不伪造修正历史摘要。测试启动时 PowerShell 的 JSON 引号问题已由参数数组启动修正，失败启动未发出工具调用。

用户明确要求停止管理员沙箱排查并继续发布准备。故将 provisioning service 不可用保留为已知限制，不作为当前业务发布阻塞；不声称 OS 隔离已验收。MCP 服务进程以宿主权限运行，固定测试数据路径与工具白名单不能替代操作系统访问控制。负向权限证据仅包括用户取消后零执行，以及测试连接不加载原业务 MCP；未对原业务库或私人档案实施访问探测。

Codex 兼容性整体仍为部分验证：真实 CLI 的以上能力已验证；Desktop 全场景、偏好读取真实调用、多用户安全隔离未验证。此限制已写入双语 README。真实读写及审批门槛关闭，不等于所有功能/安全边界都通过。公开发布仍需最终材料复核及独立发布授权；本任务不提交、建仓或 Push。

公开证据：evidence/codex-approval-write.json、evidence/codex-approval-rejection.json。本地详细证据：.release-audit/approval-interactive/write-call-evidence.json、write-approval-decisions.json、write-cleanup-evidence.json。
