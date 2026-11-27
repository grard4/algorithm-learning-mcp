# 导入预算与兼容性

数值集中在 input_limits.py，不能用环境变量静默取消。预算限制单次处理，不是认证、并发配额或操作系统沙箱；传输层解析JSON之前也可能已分配客户端输入，不能据此开放公网。

| 输入 | 上限 |
|---|---:|
| 规范化消息数量 | 128 |
| 每条正文 UTF-8 | 256 KiB |
| 规范化完整请求（转义、标识和actor计入） | 2 MiB |
| request_id / actor / conversation_id | 各512 UTF-8字节；归档聊天ID另须满足原安全路径组件规则 |
| 同步原始文件 | 16 MiB |
| 解压结果 | 32 MiB |
| 解压窗口 | 8 MiB |
| 解压字节相对原文件 | 200倍，最小允许1 MiB输出；仍受32 MiB总量限制 |
| 同步事件或压缩帧 | 20000 |
| JSONL单行 | 1 MiB |
| JSON嵌套/累计节点（键也计入） | 深度32 / 250000节点 |

规范化消息只接受 role/content/timestamp，不接受未知扩展字段或嵌套内容。role为user/assistant，正文非空；timestamp必须是有效RFC3339日期时间，带Z或数字时区，允许最多六位小数秒。拒绝无时区、非法日历、闰秒或无效偏移。同步可见消息使用相同正文和时间戳约束，非可见事件仍受整体资源预算限制。

超限返回 TOO_LARGE；时间戳返回 INVALID_TIMESTAMP；字段错误返回 INVALID_INPUT。错误不推进游标，不截短或删除历史。日志已超过预算时，应保留原源文件与游标，评估显式分档/迁移方案；不要靠截断旧文件、删除旧消息或放开硬预算“恢复”同步。

文件按64 KiB读取，解压按剩余预算读取；先限输出，再对同一有界字节快照验证完整帧，以覆盖流API不拒绝截断尾帧的情况。预算之内仍有原始字节、解压数据、解析对象及数据库开销，不宣称峰值内存等于某一输入字节上限。

所有输入校验先于归档和数据写入。逻辑冲突也先于发布。文件系统和SQLite没有跨系统原子提交：文件发布后进程崩溃可留下未登记的内容寻址文件，重试验证并复用，不能自动删除未知历史归档。原有消息/游标不会因这个窗口提前提交。新聊天注册与后续同步是两个持久步骤，后续失败可保留已注册空聊天。

六个旧写接口 update_topic_progress、add_knowledge、update_knowledge、record_learning_task、record_learning_result、add_knowledge_relation 已停用。ALGORITHM_LEGACY_TOOLS=1也不会暴露它们；CLI与直接函数返回LEGACY_WRITE_DISABLED。迁移到update_learning时读取topic_version，按changes Schema携带证据及必要来源声明。旧读取仍可用，内部KB.write仅是可信本地代码的存储原语，不是公开绕过入口。
