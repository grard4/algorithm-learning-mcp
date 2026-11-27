# 独立审计问题记录

基线：42f5937。初次隔离复现：17 项中 12 个断言失败、5 个通过；失败为安全期望与实际行为不符，非测试基础设施错误。原测试 16/16 通过，说明原覆盖不足。

| ID | 等级 | 调用链与基线位置 | 复现/根因 | 初始状态 | 设计 |
|---|---|---|---|---|---|
| A01 | 高 | server.py:507–513 → FastMCP.run | 0.0.0.0、::、非回环 IP 均进入无认证启动分支；默认 loopback 正确。SDK 本身有请求上限，不能声称完全没有限制 | CONFIRMED | 保留本地 HTTP；拒绝非回环绑定；远程采用独立认证的 SSH 隧道到 loopback，不自建认证体系 |
| A02 | 高 | server.update_learning → Context.update:389 | chat A 可写 topic B，conv 仅检查存在 | CONFIRMED | 在写事务内检查归属；跨专题关系保留，actor 字符串不视为管理员凭证 |
| A03 | 高 | contracts.py:99 → Context.update | 外专题证据默认通过；source_conversation 可伪造 | CONFIRMED | 同专题跨聊天保持允许；外专题 evidence_sources 显式标识并校验消息/聊天/专题；进度采用同规则 |
| A04a | 高 | sync.py:140–151 | 时间戳改写未报错；仅比较 content/role | CONFIRMED | 比较完整不可变消息字段，历史 source_hash 保留原证据 |
| A04b | 高 | sync.py:38–46 → sync_file | 半截尾行被忽略但 source_hash 已推进 | CONFIRMED | 不完整 JSONL 整次拒绝，不推进状态 |
| A05 | 中 | concept_reader.py:115–127 | 撤销 create/alias/retract 均通过；内连接无法发现缺失目标 | CONFIRMED | 在投影前校验同概念、早于撤销、link 类型、唯一目标，不修改历史事件 |
| A06 | 高 | sync.py:132 | ../outside 聊天 ID 逃逸预期归档目录 | CONFIRMED | 检查 ID 与解析后路径，原始有效 ID 布局不变 |

证据：tests/security/test_audit_boundaries.py、test_http_policy.py、test_concept_retractions.py；tests/regression/test_sync_integrity.py。全部使用合成内容，临时数据库完整性和外键检查通过。HTTP 非回环测试拦截监听，验证配置分支；尚不代表公网远程调用实测。

未复现：消息正文/角色改写、消息删除/截断均已拒绝；重复同步幂等。同专题跨聊天证据成功，是应保留的能力。其他专项尚为 NEEDS_INVESTIGATION。
