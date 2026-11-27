# 第二轮修复计划

基线与证据见 ROUND2_REPOSITORY_STATE.md、AUDIT_ROUND2_REVIEW.md。本计划在业务修改前保存，各阶段测试通过后再推进。

| 顺序 | 文件/函数与方案 | 兼容性及数据影响 | 测试/验收/回滚 |
|---|---|---|---|
| 1 A01 | server.tool 与六个旧写函数：从 MCP 暴露名单移除，函数本体稳定返回 LEGACY_WRITE_DISABLED；CLI call 同样拒绝 | 旧写调用必须迁移 update_learning 并提供 topic_version；旧读取、既有数据库不变。内部 KB.write 为受信任本地存储原语，不公开为 MCP/CLI 写入替代 | legacy 实际 stdio tools/list+隐藏名直接 call、CLI call、直接函数；合法现代写及跨专题声明回归。回滚该提交恢复旧行为但也恢复风险 |
| 2 A02 | 新 errors.py 映射；server.tool、cli.main、sync.run/main 统一系统异常脱敏；稳定代码和异常类型/errno 诊断 | 业务 KBError 保留；系统异常文本不再外传；日志不写路径/原始异常。CLI 系统失败非零退出，MCP ok=false | FileNotFound/Permission/OSError/SQLite/未知异常及临时文件错误；验证没有敏感字符串且有错误码。独立提交可回滚 |
| 3 A03/A07 | 集中 input_limits.py，规范化输入显式 Schema及严格额外字段/时间戳/数量/UTF-8预算；先校验再序列化；publish 移到 mutate 内最后 | 默认单条 256 KiB、最多128条、请求序列化2 MiB；拒绝旧任意 timestamp/未声明字段。不改历史数据，修改测试有效时间戳 | 上下界、多字节、总量、深嵌套、原子性、幂等及发布失败；超限零数据/归档/游标变化。回滚代码不需迁移 |
| 4 A04/A07 | sync.read_bytes/parse/visible：原始16 MiB、解压32 MiB、窗口8 MiB、比率200（1 MiB小文件宽限）、事件20000、行1 MiB、节点250000、深度32；分块有界读，先限输出再验证完整帧；发布后置 | 超限完整日志暂拒绝，原游标/历史保留；不截断历史或默默跳过。已超限课程需显式分档方案，不能自动删源。预算是输入/处理结构上限，不等于 OS 内存隔离 | 正常/多帧/截断/损坏/各上限、恢复、并发原有测试；独立子进程测峰值内存及耗时。回滚代码恢复旧接口无需数据回滚 |
| 5 A05 | 保存测量报告；完整规则不改，避免违背前次强制初始化约定 | 不声称字符数下降等于计费节省；不对未安装客户端测量作推断 | 两种 tokenizer、实际 tools/list、前后 Schema 量化；新增资源 Schema 可能增加成本如实报告 |
| 6 A06 | docs/SCHEMA_EVOLUTION.md 独立设计，冻结 v1；未来新增版本逐个事务升级，备份与副本验证 | 不修改 migrations.py 或生产 Schema | 当前迁移回归，git 核对 SQL/迁移零差异；文档可回滚 |

全面回归：原88项加新安全/资源用例；每个临时 SQLite 执行 integrity_check 和 foreign_key_check。保留基线失败与修复后结果。Windows本机测试；未实际执行的跨平台 CI 标为等待验证。新发现若涉及真实数据破坏或核心 API 重大改动，暂停相关阶段分析，不擅自迁移。发布仅评估单用户本机能力，不将 CI 或规则硬编码等同公网安全。
