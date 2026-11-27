# 第二轮修复阶段记录

基线 `0afc5b1cf6d57f40a092ea659508e8f06153de69`。复现及计划在代码修复前提交 `6ebf1e3`。

## 阶段 1：旧写接口

六个旧写接口不再通过 legacy 模式暴露，函数本体也拒绝执行，CLI 无法绕过。保留旧读取；合法写入使用 update_learning，保留同专题跨聊天证据及准确声明的跨专题引用。旧接口无 topic_version，透明适配会改变并发及幂等契约，因此选用任务允许的停用方案。

本机专项：14 passed、11 deselected（筛选范围，不计为 skipped）。包含实际 legacy stdio 发现和隐藏名称直接调用、六种 CLI/函数路径，以及现代来源校验。无生产数据、SQL 或迁移文件修改。

## 阶段 2：异常脱敏

errors.py 统一映射文件/权限/存储/SQLite/输入及未知异常；server 工具、CLI 顶层及同步日志复用。保留业务 KBError，原生错误日志只含类型、错误码和 errno/SQLite 码，不记录原异常、路径或 traceback；SQLite busy/locked 仍可识别重试。

专项 12 passed、8 deselected。首次备份错误测试误以为缺失父目录会失败，但备份本就合法创建目录；改为文件阻挡目录的真实失败条件后通过，此为测试假设修正，未修改合法备份逻辑。

## 阶段 3：规范化导入

input_limits.py 集中定义预算，MCP 发布严格消息 Schema，实际函数在任何序列化和数据库写入前检查数量、额外字段、UTF-8 字节和 RFC3339 日期/时区。总预算按包含元数据及转义后的请求计数；单条256 KiB、128条、总2 MiB。额外嵌套字段在递归序列化之前拒绝。

归档 publish 移至事务内 SQL 操作之后；幂等冲突不再留下新文件，发布失败回滚数据库。既有归档永不删除；若进程在文件发布与 SQLite 提交之间崩溃，内容寻址文件可能暂时孤立但可在同请求重试时复用，这是跨文件系统/数据库边界的明确限制。

32 passed、1 deselected，含 UTF-8/数量/总量精确边界、恶意时间戳、嵌套、零部分写入及 stdio/HTTP。旧合法测试的占位 timestamp='time' 改为真实 RFC3339 时间，未放宽拒绝断言。

## 阶段 4：同步预算与恢复

sync.py 按64 KiB读取，源16 MiB、输出32 MiB、窗口8 MiB、比率200（小文件1 MiB宽限），事件/帧最多20000，行1 MiB，单消息256 KiB，JSON深度32/节点250000。先限制分块解压输出，再对同一有界源进行帧完整性检查，避免流式 API 接受截断尾帧；第二遍保留有界小块残余，不反复复制整个剩余源。解析按有界行读取，先查深度再 JSON 解析，再累计节点数。输入预算不是进程或多会话并发的 OS 内存配额。

同步发布移至历史一致性和 SQL 检查之后，失败不推进游标；不修改合法历史。中断后保留内容寻址文件并可重试。原始/规范化归档重放仍核验已有文件、恢复缺失文件，不覆盖损坏文件。首次发现的注册元数据为独立持久步骤，后续 I/O 失败可留下已注册但未同步聊天；消息和游标仍以原子同步事务为准。

先35项同步/复现通过；补充窗口、帧数、精确边界、启动和同步错误后42项专项通过。全量初轮148 passed。10个独立进程资源样本中2个合法接受、8个超限拒绝；拒绝样本数据库/游标一致且无归档创建，所有库 integrity_check=ok、foreign_key_check无错。峰值进程RSS为71917568–142426112字节，包含依赖导入与造数，不是服务工作内存的理论上界。具体输入/输出/数量/耗时见 docs/evidence/round2-resources.json。

补充 A08（低风险）：sync_file 的 canonical 默认 None 原样传入 KB.register，首次按名称注册会触发 AttributeError。12个新测试先暴露该缺陷，修复默认值为空字符串后通过。未修改数据库或专题身份规则。

## 阶段 5–6：成本与Schema设计

A05完整规则不改，测量报告见 docs/ROUND2_CONTEXT_COST.md；instructions为8248字节/2891或2230估算token。新增安全Schema使工具列表增加427字节、142/147估算token；不是Token优化成功。实际厂商客户端计费NOT VERIFIED。

A06设计文档 docs/SCHEMA_EVOLUTION.md 已完成。现有5项迁移回归通过，migrations.py和三个SQL文件与基线零差异；未实施core-v2、未改历史checksum。固定课程规则也零差异。

## 全量本地验收

最终业务提交9304295：Windows Python3.14.7，154 passed/0 failed/0 skipped（27.56秒）；Python3.12.15，154 passed/0 failed/0 skipped（22.39秒）。Ruff、pip check、pip-audit全部通过。测试结束逐库integrity_check与foreign_key_check通过，10个资源子进程也各自核验。CI以ROUND2_TEST_MATRIX.md记录为准，未运行的环境不继承PR #2旧结果。

核心改动：server.py、errors.py、cli.py、sync.py、input_limits.py；安全测试与scripts/round2_resource_probe.py；工作流补充每平台资源测量。各阶段为独立提交，不包含生产数据或生效配置。原始基线失败、夹具错误与阶段试验日志保留在本机忽略目录；公开报告只保留脱敏摘要。

## GitHub交付与最终结论

草稿PR #3，分支audit/round2-20261127。提交c001e4f的工作流45995062371全部13个作业成功；12组合逐日志确认各154项通过、0失败、0跳过，各10个资源探针符合预期，依赖检查成功。记录见docs/evidence/round2-ci.json。未合并、未部署、未创建Release/PyPI。

A01–A04及新增A07/A08为VERIFIED；A05/A06为DESIGN_DECISION，不强行改写规则或Schema。满足披露兼容性收紧后的可信本机单用户候选验收标准；不满足公网部署标准。遗留：厂商客户端实机、实际Token计费、生产升级、断电/磁盘满完整场景、任意并发OS内存隔离未验证。下一步审阅草稿，批准后再合并；部署仍需备份和副本验收。
