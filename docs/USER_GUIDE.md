# 使用流程与能力边界

## 控制续课输入量

- 工具发现先只列名称；只展开本次需要且尚未知的单个工具定义，不输出整个工具目录。不要把 `ALL_TOOLS.filter(...)` 的完整对象直接输出。
- 已在当前上下文中的固定规则无需再取；个人偏好仍按接口要求读取。普通续课默认 `get_topic_context(full=false)`，仅所需字段被省略/截断时升级到全文。已有可靠成功收据后不全量读回。
- 在课程目录维护简短 `outputs/COURSE_HANDOFF.md`：真实聊天与专题 ID、读取时间/版本、当前与下一单元、已授课/用户自述/实测的区别、未决问题、证据 ID、必要文件路径；不得复制讲义正文，不抹去用户约束。状态变化后更新；无变化不重复写。
- 恢复或新上下文先读交接摘要，再读取该专题当前摘要；没有实际持有旧内容时不传 `known_version`，必要时定点核实原记录。历史正文只在核实问题时按 ID 分页。
- 交接文件减少恢复所需检索，不能删除客户端自动携带的旧历史。真正缩短长聊天需用户主动压缩或切换聊天；新聊天使用真实新 ID 并关联原专题，不冒用旧 ID。不要声称此改动保证降低实际计费。

> 课程规划、授课、练习及进度策略前读取 `get_learning_preferences`。固定课程规则已随初始化完整下发，已有正文无需重复读取；丢失初始化上下文时调用只读 `get_course_rules`。偏好与固定规则分开保存，删除偏好不会删除固定层，具体适用条件见 [内置课程规则](COURSE_RULES.md)。

长期课程使用真实聊天 ID。先通过 get_context_manifest 的 current_only 模式查询已有关联；未关联时才 register_conversation。按需读本专题摘要，出现具体交叉知识时再检索，避免默认读取所有专题历史。

只保存持久成果，update_learning 使用 topic_version 乐观锁和唯一 request_id；来源为归档 messages.id。新知识需要 data.title/content/evidence；进度改变需 progress.set.evidence 或 progress.append.evidence。证据是消息 ID 字符串数组，不是证据对象或模型自我判断。发生版本冲突先读取变化，不能盲目覆盖。

C2.3 三个接口只读取已批准概念关联、详情和失效事件。新库可能返回 not_indexed，不能通过这些接口创建或批准关联；关联不表示用户掌握，也不会自动继承进度。此次不实现审批导入流程。

历史恢复按消息分页；备份用 cli.py backup，恢复写入新目标。备份及恢复路径由使用者指定，不使用旧库覆盖当前合法业务。

使用示例（仅针对独立测试数据库）：

```json
{"conversation_id":"your-actual-conversation-id","current_only":true}
```

以上是 get_context_manifest 的参数。后续调用以实际 tools/list Schema 为准，不猜专题 canonical 或消息 ID。

第二轮更新：六个旧写接口已停用，系统异常不返回绝对路径；规范化导入及同步采用集中资源预算和有效时间戳校验，超限保留历史和游标。详细兼容变化、恢复及边界见 [输入预算](INPUT_BUDGETS.md)，当前结果见 [第二轮验收](../ROUND2_TEST_MATRIX.md)。
