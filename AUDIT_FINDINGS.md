# 独立审计问题记录

> 历史范围：本文保留 PR #1 审计及合并前的原始结论。PR #1 已合并至 main（`83c73f7`）；其中“草稿”“未合并”、79 项测试等只描述当时状态。PR #2 及当前验证以 [发布准备](RELEASE_READINESS.md) 和 [测试矩阵](TEST_MATRIX.md) 为准。

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

## 最终复核状态（2026-11-27）

以上为修复前记录，下面为最终状态；未将未经复现的推测列为已修复。

| ID | 风险 | 当前实现位置 | 最终状态 | 修复/处置与回归证据 |
|---|---|---|---|---|
| A01 | 高 | server.py HTTP 入口 | VERIFIED | 非回环绑定拒绝，默认本地 HTTP 保留；test_http_policy 三配置及 test_mcp_http 实际 loopback 业务调用通过 |
| A02 | 高 | context.py:377 update | VERIFIED | 写事务验证聊天专题；test_audit_boundaries 的错专题拒绝、同专题跨聊天成功、跨专题关系成功 |
| A03 | 高 | contracts.py:74 validate_changes | VERIFIED | 消息/归档/聊天/专题联查，显式 evidence_sources 作用域，来源声明及 Schema 校验；伪造来源拒绝、显式外专题引用成功 |
| A03b | 高 | contracts.py evidence / context.py 去重分支 | VERIFIED | PR 前独立复核发现额外来源键可在同正文去重时覆盖旧声明；修前参数化回归 1 failed / 1 passed，修后 2 passed。现在验证全部声明并复验最终合并记录，失败时版本与原记录保持不变 |
| C01b | 中 | cli.py main 输出 | VERIFIED | 首轮 Windows/Python 3.11 CI 复现恢复成功后 cp1252 无法编码中文而异常退出；改为可逆 JSON Unicode 转义，新增默认/cp1252/ASCII 子进程回归，含中文目标路径及完整返回内容检查；三平台四版本各 79 项通过 |
| A04a | 高 | sync.py sync_file | VERIFIED | 比较 id、conversation_id、seq、role、timestamp、content、source_line；source_hash 保留最初归档；正文/角色/时间戳/换序回归 |
| A04b | 高 | sync.py parse/read_bytes | VERIFIED | 半截尾行及不完整/损坏压缩帧拒绝；不推进游标；已提交归档的候选提取可恢复 |
| A04c | 中 | sync.py unchanged 分支 | VERIFIED | 原 unchanged 提前返回会掩盖归档丢失/损坏；两项失败用例复现后，重放先核对归档，缺失时由同 hash 原文恢复，损坏时拒绝且不覆盖 |
| A05 | 中 | concept_reader.py:115 project | VERIFIED | 先验证撤销目标存在、同概念、较早且为 link；撤销链/空目标拒绝；重复撤销被 SQLite 唯一约束拒绝；合法 link 撤销成功 |
| A06 | 高 | archive_io.py:8 archive_path | VERIFIED | 原始同步与补充导入共用路径约束和不可覆盖的原子写入；两入口均复现并修复 ../outside 越界 |
| A07 | 中 | server.py record_conversation_update | VERIFIED | 字典 content 原先触发未捕获 ProgrammingError；现在写档前验证非空字符串及消息结构；test_normalized_archive |
| B01b | 高 | kb.py backup | VERIFIED | 检查后出现的同名目标会被原备份覆盖；test_backup_collision 复现后改为临时完整副本加原子不覆盖发布 |
| B02a | 高 | migrations.py:19 initialize | VERIFIED | 旧多次 executescript 提前提交，注入通知安装失败后残留 27 表；现在同一事务回滚，无残留业务表 |
| B02b | 中 | migrations.py initialize | VERIFIED | 原实现接受 user_version=999 和残缺 topics；现在拒绝未知版本/定义漂移，记录 core-v1 checksum；checksum 篡改拒绝。校验表是新增防护，不把原来“没有表”本身算作漏洞 |
| B03a | 中 | cli.py:18 restore | VERIFIED | 原恢复保留 epoch，与缓存约定冲突；现在校验副本、轮换 epoch、原子不覆盖发布；test_restore_epoch |
| B04a | 中 | search_engine.py:176 | VERIFIED | 原分页不检查恢复 epoch；epoch 改变后旧游标仍能使用已复现；现在返回 CURSOR_STALE |
| B05a | 中 | preferences.py:21 | VERIFIED | 成功结果泄露绝对路径；现在成功/失败均不输出路径；test_preferences_privacy |
| B05b | 中 | preferences.py:21 | VERIFIED | 同大小同 mtime 替换返回旧偏好；现在每次有界读取 MAX_BYTES+1，UTF-8 严格解码，stat/read 异常脱敏 |
| C01a | 中 | tests/test_mcp_*.py、sync.py acquire_worker_lock | VERIFIED（Windows） | 原测试固定 .venv/Scripts/python.exe，watch 仅 msvcrt；改用 sys.executable 和按平台选择原生锁。Windows 两进程排他/释放通过；POSIX 分支待 CI |
| P01 | 低/性能 | search_engine.py:223 | VERIFIED | 同快照对重复证据反复 SELECT；查询内记忆存在性后 2070→80 SQL，九组返回哈希不变，不缓存跨快照数据 |

## B01：事务、幂等和回滚

主调用链 KB.mutate → BEGIN IMMEDIATE → request_id/request_hash → 实体写入与 change_history → commit。原有幂等、版本冲突及事务回滚问题 NOT_REPRODUCIBLE：原测试和新增回归均通过，未将正常实现改写。验证 WAL、外键 ON、busy_timeout=30000；6 个真实子进程相同请求仅写入一次；事务内 os._exit 后无未提交行；旧更新回滚冲突拒绝，最新回滚成功并增版本。B01b 是额外确认的备份覆盖竞争缺陷。

## B02：迁移与旧库兼容

三份原 SQL 不修改；只新增迁移校验表。空库、仅 base schema 的旧库、含合成消息/知识/概念的旧库副本均验证。完整副本去掉新 ledger 后再升级，原有每张表逐行相等。迁移失败会回滚 Schema、回填和 ledger。只采用已识别 SQL 定义，未知自定义结构拒绝自动迁移，不覆盖。生产库升级 NOT VERIFIED，本轮不部署。

## B03：缓存与通知

ReadCache 的 TTL/LRU/容量、返回副本、防止调用方修改缓存、源更新/删除、Schema 哈希破坏、通知游标/epoch 均有隔离测试。缓存每次读取通知健康状态与水位；独立连接写入后下一快照不再复用旧证明。R3 源变化触发机制缺陷 NOT_REPRODUCIBLE；恢复 epoch 缺陷为 B03a。任意外部文件替换且伪造相同 epoch 不在支持的恢复契约内。notifications.checked_path 引用未发布 sandbox，但没有调用方；属于未使用的旧辅助函数，不声称该路径可用，暂不改动。

## B04：搜索完整性

5001 条知识、2001 条消息测试证实上限命中时返回 coverage=incomplete；每组批量查询独立分页，没有相互抢占 limit。更换查询签名拒绝游标，正常更新后旧游标失效；B04a 补齐恢复边界。截断为 DESIGN_DECISION：不保证无筛选全库检索的专题公平性，调用者应按 topic_id 缩小范围；不能把 incomplete 的空结果解释为不存在。现有索引与 SQL 截断不能直接替换为全文 SQL 分页而保持 Python 别名/排名语义，因此本轮保留限制和准确披露。

## B05：偏好隐私与配置边界

偏好路径只来自操作者本地配置，没有远程传入路径参数。配置者主动指定的常规文件或符号链接目标属于受信任输入，未全面禁止链接或任意绝对路径；这一点为 DESIGN_DECISION。读取检查文件类型、64 KiB 边界、编码、热更新和读取异常。路径字段移除是明确的隐私兼容性变化；工具名称/参数保持原样。无额外诊断路径输出。

## C01—C03：工程覆盖

Windows Python 3.12.15 与 3.14.7 均执行 79 项测试；GitHub Windows/Ubuntu/macOS × Python 3.11–3.14 共 12 组合各 79 项通过（45957357861）。静态语法、有限 Ruff 严重错误集、依赖一致性、安全公告查询均执行，不将其描述为全面形式化证明。测试仍保留原根目录文件，新专项置于 unit/integration/security/stress/regression。第三方 Agent 客户端均待验证，不因缺少实机环境判定本轮失败。

## 证据与未覆盖项

最终矩阵见 TEST_MATRIX.md；实现、提交顺序、数据库保护见 FIX_REPORT.md；原始测试/覆盖率日志保留在忽略的 .release-audit/quality，公开的脱敏结果为 docs/evidence/audit-verification.json。未测试磁盘断电/磁盘满、真实生产迁移、SSH 部署、所有未知历史 Schema、恶意同机管理员的文件系统竞争。源日志整文件解压仍可能消耗较多内存，属于本地受信任日志规模限制，不提供敌对多租户保证。
