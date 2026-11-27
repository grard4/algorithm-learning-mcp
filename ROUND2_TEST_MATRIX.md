# 第二轮测试矩阵

基线：0afc5b1cf6d57f40a092ea659508e8f06153de69；最终业务提交：9304295。全部使用临时合成数据；旧报告16/79/88项及旧CI不能代替本轮结果。

| 环境/阶段 | 结果 | 证据 |
|---|---|---|
| 修复前最小复现 | 9 failed（符合安全期望、暴露原缺陷） | tests/security/test_round2_reproduction.py；原始输出留本地 |
| A01专项 | 14 passed，11 deselected | test_round2_legacy.py、test_audit_boundaries.py及复现子集 |
| A02专项 | 12 passed，8 deselected；后增启动/同步日志测试进入最终全量 | test_round2_errors.py |
| A03/规范化A07 | 32 passed，1 deselected；新增重放恢复进入最终全量 | test_round2_normalized.py、test_normalized_archive.py、stdio/HTTP |
| A04/同步A07 | 初35项通过，后42项补充专项通过；最终相关50项通过 | test_round2_sync_limits.py、test_sync_integrity.py、归档/错误专项 |
| 当前迁移 | 5 passed | test_migration_recovery.py |
| Windows Python3.14.7 | 154 passed / 0 failed / 0 skipped，27.56秒 | 本地质量门禁、JUnit、coverage.xml |
| Windows Python3.12.15 | 154 passed / 0 failed / 0 skipped，22.39秒 | 本地JUnit |
| 静态/依赖 | Ruff E9/F63/F7/F82、pip check、pip-audit通过 | .release-audit/quality（忽略） |
| 资源子进程 | 10/10预期结果；2合法接受、8超限拒绝 | [公开数值](docs/evidence/round2-resources.json)，每例含大小/数量/RSS/耗时/状态 |
| GitHub三平台 × Python3.11–3.14 | VERIFIED：12组合各154 passed / 0 failed / 0 skipped，各10个资源探针符合预期；独立依赖检查通过 | 提交c001e4f，工作流45995062371，逐个读取日志；[公开证据](docs/evidence/round2-ci.json) |
| 真实第三方客户端/厂商计费 | NOT VERIFIED | 未安装或绕过本机限制；SDK不是实机 |
| 生产数据库迁移/部署 | NOT VERIFIED / 未执行 | 本轮不访问生产数据或切换服务 |

所有pytest临时 *.sqlite3 在每例结束核验 integrity_check=ok、foreign_key_check无行；资源子进程额外核验自有数据库。覆盖专题、进度、知识/关系/任务、同步/增量、归档/恢复、搜索、概念、偏好、迁移、CLI和MCP。拒绝样本同时检查记录、归档、游标；原有强制进程退出、失败重试、来源改变及回滚测试保留。

峰值RSS包含解释器、依赖及输入构造；资源样本未采集跨线程并发峰值，不把它解释为全进程硬内存限额。pytest的deselected是阶段筛选数量，不算跳过；最终全量无筛选。首轮夹具唯一约束错误、备份测试错误假设和canonical真实缺陷均已在阶段报告披露。

复现：安装requirements-dev.txt与requirements-quality.txt，运行 `python scripts/quality_gate.py --dependencies`，再运行 `python scripts/round2_resource_probe.py --output resource-probe.json`。不得将ALGORITHM_KB指向生产库；质量门禁与探针主动使用隔离路径。

CI合计1848次pytest用例执行、120次资源探针；它们是同一154用例集及10探针集在12环境重复执行，不称为1848个独立用例。后续仅证据/报告提交的检查以草稿PR #3最终head checks为准。公网和真实厂商客户端不在CI已验证范围。
