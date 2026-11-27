# 第三方依赖与分发边界

核查日期：2026-11-27。本次发布仅含项目源码，不打包 `.venv`、Python、wheel、依赖源码或二进制。依赖由使用者通过 pip 从其分发源安装，保留其自带版权与许可证。项目的 PolyForm 许可不能覆盖或限制第三方独立组件已有权利。

下表来自实际安装环境元数据；相应许可/声明文件已读取并计算哈希。元数据与文字检查不等于独立法律权属鉴定，不保证未来版本保持相同许可。完整本地清单位于 Git 忽略的核查目录。

| 组件 | 本次版本 | 元数据许可或说明 |
|---|---|---|
| annotated-types | 0.8.0 | MIT |
| anyio | 4.16.0 | MIT |
| attrs | 26.1.0 | MIT |
| certifi | 2026.11.20 | MPL-2.0 |
| cffi | 2.1.1 | MIT-0 |
| click | 8.5.1 | BSD-3-Clause |
| colorama | 0.4.6 | BSD 风格；已读取 LICENSE.txt，元数据未填许可证名称 |
| cryptography | 50.0.2 | Apache-2.0 OR BSD-3-Clause |
| h11 | 0.16.0 | MIT |
| httpcore | 1.0.9 | BSD-3-Clause |
| httpx | 0.28.1 | BSD-3-Clause |
| httpx-sse | 0.4.3 | MIT |
| idna | 3.20 | BSD-3-Clause |
| iniconfig | 2.3.1 | MIT |
| jsonschema | 4.26.0 | MIT |
| jsonschema-specifications | 2025.9.1 | MIT |
| mcp | 1.30.0 | MIT |
| packaging | 26.4 | Apache-2.0 OR BSD-2-Clause |
| pip | 26.2.1 | MIT |
| pluggy | 1.7.0 | MIT |
| pycparser | 3.12 | BSD-3-Clause |
| pydantic | 2.14.4 | MIT |
| pydantic-settings | 2.16.3 | MIT |
| pydantic_core | 2.50.5 | MIT |
| Pygments | 2.21.0 | BSD-2-Clause |
| PyJWT | 2.15.1 | MIT |
| pytest | 9.2.0 | MIT |
| python-dotenv | 1.2.4 | BSD-3-Clause |
| python-multipart | 0.0.34 | Apache-2.0 |
| pywin32 | 312 | PSF |
| referencing | 0.37.0 | MIT |
| rpds-py | 2026.9.1 | MIT |
| sse-starlette | 3.7.1 | BSD-3-Clause |
| starlette | 1.10.0 | BSD-3-Clause |
| typing-inspection | 0.4.5 | MIT |
| typing_extensions | 4.16.0 | PSF-2.0 |
| uvicorn | 0.54.0 | BSD-3-Clause |
| zstandard | 0.25.0 | BSD-3-Clause |

## 本次审查结论

已读取全部 38 个已安装分发包可找到的许可及相关声明。直接运行依赖为 MCP 与 zstandard；其余含传递依赖、开发测试工具和 pip 安装工具。包内可能另含第三方通知，例如 pywin32 与 pip 的嵌入组件；不能只看顶层许可标识就认定所有内容采用相同许可。

本次未发现要求将独立项目整体改为其他许可证的已确认冲突；这是“不随项目捆绑第三方实现”的源码发布边界结论，不是对所有打包方式的法律保证。MPL 组件的受覆盖文件、Apache 的适用 NOTICE、BSD/MIT/PSF 的版权与许可要求仍分别有效。未修改或复制依赖代码进入项目源码。

若未来发布可执行文件、Docker 镜像、离线安装包、依赖源码或修改第三方组件，必须重新核对实际包含文件、许可文本、NOTICE 和对应源码义务，不能沿用本报告作为打包授权。
