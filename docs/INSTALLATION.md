# 安装与初始化

默认入口为根目录 README.md，英文版为 README.en.md。使用 Python 3.11+；本轮实际环境为 Windows 11 / Python 3.14.7。运行依赖安装命令：

```powershell
git clone https://github.com/grard4/algorithm-learning-mcp.git
cd algorithm-learning-mcp
py -3.11 -m venv .venv
.\.venv\Scripts\python.exe -m pip install -r requirements.txt
```

如本机只安装其他受支持版本，使用该版本建立环境。开发测试另装 requirements-dev.txt。首次启动服务器自动创建空库，不需要导入私人课程。运行前设置自己的 `ALGORITHM_KB`；不要误指向其他学习者或生产数据库。

```powershell
$env:ALGORITHM_KB = "$PWD/data/learning.sqlite3"
.\.venv\Scripts\python.exe server.py
```

stdio 服务等待客户端协议消息，不以终端无输出判断启动失败。可用临时目录运行 `python -m pytest` 验证；测试结果只覆盖执行环境。

固定版本安装可在创建虚拟环境前执行 `git checkout v0.1.1`；直接使用 `main` 将取得最新提交。发布内容不包含虚拟环境、私人数据库、凭据或审计临时目录。
