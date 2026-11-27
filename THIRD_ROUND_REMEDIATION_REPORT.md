# 第三轮复核、修复与回归报告

日期：2026-11-27。分支：`audit/round3-20261127`。本轮只处理源码、隔离测试和文档，不操作生产数据、不部署、不合并、不发布。

## 1. 执行摘要

- A09 原报告的单位错误 **NOT CONFIRMED**。固定 `zstandard==0.25.0` 的实际 C 后端按字节设置窗口，原 8 MiB 限制有效；没有采用会把预算缩成 8 KiB 的除法。新增边界与失败原因断言。
- A10 **VERIFIED**：真实 CLI 的错误字典原先退出 0；现在退出 1，保留 JSON。补齐参数、启动、旧写入、文件、数据库与意外异常；未知 Schema 版本保留专用错误码。
- A11 **VERIFIED**，范围为已确认的输入反射：调用者提供的路径、非法值与自定义字段名经 KBError 回显到 MCP/CLI。修复了这些路径，不声称发现了读取服务端未知私密路径的漏洞。
- 本机单用户源码候选：有条件通过。公开源码候选：有条件通过，正式发布尚待本轮远程 CI 与部署验收。多用户或公网部署：不通过。

## 2. 基线与保护

开始检查时，现有工作区位于 `audit/round2-20261127`，HEAD 为 `1543e9c4648635f30e761d130146c6e48bb72087`；与该远程分支一致。指定 main 基线为 `991ea4030061be8e8740e33629fae2a8114936b0`。拉取并比较后，两者文件树完全相同；main 已包含第二轮分支提交，差别是合并历史。

初始已修改、未跟踪、已暂存文件均为空；没有未纳入 main 的本地提交。确认干净后，在同一工作区创建 `audit/round3-20261127`，以 main 基线开始修改。未重建项目，未覆盖其他工作树或用户修改，无冲突。

代码结束 HEAD 为 `8b805a52168934474233c939c3a39f448826f4c8`（其完整哈希可由 `git rev-parse 8b805a5` 获取）；之后仅有本报告及相关文档/证据提交。完整交付 HEAD 用 `git log -1 --format=%H -- THIRD_ROUND_REMEDIATION_REPORT.md` 解析；避免把文档提交自己的循环哈希写作已知值。最终回复提供交付提交号。

依赖锁定仍是 `requirements.txt` 中 mcp 1.30.0、zstandard 0.25.0；未修改依赖或安装新工具。实际环境为 Windows、Python 3.14.7 / 3.12.15，zstandard 0.25.0，C 扩展后端，内置 Zstd 1.5.7。测试数据库均由临时目录构造；未连接真实学习数据库。

## 3. A09：先验证单位，而非照搬换算

上游 0.25.0 文档及 CFFI docstring 将 max_window_size 描述为 kibibytes；但是同版本 `c-ext/decompressor.c:23` 和 `zstandard/backend_cffi.py:4456` 都把数值原样传给 `ZSTD_DCtx_setMaxWindowSize`。下游 API 用窗口大小限制缓冲分配。源码 URL、SHA-256、关键片段和实际输出收录于 [窗口证据](docs/evidence/round3-window.json)。CFFI 只查源码，未动态执行。

用 compressobj、`write_content_size=0` 和指定 window_log 生成帧，再用 `get_frame_parameters(...).window_size` 读取真实窗口。每个独立探针压缩后仅 58 字节、解压后 49 字节，排除原始大小、输出大小及比率上限。先在原代码和固定版本环境执行，结果如下：

| 实际帧窗口 | max_window_size=8388608 | max_window_size=8192 |
|---|---|---|
| 4 KiB | 接受 | 接受 |
| 8 KiB | 接受 | 接受 |
| 16 KiB | 接受 | 拒绝 |
| 4 MiB | 接受 | 拒绝 |
| 8 MiB | 接受（包含等号） | 拒绝 |
| 16 MiB | 拒绝 | 拒绝 |
| 128 MiB | 拒绝 | 拒绝 |

拒绝均为 `ZstdError: Frame requires too much memory for decoding`。因此原报告所述放宽 1024 倍未复现；此外 8,388,608 KiB 应为 8 GiB，而不是 8 TiB。

原 test_window_budget 确实构造了 16 MiB 帧并触发窗口上限，但只断言 KBError，缺少上下边界与失败原因证据。现在参数化 4/8/16/128 MiB：校验实际帧头、充足预算对照成功、错误 cause 的类型与原因、合法帧完整同步、超限不发布归档/消息/游标，以及换成合法帧后可重试。除以 1024 的反向对照明确失败。

实现选择：保留 WINDOW_BYTES 及原传参，其他预算零变更；增加测试，不制造不存在的修复。依赖未来升级必须重跑该测试，不能把本次实测泛化到任意版本/后端。原指控为 NOT CONFIRMED，当前 8 MiB 限制的验证为 VERIFIED。

## 4. A10：真实 CLI 退出码

修复前新增子进程测试：9 failed / 7 passed。7 个失败来自普通业务错误及六个停用写接口退出 0；另 2 个为 argparse 和服务初始化失败没有 JSON stdout。原文件异常、未知工具、非法 JSON、成功调用等路径已经满足相应预期。

修复后只对明确 `dict` 且 `ok is False` 的结果返回 1；没有 ok 的成功形状仍为 0。参数解析失败映射 INVALID_INPUT；服务初始化的安全错误码转成 JSON，保留数据库、权限及 Schema 专用码。正常 main 返回不额外抛 SystemExit，兼容本地 runpy 包装器的成功输出转发。MCP 包装器的协议返回语义不变。

最终复核另发现启动错误白名单漏列 Schema 码：专项先失败 1 项，补齐 UNKNOWN_SCHEMA_VERSION/MIGRATION_CHECKSUM/SCHEMA_DRIFT 后通过。用临时 SQLite 的 user_version=99 实际验证，未改生产数据库。

| 情况 | 退出码 | 对外结果 |
|---|---:|---|
| 正常工具、无 ok 的历史成功形状 | 0 | 可解析 JSON |
| 不存在实体 | 1 | NOT_FOUND |
| 六个停用写接口 | 1 | LEGACY_WRITE_DISABLED |
| 未知工具、缺参数、坏 JSON | 1 | INVALID_INPUT |
| 缺参数文件 | 1 | SOURCE_UNAVAILABLE |
| 存储路径不能作为目录 | 1 | STORAGE_UNAVAILABLE |
| 未知数据库版本 | 1 | UNKNOWN_SCHEMA_VERSION |
| 注入意外 RuntimeError | 1 | INTERNAL_ERROR |

--help 按 argparse 约定为帮助文本、退出 0。verify 的完整性诊断结果保持历史结构，调用者仍应检查诊断字段；本轮只规定 call 的 ok 字典退出语义。

## 5. A11：已确认的反射链及脱敏范围

检查全部 KBError 构造点、统一错误边界、文件/归档/同步、启动和 CLI；系统异常原已有安全映射。确认两条实际链：

1. `get_topic_context(topic_id)` → Context.version → NOT_FOUND 动态 ID → error_response → MCP/CLI 原样回显。
2. `update_learning(changes)` → validate_changes → jsonschema 的 e.message（包含非法值）、自定义字段路径 → VALIDATION_ERROR.message/details → MCP/CLI 原样回显。

测试只使用合成 Windows/POSIX 路径。修复前 4 个真实 CLI+MCP 用例均失败，证明两种输入经两个出口返回；另 1 项暴露 KBError 没有结构化诊断日志。这里是调用者输入反射，未发现无需已知输入即可窃取服务端路径的链。

统一边界对 NOT_FOUND、EVIDENCE_NOT_FOUND、SOURCE_AMBIGUOUS 使用稳定消息；VALIDATION_ERROR 用稳定摘要并保留 details。校验生产端只输出 Schema 拥有的字段名、数组下标、预期类型/约束和错误类别；自定义字段用 <field> 替代，非法值不进入文本。保留普通业务消息、实体版本信息和合法错误详情，不做全局删除或宽泛路径正则替换。

内部日志记录 code/type；系统错误还保留 errno/sqlite_errorcode，不记录值、路径、异常文本或 traceback。测试还在真实 CLI/MCP 服务中注入 Windows PermissionError、POSIX FileNotFoundError、SQLite OperationalError、RuntimeError，核验对外 JSON 和各自 stderr；这些是注入测试，不冒充真实磁盘故障。

限制：不是通用任意字符串脱敏器；未来新增动态 KBError 或 details 生产者必须继续审查。标准路径仍可诊断，自定义字段的精确名称不再公开，同位置未知字段可能合并。

## 6. 回归、命令与证据

命令中的 python 指已锁定依赖的测试解释器；未使用生产启动配置。完整本地命令、stdout/stderr 和退出码保存在忽略目录 `.release-audit/round3/`，全量质量门禁日志在 `.release-audit/quality/`；公开摘要见 [结果](docs/evidence/round3-results.json)。

| 检查 | 命令 | 结果 |
|---|---|---|
| 窗口与同步预算 | `python -m pytest -q tests/security/test_round2_sync_limits.py` | 19 passed，exit 0 |
| CLI 与旧接口 | `python -m pytest -q tests/security/test_round3_cli.py tests/security/test_round2_legacy.py` | 17 passed，exit 0 |
| 脱敏专项 | `python -m pytest -q tests/security/test_round3_errors.py tests/security/test_round2_errors.py` | 22 passed，exit 0 |
| Python 3.14 全量及静态/依赖 | `python scripts/quality_gate.py --dependencies` | 176 passed / 0 failed / 0 skipped，59.28 秒，全部 exit 0 |
| Python 3.12 全量 | `python -m pytest -q` | 176 passed / 0 failed / 0 skipped，48.61 秒，exit 0 |
| 资源子进程 | `python scripts/round2_resource_probe.py --output .release-audit/round3-resources.json` | 10/10，exit 0 |
| 编译 | `python -m compileall -q -x "[\\/]\." .` | exit 0 |

质量门禁包括 Ruff E9/F63/F7/F82、pytest（ResourceWarning 作为错误）、coverage/JUnit、pip check、pip-audit。未配置独立类型检查器、全项目格式门禁或 SAST；本轮没有引入新依赖，不把 Ruff 的有限检查称为完整静态安全审计。Git diff --check 通过；不是代码风格格式化检查。一次专项命令误用了不存在的 tests/test_contracts.py，未执行任何测试；之后使用实际 tests/test_release_contracts.py 所在全量套件完成覆盖，此次命令错误不记作通过。

每例 pytest 后，所有临时 *.sqlite3 执行 `PRAGMA integrity_check` 返回 ok、`PRAGMA foreign_key_check` 无行；资源子进程也逐例核验，详见 [资源数据](docs/evidence/round3-resources.json)。原强制进程退出、恢复、归档幂等、MCP stdio/回环 HTTP、迁移、偏好和规则测试保留。未跳过失败测试。

| 资源限制 | 实际执行覆盖 |
|---|---|
| 原始文件 16 MiB | read_bytes 原始/压缩输入；source 及 raw_file 探针 |
| 窗口 8 MiB | 4/8/16/128 MiB 帧、直接 API 对照和完整 sync_file |
| 输出 32 MiB | decoded 限额和 33 MiB decompressed 子进程样本 |
| 压缩比 200 + 1 MiB 宽限 | ratio 测试与 2 MiB 高压缩样本 |
| 事件 20000 | parse 超限、20001 事件资源样本 |
| JSON 深度 32 / 节点 250000 | depth 深嵌套 / nodes 缩小预算穿过实际解析路径；不是 250000 节点边界压力实测 |
| 单条消息 256 KiB | UTF-8 多字节、超限和精确合法边界 |
| 请求总字节 2 MiB | total、escaped_total、精确序列化边界和 normalized_total 探针 |
| 消息数 128 | 128 合法、129 拒绝及 normalized_count 探针 |

GitHub Actions：本轮 **NOT VERIFIED**，未推送当前分支，未触发本轮工作流。第二轮历史运行不计入本轮；三平台四 Python 的工作流配置未变。其他客户端实机仍为 NOT VERIFIED。

## 7. A01–A11 最新总表

| 编号 | 状态 | 本轮证据与边界 |
|---|---|---|
| A01 | VERIFIED | 六个旧写入本体/CLI 拒绝、MCP 不暴露，新写入和读取全量回归 |
| A02 | VERIFIED | 系统异常的统一安全映射与内部日志；动态业务回显另计 A11 |
| A03 | VERIFIED | 规范化输入 Schema/UTF-8/时间戳/数量与无部分写入回归 |
| A04 | PARTIAL | 明确预算及样本通过；没有补齐任意并发/进程级内存、敌对环境等完整保证，不提升总体状态 |
| A05 | DESIGN_DECISION | 保留用户要求的完整固定规则；不声称真实客户端 token 费用优化 |
| A06 | DESIGN_DECISION | core-v1 冻结；现有迁移回归通过，未来迁移设计不等于实现 |
| A07 | VERIFIED | 逻辑拒绝无新归档、重试/失败回滚回归；文件系统与 SQLite 仍无跨系统原子提交 |
| A08 | VERIFIED | 首次同步 canonical 规范化修复全量回归 |
| A09 | NOT CONFIRMED | 单位错误未复现；实际字节单位与 8 MiB 边界已验证 |
| A10 | VERIFIED | 真实 CLI 成功/失败状态、JSON 与 Schema 错误码 |
| A11 | VERIFIED | 已确认的输入反射链修复；真实 MCP/CLI 与日志回归 |

## 8. 剩余风险与发布结论

本机单用户使用：**有条件通过**源码候选验收。正式切换本机前仍需备份、在副本验证并验收当前候选；本轮没有升级生产。此前课程验收仅证明旧部署，不能充作本轮实机证据。

公开发布：**有条件通过**作为披露限制的源码候选；本轮远程 CI、目标环境部署尚未验证，不宣称已具备正式 Release 全部条件。

多用户或公网部署：**不通过**。缺少身份认证、多租户隔离和用户级配额；回环 HTTP 与输入预算不能替代安全服务边界。

保留 A07 的文件发布后、SQLite 提交前的崩溃窗口：可能留下未登记的内容寻址文件，重试核验复用；未引入自动删除。首次聊天注册与同步分两步，失败可留下注册记录。网络文件系统、磁盘满/断电完整矩阵、敌对管理员、任意并发内存峰值、CFFI 动态行为、其他 Agent 实机均未完成验证。固定规则不保证外部模型一定遵循，也没有新增 GUI 验收。

## 9. Git 变更记录

| 提交 | 文件/目的 |
|---|---|
| 18b6daa | test_round2_sync_limits.py：A09 真正的窗口边界、原因、重试与原子性证据 |
| 46b1241 | cli.py、test_round3_cli.py、test_round2_legacy.py：A10 退出码和 JSON |
| f30208b | errors.py、contracts.py、test_round3_errors.py：A11 脱敏和诊断 |
| 8b805a5 | cli.py、test_round3_cli.py：A10 启动 Schema 码补充与实际 SQLite 回归 |
| 本文档提交 | 双语 README、CHANGELOG、RELEASE_READINESS、第二轮状态勘误、预算/CLI 说明、第三轮报告与公开证据 |

没有修改 schema.sql、依赖、固定课程规则、个人偏好或生产配置。未强推、未发布正式版本；全部目标修改分项提交，文档提交后检查工作区干净。忽略目录保存测试日志，不属于待提交业务改动。
