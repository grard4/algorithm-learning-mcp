# 发布准备情况

## 第四阶段发布候选验收（2026-11-28）

候选分支 `release-candidate/2026-11-28` 从第三轮提交 `d8f190686d3eef5abca052d7fad00793e5274b1a` 建立。候选当前仅含本报告、资源证据及本文件/变更记录的发布文档更新；业务源码、Schema、运行依赖和工作流未修改。第三轮 worktree 中已有的 5 项未提交改动因归属无法确认而保留在原处，未进入候选。

Windows Python 3.14.7 隔离环境按 `requirements-dev.txt` 与 `requirements-quality.txt` 安装后，质量门禁的静态检查、176 项回归、依赖一致性和漏洞扫描均通过；pip-audit 未报告漏洞。本机隔离安装、CLI、stdio MCP、回环 HTTP、合成数据初始化/读写、备份恢复以及从第二轮 `991ea40` 数据库副本重复启动均通过。错误 Schema 版本与不匹配 checksum 会分别以 `UNKNOWN_SCHEMA_VERSION`、`MIGRATION_CHECKSUM` 拒绝启动。此处的旧库验证是相同冻结 `core-v1` Schema 的跨版本重开与保留数据验证，不代表执行了新的 Schema 迁移。

A04 保持 `PARTIAL`。新增 Windows 子进程样本在接近 16 MiB 原始输入、约 31.2 MB 解压输出、近 20,000 个事件和近 250,000 个 JSON 节点时均按预期工作；过深 JSON 与超压缩比输入在写入前拒绝。4 个并行独立会话共用隔离 SQLite 后完整性/外键检查通过。接近解压上限的单任务峰值工作集约 95 MiB；并发测试没有形成理论或严格的聚合内存上界，服务也没有进程级并发/内存配额。具体边界见 [第四阶段验收报告](FOURTH_STAGE_RELEASE_CANDIDATE_REPORT.md) 与 [资源样本](docs/evidence/round4-resources.json)。

候选尚未推送，因而没有本轮候选 SHA 对应的 GitHub Actions 运行结果；历史 `main`/PR 检查不替代本轮 CI。生产本机未升级、未连接，数据库和生产配置未被操作。

## 当前分层结论

- 本机单用户：有条件通过；限于既有输入预算与正常单用户负载，A04 任意并发与进程级资源保证仍未验证。
- 公开源码候选：有条件通过；须披露 A04、跨文件系统归档提交窗口及其他未验证边界，并在推送后确认本候选 SHA 的完整远程 CI。
- 正式 GitHub Release：暂不建议；候选 SHA 的远程 CI 尚未运行，正式版本号/Release notes 审批未完成。
- 多用户或公网部署：不通过；无完整身份认证、多租户隔离、用户级资源配额或不可信调用者隔离。

本阶段没有创建 PR、合并 `main`、创建正式 Release/Tag 或发布 PyPI 包。生产部署若后续另行安排，仍须先备份并在隔离副本验收。

更新：2026-11-27，第三轮基线 main=991ea4030061be8e8740e33629fae2a8114936b0，代码候选 8b805a5，独立分支 audit/round3-20261127。本轮只完成源码与隔离验收，未升级生产、未推送、未合并、未创建 Release/Tag/PyPI。第二轮 PR #3 已合并及此前部署是历史事实，不作为本轮部署证据。

## 本机单用户

有条件通过源码候选标准：A09 原单位错误 NOT CONFIRMED，8 MiB 实际限制验证有效；A10 CLI 退出码与 A11 动态错误脱敏 VERIFIED。Windows Python 3.14.7/3.12.15 各 176 passed、0 failed、0 skipped；10 个资源探针、临时数据库完整性/外键、Lint、依赖一致性与漏洞检查通过。A04 保持 PARTIAL，具体状态、命令、边界见 [第三轮完整报告](THIRD_ROUND_REMEDIATION_REPORT.md)。

公开源码候选有条件通过：需披露剩余限制；正式发布准备尚不完整，本轮 GitHub Actions 与生产部署未验证。其他客户端仍为 NOT VERIFIED；第二轮历史 13 个 CI 作业成功不能替代本轮代码检查。

部署前必须备份并在副本验证。六个旧写接口继续返回 LEGACY_WRITE_DISABLED；CLI 现在退出 1。统一使用 update_learning；旧读取保留。预算、兼容变化及错误约定见 [输入预算](docs/INPUT_BUDGETS.md)。本轮未修改个人偏好、固定课程规则或生产 Schema。

## 公网部署

不达标、不支持直接公网服务。仍没有身份认证、多租户隔离、细粒度权限或用户级并发/速率配额；HTTP仅回环。输入预算不等于传输层/进程级沙箱，不保证客户端JSON解析前或任意并发下的内存安全。SSH单用户隧道需独立认证，部署NOT VERIFIED。

## 保留的边界

- 真实Claude Desktop/Cursor/VS Code/Gemini等客户端：NOT VERIFIED；stdio/HTTP SDK成功不是厂商客户端或真实课程验收。
- 本机升级前后生产数据与151份已登记归档已核验；代码/偏好回滚在副本演练。真实Codex课程的偏好读取、上下文、归档及进度写入成功；不推广到其他客户端或任意课程。
- 文件系统与SQLite无跨系统原子提交；文件发布后崩溃可能留下可在重试复用的孤立内容寻址文件。无自动删除历史，磁盘满/断电/敌对管理员完整场景尚未验证。
- 首次发现注册与同步分两步持久化，I/O失败可保留已注册未同步聊天；消息与游标事务不会提前推进。
- 原子发布依赖硬链接，网络共享文件系统未验证。搜索仍须尊重incomplete；旧隐藏读取及受信任本地CLI不构成多用户权限系统。
- 固定规则保证来源不受偏好修改，不保证外部模型遵从，不是课程文件服务端强制校验；实际模型Token计费未验证。
- 当前core-v1冻结；未知Schema拒绝。未来迁移需独立实现与副本验证，不允许覆写checksum绕过检查。

复核、计划、实现和测试分别见 [审计复核](AUDIT_ROUND2_REVIEW.md)、[修复计划](ROUND2_FIX_PLAN.md)、[修复报告](ROUND2_FIX_REPORT.md)、[测试矩阵](ROUND2_TEST_MATRIX.md)。旧审计文档只作历史证据。
