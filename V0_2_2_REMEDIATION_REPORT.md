# v0.2.2 修复与发布候选验证报告

日期：2026-11-28。范围：受信任的本机单用户。本文与历史审计文档分开，历史结论保持原样。

## 1. 执行摘要

A12、A13、A14 已修复并通过本地专项及全量回归；A15 当前状态文档已更新。建立独立分支 `release-candidate/v0.2.2`。本地干净 Python 3.14.7 环境 221 passed，0 failed，0 skipped。远程 Actions `46155676605` 的 13 个作业与全部步骤成功，12 组实机 runner 各 221 项测试、0 failed/error/skipped；已逐项检查上传产物。发布建议 **CONDITIONALLY_READY**，只限下述受信任本机单用户边界。A04 保持 **PARTIAL**。

本任务只形成候选；不合并 main、不创建正式 Release/Tag、不发布 PyPI，也不升级或修改本机生产数据库。

## 2. 基线与工作区保护

- 实时核实最新正式 Release：v0.2.1（非草稿、非预发布），2026-11-28 发布。
- 正式 commit：`df6c3401d5829cbf99b2734120b9440397acc633`；远程 main、正式 tag 的解引用 commit 与之相同。核实时没有更新的 Release 或 v0.2.2 分支。
- 原本地 main 工作区干净、落后远程 49 commits；从正式 tag 新建候选分支，未移动本地 main 引用。原 stage4 工作区及其他历史 worktree 保持原分支。
- 修复按问题分开提交。已完整远程验证的最新实现 commit 为 `d45773d29a70a2c4fc7c13dbdce9c516b471202a`（含分页 JSON 和正则资源边界补充修复）。本报告及 CI 证据随后以独立文档提交补齐，并补强原生权限测试（断言写权限位真实改变），最终分支 HEAD 用 `git rev-parse release-candidate/v0.2.2` 查询；文档及验收断言补强不改变运行实现或正式 tag，提交后再次核验该 HEAD 的完整 CI。
- 开始前检查当前目录、Git 根、分支/HEAD、暂存/未暂存/未跟踪文件、远程分支和 tags；未发现用户未提交改动。当前协作树仅本 agent。检测到的 Python 服务来自独立安装目录，未操作其进程或数据；进程清单不能证明任意外部编辑器永不写入，提交前仍复核 diff。
- 没有 reset --hard、clean、强推、覆盖分支或删除非本任务文件。新环境与所有测试数据在忽略目录/临时目录中，未进入候选发布内容。

## 3. A14：公开 MCP 响应边界

**状态：VERIFIED（本地及三平台真实 MCP/回归）。** 根因是成功路径直接序列化数据库记录，而旧错误脱敏不能覆盖历史 JSON、正文和框架参数验证。真实 stdio 最小测试在修复前 2 failed：偏好正文带出路径，以及分页拼接还原路径。

修改 `public_response.py`、`server.py`、`context.py`：

- 在所有已注册工具共享的输出边界生成对外副本；移除 cwd/source_path 等定位字段，为来源生成与 worker 一致的不透明 source_id。
- 递归处理结构、JSON 字符串中的 JSON、Windows/UNC/POSIX/file URI 风格的路径文本；原始数据库及归档不改写。
- 单条知识/消息（包括作为文本读取的嵌套 JSON）先结构脱敏再切片，offset/total_chars 针对脱敏后的文本，避免拆分绕过。原始证据哈希仍指向内部原文，不能拿遮蔽后的文本重新计算原文哈希。
- 框架参数验证可能在业务装饰器之前失败，因此单独替换其异常文本；保留 MCP `isError` 语义。Schema details.path 是字段位置，不作为磁盘路径字段删除。
- 普通和 full=true 历史查询均经过相同边界。可信本地 CLI/数据库诊断可继续定位原始文件。

证据：`tests/security/test_mcp_path_boundary.py` 使用真实 ClientSession/stdio，对工具发现集合做完整性断言，实际调用 17 个公开读取工具；覆盖健康状态、完整/普通/分页历史、偏好、上下文、概念读取、错误响应和逐段拼接。随后核实内部 cwd/source_path、发现候选与审计记录仍存在。既有 stdio/HTTP 与 legacy 工具拒绝测试继续通过。

取舍：路径样式正文可能被保守遮蔽，分页返回不再保证与原始归档逐字相同；这不是通用秘密扫描器，不承诺识别任意编码/隐写内容。原生客户端实际显示与大规模历史总内存不由本测试证明。

## 4. A12：首次解压阶段帧数量限制

**状态：VERIFIED（本地及三平台真实 MCP/回归）。** 旧代码先 stream_reader 完整解压，再用 decompressobj 第二次解压统计帧数。修复前计数测试 2 failed：第一次解码器直接收到了全部 10,000 帧。

修改 `zstd_frames.py`、`sync.py`：依据 Zstandard 帧结构先检查一帧的数量、头、块长度和完整结束位置，再把单个帧交给固定版本 zstandard==0.25.0 的有界 stream_reader。达到帧预算时，不再检查或解压下一帧。包括 skippable 帧在内均计数。块内容/字典/校验和由真实解码器校验；移除 decompressobj 二次解压。

输入 16 MiB、输出 32 MiB、窗口 8 MiB、200 倍比例/1 MiB allowance、20,000 帧/事件及 64 KiB 读取预算保留。未修改 zstandard 版本；窗口专项仍实测该版本 API，未按其他版本文档猜测单位。

证据：24 项新测试，覆盖单帧、多帧、等于/超过上限、10,000 空/微小帧、skippable、输出超限、非法/混合/逐字节截断、损坏校验和、真实压缩器产生的不同内容长度与有/无 content-size 帧。计数包装器验证上限 3 时恰好只有 3 次解码器调用，禁止第二次 decompressobj；不是仅检查最终错误码。既有窗口 4/8 MiB 接受、16/128 MiB 拒绝等专项继续通过。

取舍：新增帧边界解析器不替代解码器校验；格式变更或升级依赖时必须重跑合法编码、截断和资源专项。

## 5. A13：跨平台发现边界

**状态：VERIFIED（Windows、Linux、macOS 真实 runner，加明确标注的模拟边界测试）。** 根因是把 POSIX metadata-change time 当作创建时间。修复前模拟 POSIX ctime 更新测试确实错误触发旧文件导入；Windows 原生测试不被冒充为 POSIX 复现。

修改 `discovery.py`、`sync.py` 及 `.gitignore`：

- 初始完整扫描持久化来源目录身份、边界时间及文件路径/设备-inode 哈希；原子、不可覆盖地发布快照。扫描错误不生成可信的部分清单。
- 初始已有路径或文件身份继续排除，metadata 更改、移动/重命名不能重新成为新聊天。
- 可用且有限、有效的 st_birthtime 须晚于边界且不在未来；不退回 ctime/mtime。
- 没有 st_birthtime 时，仅把快照后新出现的稳定身份加入待确认列表，不读取/导入正文，要求显式登记。这样不会把外部移入的旧文件当作新创建聊天。
- 已登记聊天优先；排除文件仍计入初始快照。缓存包含已登记状态，人工登记后不会被旧缓存跳过；同步成功清理对应待确认候选。
- 匹配源文件最多 50,000 个，快照最多 8 MiB。丢失/不可靠身份、损坏快照、根身份变化保守拒绝；允许人工登记恢复。

证据：8 项新回归，外加原有排除规则/持久 cutoff 测试。原生测试真的创建旧文件、修改 chmod/utime、创建新文件、重复扫描和重建 worker 缓存；模拟测试单独命名，涵盖无 birthtime、异常时间、身份缺失、旧 inode 更名、扫描权限错误、人工登记与缓存衔接。Linux 和 Windows Python 3.11 的无 birthtime 路径按设计进入确认队列；不宣传为自动推断可靠创建时间。

升级取舍：首次启用新边界时，已有未知聊天需显式登记，不自动补入。快照是本地配置，不改变数据库 schema/checksum；应纳入备份。不要删除快照来绕过保护。

## 6. A15：发布状态文档

**状态：已更新。** README.md / README.en.md 一致说明正式版本 v0.2.1 已发布、main/tag/CI 状态及 v0.2.2 候选身份。RELEASE_READINESS.md 以当前状态开头，将旧阶段结论清楚归为历史记录；未改写历史审计报告以抹去风险。同步、输入预算、CHANGELOG 同步说明本次行为变化。

v0.2.1 正式基线 CI 为 Actions `46150934512`：12 个 Windows/Ubuntu/macOS × Python 3.11–3.14 测试 job 加 1 个依赖审计均成功；该历史运行不替代 v0.2.2 的 CI。

## 7. A04 重新评估与资源证据

最终状态维持 **PARTIAL**。A12 消除了先无限制穿过所有帧、再检查帧数的顺序缺陷，并移除了第二次解压。它与源字节、解压输出/比例、窗口、帧/事件上限组合有效。首次清单也有数量/字节限制，但这不构成整个进程或所有并发请求的资源上界。

仍未实现：进程内存硬限制、聚合并发配额、整体任务超时、磁盘累计配额、被强制终止后的临时文件清理保证。未知文件树遍历、数据库历史累计、公开健康检查记录总量、并发任务与缓存仍可能消耗较多资源。新增脱敏扫描与发现快照也有分配开销，不作“零增长”承诺。

可复现脚本 `scripts/v022_resource_probe.py` 与原有 `scripts/round2_resource_probe.py` 均使用合成输入和独立临时数据库。完整规模、耗时、OS 峰值 RSS、返回状态、完整性、残留文件检查见 `docs/evidence/v022-resources-windows.json` 与 `docs/evidence/v022-existing-resources-windows.json`。样本包括 200,000 个空帧、200,000 微小帧、33 MiB 解压输出、约 15 MB 同步输入、5,000 文件连续 5 次扫描、5,000 条真实 stdio MCP 历史分页读取，以及 500,000 个连续反斜杠的脱敏扫描。

RSS 是整个探针子进程的峰值，含导入和构造输入；历史读取另启 MCP 服务子进程，其 RSS 没有计入，不是两进程聚合测量。正常退出后临时目录/发布暂存文件清理已检查；未测试强制杀进程清理。计时不是跨设备性能保证。旧 10 项资源探针同样通过。

## 8. 本地验证与失败分析

环境：Windows，Python 3.14.7，mcp 1.30.0，zstandard 0.25.0，pytest 9.2.0，ruff 0.17.6，pip-audit 2.10.1。从 requirements-dev.txt / requirements-quality.txt 新建独立虚拟环境安装成功；运行依赖未变更。

| 验证 | 结果 |
|---|---|
| A12/A13/A14 先复现再修复 | 明确红/绿证据，如上 |
| 既有安全与回归目录 | 中间版本 150 passed；新增边界纳入最终全量 |
| 最终全量 pytest + ResourceWarning as error | 221 passed，0 failed，0 skipped |
| Ruff E9,F63,F7,F82 / compileall | 通过 |
| pip check / pip-audit | 通过；本次审计未报告已知漏洞 |
| SQLite integrity_check / foreign_key_check | 各测试隔离 DB fixture 和资源/升级探针均通过 |
| 原有资源探针 / 新资源探针 | 10 / 7 个场景通过 |
| 实际 v0.2.1 升级、CLI、备份恢复 | 通过，见 v022-upgrade-windows.json |
| 真实 MCP stdio + 回环 HTTP | 通过；17 公开读取、分页、嵌套 JSON、错误路径和分隔符噪声专项通过 |
| GitHub Actions 实现候选 d45773d | 13/13 job、全部 step 成功；12 组各 221 tests，0 failed/error/skipped |

命令（在候选仓库、独立环境执行）：

```text
python -m pytest tests/security/test_zstd_frame_gate.py -q
python -m pytest tests/regression/test_discovery_boundary.py -q
python -m pytest tests/security/test_mcp_path_boundary.py -q
python -m pytest -q -W error::ResourceWarning --junitxml=test-results.xml
python -m ruff check --select E9,F63,F7,F82 .
python -m compileall -q -x "[\\/]\." .
python -m pip check
python -m pip_audit --progress-spinner off --format json
python scripts/round2_resource_probe.py --output resource-probe.json
python scripts/v022_resource_probe.py --output v022-resource-probe.json
python scripts/v022_upgrade_smoke.py --output v022-upgrade-smoke.json
```

升级冒烟从已核实的实际 v0.2.1 tag 导出代码，创建有合成聊天/消息/归档的临时库，再用候选打开；逐表比较升级前后数据、验证归档哈希及 Schema，不复制生产数据。支持新建空库、备份、恢复与失败退出码。

失败均已分析：初次全量 1 failed/204 passed 是脱敏包装改变 framework isError 语义，修复后恢复断言；早期裸 UNC 正则误遮蔽规则里的双反斜杠，收紧匹配并保留规则一致性测试；资源脚本首次引用了错误列名 last_seq，改为实际 line_count 后重跑。追加复核复现了嵌套 JSON 分页遗留字段，已移到分页前处理；同时发现初版路径正则对连续反斜杠存在二次回溯，8,000 字符约 0.47 秒。收紧路径起始匹配后，500,000 字符约 0.02 秒，并加入独立子进程超时回归与资源探针。未删除测试、降低断言或跳过失败项。

## 9. 跨平台与远程 CI

实际实现提交 `d45773d29a70a2c4fc7c13dbdce9c516b471202a`，运行 **46155676605**。13 个 job 全部成功，0 skipped job，所有 step 成功。已下载全部 13 份 artifact，解析 JUnit 并检查关键 testcase 确实存在且无跳过；并非只看总体绿色状态。摘要与逐平台资源原始数字见 [CI 证据](docs/evidence/v022-ci.json)。

| 系统 | 实际 Python 版本 | 实际验证 |
|---|---|---|
| Windows | 3.11.9 / 3.12.10 / 3.13.17 / 3.14.10 | 每组 221 passed，0 failed/error/skipped；原生文件 metadata/新建/重启测试、实际 stdio/HTTP、17 资源场景、v0.2.1 升级冒烟 |
| Linux (Ubuntu) | 3.11.18 / 3.12.16 / 3.13.18 / 3.14.10 | 同上，真实 runner；无 birthtime 时走待确认与显式登记路径 |
| macOS | 3.11.9 / 3.12.10 / 3.13.17 / 3.14.10 | 同上，真实 runner；birthtime 校验与首次快照 |

本地 Windows 3.14.7 的结果单独保留。monkeypatch 模拟用例并未冒充真实跨平台测试。矩阵总计 2,652 次 pytest 用例执行；dependency job 审计 62 个环境依赖，0 已知漏洞。原生系统/版本来自上传 JSON，与 workflow matrix 一一核对。尚未验证其他厂商真实客户端、生产课程生成和极端存储故障，不因 CI 全绿扩大这些结论。

CI 每组执行 pytest（含 A12 调用计数、A13 原生和模拟测试、A14 实际 MCP 与分页/资源用例）、静态检查、原有 10 场景资源探针、新 7 场景探针，以及从实际 v0.2.1 tag 导出的升级脚本，均有上传产物。检查未发现关键测试被 CI 排除。后续文档/验收断言补强提交的 HEAD 检查仍需成功；其运行记录可在候选分支 Actions 下按精确 SHA 查询。

## 10. 遗留风险、发布建议与操作边界

发布建议为 **CONDITIONALLY_READY**。A12/A13/A14/A15 与候选回归门槛已通过；条件是只支持受信任本机单用户，接受以下公开限制，安装前按文档备份并进行个人环境验收。此结论不是合并/正式发布授权。

- A04 五类资源保护仍未实现；非公网多租户服务，无认证/隔离/每用户配额。
- 文件系统与 SQLite 无跨系统原子提交；崩溃可留孤立内容寻址文件，重试可复用。登记与同步仍为两个持久步骤。
- hardlink/网络盘、断电/磁盘满、敌对管理员、强杀后清理等全场景未验证。
- v0.2.2 未升级本机安装、未进行真实课程生成验收；本次真实 MCP 指协议级子进程调用，不是新版本用户课程验收。
- Claude/Cursor/VS Code/Gemini 等真实客户端未验证，协议测试不能替代；实际总 token 显著下降未证明。
- 路径文本可能保守遮蔽，出生时间缺失时需人工登记，这是明确兼容性取舍。

操作边界：未修改 main 引用、未合并、未创建正式 Release/Tag、未发布 PyPI、未修改生产数据库或真实聊天/归档。所有修复、文档和公开合成证据提交至独立候选分支；忽略目录的本地测试日志/虚拟环境不作为发布内容。提交前审查 diff 与密钥/私人路径模式，未包含真实配置、数据库或个人资料；仅保留明确的合成测试路径与通用安装示例。最终交付时再次核验 git status、远程 main 和正式 tag。
