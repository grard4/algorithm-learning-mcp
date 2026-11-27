# 安装与初始化

默认入口为根目录 README.md，英文版为 README.en.md。使用 Python 3.11+；本地测试使用 Windows；三平台 CI 已覆盖 Python 3.11–3.14，具体提交及结果见 [测试矩阵](../TEST_MATRIX.md)。运行依赖安装命令：

```powershell
git clone https://github.com/grard4/algorithm-learning-mcp.git
cd algorithm-learning-mcp
py -3.11 -m venv .venv
.\.venv\Scripts\python.exe -m pip install -r requirements.txt
```

如本机只安装其他受支持版本，使用该版本建立环境。开发测试另装 requirements-dev.txt；执行完整质量门禁还需 requirements-quality.txt。首次启动服务器自动创建空库，不需要导入私人课程。运行前设置自己的 `ALGORITHM_KB`；不要误指向其他学习者或生产数据库。

```powershell
$env:ALGORITHM_KB = "$PWD/data/learning.sqlite3"
.\.venv\Scripts\python.exe server.py
```

stdio 服务等待客户端协议消息，不以终端无输出判断启动失败。可用临时目录运行 `python -m pytest` 验证；测试结果只覆盖执行环境。

直接使用 `main` 取得已合并源码。需要复现固定版本时，在创建虚拟环境前检出经核验的提交 SHA，并记录 `git rev-parse HEAD`。历史标签 `v0.1.1` 不包含后续审计修复或内置课程规则，不应把它作为这些能力的安装版本。升级已有服务前备份数据库、归档、配置和偏好；重启并重新连接，确认 `get_course_rules` 返回版本 `2` 后再精简偏好，见 [迁移步骤](COURSE_RULES.md)。发布内容不包含虚拟环境、私人数据库、凭据或审计临时目录。
