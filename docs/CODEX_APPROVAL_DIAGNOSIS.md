# Codex 审批机制诊断

日期：2026-11-27。状态：部分定位，真实用户审批界面已出现，拒绝和写入验收尚未完成。

## 已核实事实

- 早前非交互 `codex exec` 在 10:22:19—10:23:19（北京时间）发现工具，但调用报错：`MCP tool call requires approval, but approval policy is never`。进程退出码 0 不代表业务成功。
- 本机 CLI 为 0.171.0-alpha.13.2；Desktop Appx 为 26.1120.6357.0。官方本机 app-server `config/read` 返回用户、系统和探测会话层均无显式 approval_policy；`configRequirements/read` 无组织要求。不能将 never 归因于已经找到的全局配置项。
- 官方上游 exec 源码包含非交互 MCP elicitation 取消逻辑。它说明非交互运行不适合作为用户批准/拒绝验收入口；上游 main 不是本机二进制逐字源码，不能据此声称已定位本机内部默认值的全部来源。
- 经用户明确授权，创建专用 E 盘 CODEX_HOME，备份原配置，仅复制模型连接设置、登录凭据及模型目录。目录 ACL 限当前用户与 SYSTEM。第一次 ACL 命令的 SID 表示错误已纠正并核验；不隐瞒该准备错误。
- 专用配置为 on-request、user reviewer、read-only 命令沙箱，测试 MCP 的 default_tools_approval_mode=prompt，仅开放三个只读工具。不修改原配置、不加载原业务 MCP。
- 真实 Codex CLI 交互窗口出现 Allow/Cancel。会话记录确认 on-request；两次 resolve_elicitation 均记录 decision: Accept。服务端随后分别收到 get_topic_context（10:55:57）和 get_global_overview（10:56:20）。第二次没有取得 Cancel 证据，拒绝测试未通过，不能推断用户已拒绝但客户端绕过。
- 用户截图显示管理员沙箱初始化失败。日志工具元数据 sandbox=none，尽管 sandbox_mode=read-only。不能声称 OS 沙箱已建立；没有选择降级保护，也未执行模型 shell 或学习记录写入。错误细节不足，不能推断 UAC 被拒绝或管理员权限不足。

## 原因与下一步

已确认：非交互执行方式不能完成需要用户交互的验收。切换到专用交互窗口后，正常审批和批准后业务执行可用。尚未完整证明 Desktop 当前原会话的审批能力，也未定位沙箱初始化失败的底层原因。

下一步先确认第二次审批的实际操作，保留失败证据；解决管理员沙箱初始化问题后，再进行单独拒绝测试及用户逐次批准的临时写入测试。不采用自动批准、关闭防护或修改原业务连接。

## 证据索引与范围

本地忽略目录 `.release-audit/approval-diagnosis/`：sources.json、exec-lib.txt、本机生成的协议 Schema、resolved-config-sanitized.json。

本地忽略目录 `.release-audit/approval-interactive/`：setup-evidence.json、approval-decisions.json、mcp-delivery.jsonl、before-readonly.json、after-readonly.json、专用会话日志及沙箱日志。配置备份与凭据不得公开。

官方参考：
- https://developers.openai.com/codex/cli/reference
- https://developers.openai.com/codex/config-reference
- https://developers.openai.com/codex/app-server
- https://raw.githubusercontent.com/openai/codex/main/codex-rs/exec/src/lib.rs

所有数据库核查使用只读连接及 query_only；只核查独立测试库和专用客户端日志库。未访问原业务数据库，不宣称原库哈希验证通过。

## 后续核查：拒绝操作澄清与沙箱安装

用户已明确确认第二次选择的是 Allow，与两次 Accept 日志一致。此前拒绝测试现归类为“未执行拒绝操作”，不是拒绝机制失效。

普通权限运行官方 `codex sandbox setup --elevated --current-user` 返回 `orchestrator_elevation_required: sandbox provisioning setup must be run from an elevated process`。通过用户正常 UAC 授权启动官方安装后返回退出码 0，形成 setup_marker 与专用日志；创建/确保 CodexSandboxOffline、CodexSandboxOnline 账户及对应网络阻断规则，没有关闭防火墙。第一次辅助 PowerShell 脚本未带 UTF-8 BOM、未产出安装日志，纠正编码后才取得上述结果。

但本机官方 app-server 的 windowsSandbox/readiness 仍返回 updateRequired。经用户授权并备份专用配置，调用 windowsSandbox/setupStart(mode=elevated) 返回 started=true，随后 setupCompleted 明确 success=false，错误为 `app runtime provisioning service is unavailable; refusing helper fallback`。因此官方初始化并未成功，不能以安装退出码 0 覆盖该失败，也不能假称 OS 隔离就绪。

当前已定位到专用 CLI 的 app runtime provisioning 服务不可用；其不可用的更底层原因尚未确认。不得擅自修改二进制、内部状态或绕过拒绝回退。原始证据新增 sandbox-setup.log、sandbox-setup-elevated.log、sandbox-official-setup.json、before-sandbox-config.toml，均留在本地忽略目录。

独立拒绝重测已启动：只请求一次只读 get_global_overview，由用户选择 Cancel。禁止模型 shell、写入及其他 MCP。它不替代尚未通过的 OS 边界检查。

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
