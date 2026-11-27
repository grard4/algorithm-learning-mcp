# 第二轮修复阶段记录

基线 `0afc5b1cf6d57f40a092ea659508e8f06153de69`。复现及计划在代码修复前提交 `6ebf1e3`。

## 阶段 1：旧写接口

六个旧写接口不再通过 legacy 模式暴露，函数本体也拒绝执行，CLI 无法绕过。保留旧读取；合法写入使用 update_learning，保留同专题跨聊天证据及准确声明的跨专题引用。旧接口无 topic_version，透明适配会改变并发及幂等契约，因此选用任务允许的停用方案。

本机专项：14 passed、11 deselected（筛选范围，不计为 skipped）。包含实际 legacy stdio 发现和隐藏名称直接调用、六种 CLI/函数路径，以及现代来源校验。无生产数据、SQL 或迁移文件修改。

## 阶段 2：异常脱敏

errors.py 统一映射文件/权限/存储/SQLite/输入及未知异常；server 工具、CLI 顶层及同步日志复用。保留业务 KBError，原生错误日志只含类型、错误码和 errno/SQLite 码，不记录原异常、路径或 traceback；SQLite busy/locked 仍可识别重试。

专项 12 passed、8 deselected。首次备份错误测试误以为缺失父目录会失败，但备份本就合法创建目录；改为文件阻挡目录的真实失败条件后通过，此为测试假设修正，未修改合法备份逻辑。
