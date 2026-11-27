# 修复与验收报告

本轮已完成本地独立复核、隔离复现、分组修复、回归和性能对照。Windows 两套 Python 各 75 项通过；生产数据未访问、未迁移。原 main 保持 42f593752c295bb2ef5d647a40c00bead19dde94，GitHub main 在开始及结束均核对为同一提交。工作位于独立 audit/security-review-20261127 分支；未 Push、合并、Release 或发布 PyPI。

## 阶段 1：基线

核实远程、分支、HEAD、干净工作区、忽略材料、运行环境。Git 直连失败后通过已授权 GitHub 连接器验证 HEAD，没有绕过权限。原工作区数据目录仅 .gitkeep。产物 AUDIT_BASELINE.md；此阶段没有修改业务源码或运行生产数据库检查。

## 阶段 2、3：独立复现和设计

原 16 项测试通过，但新增 A 组 17 项中 12 个安全期望断言失败。确认 A01—A05 及路径逃逸 A06；正文/角色修改、截断拒绝和幂等保持正常。同专题跨聊天和合理知识关系保留。先提交 ab93c39 的测试/审计记录，再实施修复；AUDIT_FINDINGS.md 和 FIX_PLAN.md 保存初始证据与决策。

## 阶段 4：安全与完整性修复

- server.py：非回环 HTTP 拒绝；补充消息结构验证；通知健康错误保持明确错误码。
- context.py、contracts.py：事务内检查聊天归属，显式跨专题证据来源，保留同专题跨聊天及关系引用；工具 Schema 展示新增的可选来源元数据。
- sync.py、archive_io.py：完整解析和消息字段校验；安全归档路径；先完整落盘再以不覆盖方式发布；同样覆盖补充归档入口。
- unchanged 重放仍核对物理归档；丢失可用同 hash 原文恢复，损坏则明确拒绝，不静默覆盖。
- concept_reader.py：投影前拒绝非法撤销，现有概念和关联事件不改写。

35 项阶段回归先通过；后续又补充真实进程中断、提取恢复及补充导入绕过测试。失败会回滚数据库事务；归档文件可能留下未引用的完整证据或 .pending 临时文件，保留而不删除历史。注册、归档提交与候选提取是可恢复的独立步骤，不宣称文件系统和 SQLite 具有同一个物理事务。

## 阶段 5：B、C 专项

- kb.py、migrations.py：整个已有 Schema 组合及通知安装原子提交；新增 schema_migrations checksum；未知版本和结构拒绝迁移。含合成数据的旧库副本各原有表升级前后逐行相等。
- kb.py、cli.py：备份/恢复先生成完整副本，再原子不覆盖发布；恢复轮换 R3 epoch，防止旧缓存/通知游标继续有效。
- search_engine.py：分页版本包含恢复 epoch。5000/2000 条限制保留，真实超限测试检查 incomplete；不承诺全库公平覆盖。
- preferences.py：隐藏路径，64 KiB 有界新读取，避免同时间戳替换继续返回旧内容，文件异常脱敏。
- 测试入口使用 sys.executable；后台锁按平台选择 msvcrt/fcntl；Windows 排他测试通过。
- 新增 tests/unit、integration、security、stress、regression，以及三系统四版本 CI、覆盖率、依赖公告和严重静态错误检查。

所有已确认缺陷都有修复与回归。原事务/通知核心未复现的问题保留实现；未实施无收益的数据库大重构。Linux/macOS、未运行的 Python 版本及真实第三方客户端继续待验证。

## 阶段 6：性能对照

只对同一读取快照内重复消息存在性查询去重，不删除证据、版本或错误字段。合成数据：500 条知识、200 个进度条目、1 条概念关联。

| 指标 | 修改前 | 修改后 |
|---|---:|---:|
| 批量进度检索请求 | 10 | 10 |
| SQL 查询总数 | 2070 | 80 |
| 请求参数 Token | 110 | 110 |
| 返回 Token | 16300 | 16300 |
| 中位延迟 ms | 562.919 | 583.068 |

查询数下降约 96.1%，但本轮延迟未改善，不宣传稳定提速。九种结果哈希完全相同。现有概念缓存 20 次请求 19 次命中，查询 280→170；两次测量延迟有波动，缓存收益只证实减少 SQL。现有 L1 摘要 122 Token/次、完整进度 869 Token/次，体现按需读取；这是已有功能的测量，不冒充新增 Token 优化。全部 Token 为 cl100k_base 对序列化参数/结果的计数，不是实际模型账单，未包含系统提示和工具 Schema。

复现：安装 tiktoken 后运行 python scripts/benchmark_audit.py --label current --output .release-audit/performance.json。对照结果位于 docs/evidence/audit-performance-before.json 与 audit-performance-after.json。

## 阶段 7：最终验收

Python 3.14.7：75 passed / 0 failed / 0 skipped；Python 3.12.15 同样通过。最终覆盖率 74.54%，资源警告作为错误运行，无未解释失败。静态、依赖一致性、67 包安全公告查询通过。每个测试的临时数据库均检查完整性与外键。发布准备和未验证范围见 RELEASE_READINESS.md，详细矩阵见 TEST_MATRIX.md。

兼容性变化均明确披露：非回环 HTTP 启动拒绝；错误专题更新拒绝；跨专题证据需要来源声明；偏好结果省略 path；恢复后的旧搜索游标需重新开始；无法识别的数据库 Schema 停止而非强行覆盖。原 MCP 工具名称和顶层参数保持兼容，原三份 SQL 与业务记录未替换。
