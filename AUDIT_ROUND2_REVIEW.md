# 第二轮审计复核

基线 `0afc5b1cf6d57f40a092ea659508e8f06153de69`。状态报告先于本报告保存，下表保留修复前复核结论；当前最终状态见文末。本地合成最小复现见 tests/security/test_round2_reproduction.py：9 个期望安全断言在基线失败；首次夹具路径重复导致的 8 个 setup error 单独保存，修正后才采信产品复现。原始日志含临时路径，留在忽略目录。

| 项目 | 原始线索及实际调用链（基线位置） | 前提、防护与影响 | 风险及结论 |
|---|---|---|---|
| A01 | server.py:208 起的六个旧写入函数 → evidence（只查存在）→ KB.write；CLI call → TOOLS/getattr 同一路径，未经过 Context.update/validate_changes | MCP 需显式 legacy=1；CLI 默认可调全部 TOOLS；正常外键/实体版本防护不足以检查聊天专题及声明来源。add_knowledge 跨专题、record_learning_task 跨专题证据写入均复现。旧读取不涉及本缺陷 | 高（本机受信任工具的逻辑完整性，非远程身份认证漏洞）；CONFIRMED |
| A02 | server.py:45 工具包装器 → sync_conversation → sync_file → read_bytes → 文件异常；sync.run/main 将 str(e)/source 路径写日志 | 缺失源文件即可使异常返回绝对临时路径；权限、数据库及备份错误同属系统异常出口。已有偏好脱敏未覆盖这些入口 | 中；CONFIRMED |
| A03 | server.py:302 record_conversation_update → 非空字符串检查 → dump/encode → publish → mutate | 无消息数量、UTF-8 字节、额外嵌套字段及时间戳语义上限。129 条、256 KiB+1 单条、无效日期及嵌套扩展字段均被接受。已有角色/文本/路径校验不足 | 中；CONFIRMED |
| A04 | sync.py:34 read_bytes → 整文件读取/decompressobj/parts join → parse.splitlines/json.loads → visible → sync_file | 2 MiB 重复字符压缩样本无任何比率限制并完整解压；未设输入、输出、事件、单消息、JSON 深度预算。已有截断帧、历史消息变更和游标回滚防护应保留 | 中（本地源/导入边界）；CONFIRMED |
| A05 | course_rules.py COURSE_INSTRUCTIONS → FastMCP 初始化；22 工具的 tools/list | 初始化 8248 字节；cl100k_base 2891、o200k_base 2230 估算 token。完整工具描述+Schema 16102 字节、3925/3907 token；纯 inputSchema 12705 字节、3022/3139 token。描述中完整规则副本数为 0。真实客户端计费/转发/缓存不可由协议推断 | 低/成本；DESIGN_DECISION：保留用户要求的完整强制规则，不将其降为按需参考 |
| A06 | migrations.py initialize → core-v1 文件 checksum → 已有结构核对 → 原子执行 | 当前 checksum、未知版本、结构漂移与失败回滚的 5 项隔离回归通过；不是已证实数据损坏。源码写权限者能同时改校验逻辑，checksum 不是对管理员的安全认证 | 低/未来演进；DESIGN_DECISION：冻结 v1，提供版本追加方案，不修改现有 SQL 或账本 |
| A07（新增） | record_conversation_update 在 mutate 幂等冲突检查前 publish；sync_file 亦在历史内容一致性检查前发布 | 同一 request_id 改正文被拒绝但新增归档文件，复现成立。数据库/游标未推进，却积累孤立文件。不能用删除所有历史归档补救 | 中；CONFIRMED；将发布移动到事务校验后，并保留崩溃重试语义 |

同专题其他聊天消息本来允许；跨专题证据只要显式准确声明也允许，不应把合法复用误判为绕过。A01 优先评估适配，旧接口缺少 topic_version，关系接口缺少统一更新上下文，透明转接会改变版本、幂等和返回契约；采用允许的停止旧写入方案，MCP、CLI 和直接包装调用一致拒绝，保留旧读取及新版合法写入。

实际厂商客户端成本/兼容性：NOT VERIFIED。stdio/HTTP 的服务指令来源相同，不声称各客户端实际都消耗同样 token。压缩压力样本规模受控，不运行无限炸弹或访问用户日志。

## 最终状态

| 项目 | 状态 | 完成依据 |
|---|---|---|
| A01 | VERIFIED | 六个旧写本体拒绝、MCP legacy不暴露、CLI不能绕过；旧读取及新版合法证据回归通过 |
| A02 | VERIFIED | 工具/CLI/同步/启动错误脱敏；保留稳定代码及类型、原生错误码诊断，无路径或traceback |
| A03 | VERIFIED | 严格Schema、时间戳/字节/数量/总量校验；边界、深嵌套和零部分写入验证 |
| A04 | PARTIAL | 有界源/输出/窗口/比率/事件/行/消息/深度/节点/帧；截断、进程死亡和恢复回归；独立资源实测 |
| A05 | DESIGN_DECISION | 量化后保留完整强制初始化；安全Schema新增成本如实披露，不声称已优化 |
| A06 | DESIGN_DECISION | 当前5项迁移回归通过，设计文档完成；SQL、迁移及固定规则正文与基线零差异 |
| A07 | VERIFIED | 逻辑拒绝不再新建归档；发布失败回滚，重试检查/恢复归档；保留跨系统崩溃窗口说明 |
| A08 | VERIFIED | 新发现：sync_file canonical=None导致首次按名称注册失败；空字符串规范化修复，首次注册/同步回归通过 |

A01仅缩小兼容入口，不宣称应用拥有多用户身份认证。第三轮复核将A04总体保持PARTIAL：已验证部分限于明确输入预算和已执行样本，不代表任意并发或敌对本机管理员下的总内存保证。详见 ROUND2_TEST_MATRIX.md 与 ROUND2_FIX_REPORT.md。

第三轮状态以 [最新总表](THIRD_ROUND_REMEDIATION_REPORT.md) 为准；A02 的系统异常修复继续有效，动态业务错误回显另计 A11。
