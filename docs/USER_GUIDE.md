# 使用流程与能力边界

长期课程使用真实聊天 ID。先通过 get_context_manifest 的 current_only 模式查询已有关联；未关联时才 register_conversation。按需读本专题摘要，出现具体交叉知识时再检索，避免默认读取所有专题历史。

只保存持久成果，update_learning 使用 topic_version 乐观锁和唯一 request_id；来源为归档 messages.id。新知识需要 data.title/content/evidence；进度改变需 progress.set.evidence 或 progress.append.evidence。证据是消息 ID 字符串数组，不是证据对象或模型自我判断。发生版本冲突先读取变化，不能盲目覆盖。

C2.3 三个接口只读取已批准概念关联、详情和失效事件。新库可能返回 not_indexed，不能通过这些接口创建或批准关联；关联不表示用户掌握，也不会自动继承进度。此次不实现审批导入流程。

历史恢复按消息分页；备份用 cli.py backup，恢复写入新目标。备份及恢复路径由使用者指定，不使用旧库覆盖当前合法业务。

使用示例（仅针对独立测试数据库）：

```json
{"conversation_id":"your-actual-conversation-id","current_only":true}
```

以上是 get_context_manifest 的参数。后续调用以实际 tools/list Schema 为准，不猜专题 canonical 或消息 ID。
