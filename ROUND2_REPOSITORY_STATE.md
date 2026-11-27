# 第二轮仓库状态

本文保留审计开始时的访问边界快照。后续维护者授权的本机升级、备份及真实课程验收见 [部署验收更新](docs/ROUND2_LOCAL_ACCEPTANCE.md)；下文“未打开生产数据库”等仅对应最初审计阶段。

日期：2026-11-27。审计基线为远程 main 的 `0afc5b1cf6d57f40a092ea659508e8f06153de69`，仓库 `grard4/algorithm-learning-mcp`。先 fetch 再核验，未使用旧报告提交替代当前代码。

原课程规则分支 HEAD 为 `b001fe8`，与最新 main 的文件树一致；原 main 工作区仍在 `42f5937`，旧审计工作区在 `90221cb`。三个工作区均无已跟踪、暂存或未跟踪修改；旧环境和忽略材料保留，不清理、不覆盖。无法仅凭 Git 状态排除其他会话未落盘工作，故本轮创建独立工作区及 `audit/round2-20261127` 分支。

当前 shell 无 ALGORITHM_* 变量。生产连接由独立本地运行目录的 local_server.py 启动，数据库由用户配置的 ALGORITHM_KB 指向既有课程库；生产运行配置和数据路径仅在本机核对，不写入公开报告。未打开生产数据库，不迁移、不做压力测试、不切换部署。公开默认配置为项目 data/learning.sqlite3 和 config/learning_preferences.md；新工作区 data 仅含 .gitkeep，私人偏好未复制。测试强制使用临时数据库、缺失偏好或合成偏好；复用已有审计虚拟环境解释器而不修改其依赖。

本地环境：Windows、Python 3.14.7、SQLite 3.50.4、MCP SDK 1.30.0、zstandard 0.25.0、pytest 9.2.0、Ruff 0.17.6、tiktoken 0.14.0。psutil 未安装；资源压力测量使用独立子进程与 Windows 原生进程内存统计，不把缺失依赖记为通过。

仅允许本轮隔离测试与逻辑独立提交。不强制推送、不改标签、不发布 Release/PyPI；跨平台结果只有实际运行后才标为通过。GitHub CI 若本轮未执行则列为待验证。基线审计不修改 SQL 文件、迁移历史或真实用户数据。
