# 测试矩阵

日期：2026-11-27。所有数据均为临时目录内合成数据。最终 Windows Python 3.14.7 与 3.12.15 各 **75 passed，0 failed，0 skipped**。原始基线 16/16 通过；新 A 组首次 12 failed / 5 passed 是修复前缺陷证据，已全部转绿。后续新发现均先保留失败复现，再修复。

| 专项 | 实际执行与结论 | 证据 |
|---|---|---|
| A01 默认/远程绑定 | PASS：本地 HTTP 读写成功；三个非回环地址入口拒绝（拦截真实监听） | test_http_policy.py、test_mcp_http.py |
| A02 归属 | PASS：错专题拒绝，同专题跨聊天成功 | test_audit_boundaries.py |
| A03 来源范围 | PASS：隐式跨专题/伪造声明拒绝，显式来源和跨专题关系允许 | test_audit_boundaries.py |
| A04 消息完整性 | PASS：正文、角色、时间戳、顺序变化及删除/截断拒绝 | test_sync_integrity.py |
| A04 尾行/压缩 | PASS：半截尾行、截断 Zstandard 帧拒绝，完整及多帧解压成功 | test_sync_integrity.py |
| A04 中断恢复 | PASS：异常注入、真实子进程 os._exit、归档提交后提取中断，重启幂等恢复 | test_sync_integrity.py |
| A04 无变化重放 | PASS：归档丢失可从同 hash 原文恢复；损坏拒绝且保留现场 | test_sync_integrity.py |
| A05 撤销 | PASS：非 link/撤销链/空目标拒绝，重复目标约束与合法 link 撤销 | test_concept_retractions.py |
| A06/A07 归档接口 | PASS：两个入口路径逃逸拒绝，非文本消息拒绝，正常重放成功 | test_normalized_archive.py、test_sync_integrity.py |
| B01 幂等/版本/事务 | PASS：相同 request 重放、不同 payload 冲突、旧版本拒绝、中途失败全回滚 | test_release_contracts.py |
| B01 并发 | PASS：线程写入及 6 子进程相同请求，WAL/FK/busy_timeout | test_database.py、test_concurrency.py |
| B01 回滚/备份竞争 | PASS：回滚冲突、最新版本回滚、不覆盖新出现的备份目标 | test_rollback_conflict.py、test_backup_collision.py |
| B02 初始化/迁移 | PASS：空库、base-only、完整旧库副本、重复启动、失败回滚、checksum/未知版本/漂移拒绝 | test_migration_recovery.py |
| B03 缓存 | PASS：LRU、TTL、容量、深拷贝、修改/删除知识或消息失效、Schema 篡改拒绝 | test_cache_notifications.py |
| B03 恢复/通知 | PASS：恢复轮换 epoch，游标检查与通知读取 | test_restore_epoch.py、test_cache_notifications.py |
| B04 搜索 | PASS：5001 知识/2001 消息披露 incomplete、专题筛选、批量分页隔离、恢复及查询版本检查 | test_search_coverage.py |
| B05 偏好 | PASS：64 KiB 边界、UTF-8、同 mtime 替换、脱敏及权限错误 | test_preferences*.py、test_release_contracts.py |
| C01 后台锁 | PASS（Windows）：另一进程排他，退出后释放 | test_worker_lock.py |
| MCP stdio | PASS，Python SDK 模拟：初始化、21 工具、Schema、偏好、登记、归档、知识更新/读取 | test_mcp_stdio.py |
| MCP HTTP | PASS，Python SDK 模拟：初始化、发现、偏好、登记、归档、更新、搜索、幂等、回滚 | test_mcp_http.py |
| 数据库完整性 | PASS：每个测试结束逐个临时 *.sqlite3 执行 integrity_check、foreign_key_check | tests/conftest.py |
| 静态检查 | PASS：Ruff E9/F63/F7/F82；41 个 Python 文件 AST 解析；git diff --check | quality gate + 审计记录 |
| 覆盖率 | 1303/1748 行，74.54%；不是分支覆盖率，未覆盖旧工具等路径 | coverage.xml（忽略文件） |
| 依赖检查 | PASS：pip check；67 个环境包 pip-audit 未发现已知漏洞 | .release-audit/quality/dependencies.json |
| 发布内容扫描 | 已跟踪内容规则扫描无命中；不等同于所有 Git 历史/未知秘密都已审计 | scripts/release_audit.py 的 findings 复用 |
| 性能对照 | PASS：九种结果哈希一致；输入输出 Token、SQL、延迟、命中率记录 | audit-performance-before/after.json |

## 执行环境边界

| 环境/能力 | 状态 |
|---|---|
| Windows + Python 3.12.15 / 3.14.7 | 已实测，每套 75 项通过 |
| Windows + Python 3.11 / 3.13 | NOT VERIFIED |
| Linux/macOS + Python 3.11–3.14 | NOT VERIFIED；CI 已配置，未触发 |
| 真实第三方 Agent 客户端 | NOT VERIFIED；按用户环境限制不安装 |
| 本轮真实 Codex 客户端业务调用 | NOT VERIFIED；不继承旧报告作为本轮证据 |
| SSH 远程认证隧道/TLS 网关 | NOT VERIFIED；非回环直连不支持 |
| 私人生产库、生产归档和生产迁移 | NOT VERIFIED；未访问或修改 |
| 断电、硬盘满、极大压缩炸弹、敌对本机管理员 | NOT VERIFIED |

## 重复执行

先安装 requirements-dev.txt 和 requirements-quality.txt，再运行：

```text
python scripts/quality_gate.py --dependencies
```

结果和日志写入忽略目录 .release-audit/quality。缺少依赖、测试失败或公告服务失败均产生非零退出码，不跳过失败。GitHub 工作流运行相同测试和静态检查，并保存 JUnit/覆盖率/依赖结果；未运行的 CI 不记为通过。
