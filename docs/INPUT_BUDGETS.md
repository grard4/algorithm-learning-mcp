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

文件按64 KiB读取，解压按剩余预算读取；v0.2.2 在每帧解压前检查帧数与帧边界，只把一个完整帧交给 zstandard==0.25.0 的 stream_reader，超限帧不会进入解压器；不再二次解压。解码器仍校验块内容及校验和。预算之内仍有原始字节、解压数据、解析对象及数据库开销，不宣称峰值内存等于某一输入字节上限。

所有输入校验先于归档和数据写入。逻辑冲突也先于发布。文件系统和SQLite没有跨系统原子提交：文件发布后进程崩溃可留下未登记的内容寻址文件，重试验证并复用，不能自动删除未知历史归档。原有消息/游标不会因这个窗口提前提交。新聊天注册与后续同步是两个持久步骤，后续失败可保留已注册空聊天。

六个旧写接口 update_topic_progress、add_knowledge、update_knowledge、record_learning_task、record_learning_result、add_knowledge_relation 已停用。ALGORITHM_LEGACY_TOOLS=1也不会暴露它们；CLI与直接函数返回LEGACY_WRITE_DISABLED。迁移到update_learning时读取topic_version，按changes Schema携带证据及必要来源声明。旧读取仍可用，内部KB.write仅是可信本地代码的存储原语，不是公开绕过入口。

## 窗口单位和 CLI 退出码（第三轮复核）

固定 zstandard==0.25.0 的 C 后端将 max_window_size 原样传给 ZSTD_DCtx_setMaxWindowSize，单位为字节。上游文档的 KiB 描述与实现不一致；不应按该描述除以 1024。实际帧窗口 4/8 MiB 接受，16/128 MiB 拒绝；改传 8192 会拒绝合法 4/8 MiB 帧。CFFI 源码也直接转传，未执行 CFFI 动态测试。升级依赖必须重跑窗口专项；原输出、比率等预算保持不变。证据见 ../THIRD_ROUND_REMEDIATION_REPORT.md 与 evidence/round3-window.json。

CLI call 成功（含没有 ok 字段的历史成功形状）退出 0；ok=False、参数/文件/数据库/意外异常退出 1，stdout 保持可解析 JSON 与稳定错误码。--help 仍为帮助文本并退出 0。成功执行 main 不额外抛 SystemExit，以保留 runpy 包装器兼容。MCP 错误封装语义不变。verify 的结果仍需检查 integrity、foreign_keys、bad_archives；本次 call 修复不将 verify 的诊断字段改造成 ok 契约。

错误响应不回显不存在的 ID、非法输入值或自定义字段名。VALIDATION_ERROR 保留 details 的 path/expected/problem，非 Schema 字段标记为 <field>；同位置未知字段可能合并。内部日志保留 code/type/native_code，不写入用户值、路径或 traceback。

自动发现最多枚举 50,000 个匹配源文件；首次快照最多 8 MiB，按来源目录单独保存。超限保守拒绝，不缩减现有字节/帧/事件预算。
