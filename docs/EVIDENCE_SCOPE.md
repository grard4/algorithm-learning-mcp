# 学习更新的来源范围

update_learning 的 conversation_id 必须存在并属于目标 topic_id；它是审计来源，不是身份认证。没有基于 actor 字符串的管理员绕过。

evidence 仍是 messages.id 字符串数组。同专题不同聊天可以互引。跨专题引用需要在知识/任务 data.evidence_sources 或 progress.set.evidence_sources 中加入逐条来源：

```json
{"message-id":{"conversation_id":"source-chat","topic_id":"source-topic","scope":"cross_topic"}}
```

显式同专题来源使用 scope=same_topic。服务器从数据库解析消息、归档、聊天及专题，检查声明完全匹配。外部证据仍通过已登记聊天归档，URL 或任意字符串不是可验证消息 ID。

source_conversation 是条目原始来源聊天，必须属于条目专题；跨专题来源保存在 evidence_sources。relations 允许关联其他专题知识，至少一端属于本次更新专题。数据库 Schema 不变；历史数据不回写，旧的不明确来源在下次编辑时需要补齐声明。
