# a13n for AstrBot

[English](README.md)

让 AstrBot 的文本聊天由现有 [a13n Service](https://a13n.converge.ai/docs/a13n-service/) Agent 执行。插件在 AstrBot 进程内启动一个本地 HTTP 接口，AstrBot 内置的 Dify Chat Runner 调用该接口，插件再把消息转发给 a13n。安装一个插件后，即可在 AstrBot WebUI 完成配置。

## 使用前提

- AstrBot 4.29.4 和 Python 3.12 或更新版本。插件面向从 4.29.4 开始的 AstrBot 4.29 系列。
- AstrBot 能访问的 a13n Service，且其 `/api/v1` 提供 Threads、Inbox 和 Runs 接口。
- 一个返回文本的 Agent，以及对应工作区的 API Key。密钥所属身份需要 `read` 和 `run` 权限。

## 安装与配置

1. 打开 AstrBot WebUI 的「扩展 → 插件」。如果 AstrBot 能访问此仓库，可以通过 URL 安装，也可以上传插件目录的 ZIP。私有仓库可先登录 GitHub 下载 ZIP，再在 WebUI 上传。
2. 打开插件配置，填写下表中的字段，保存后重载插件。

   | 配置项 | 填写内容 |
   | --- | --- |
   | `service_url` | a13n Service 地址，省略末尾的 `/api/v1`。AstrBot 在 Docker 内运行时，请填写容器能访问的地址。 |
   | `service_api_key` | a13n 工作区 API Key。 |
   | `agent_id` | 用来执行聊天的 a13n Agent ID。 |
   | `bridge_key` | 单独生成的本地访问密钥，至少 24 位 ASCII 字母或数字。可用 `python -c "import secrets; print(secrets.token_hex(24))"` 生成。 |
   | `port` | 本地 HTTP 端口，默认 `18767`。 |
   | `timeout_seconds` | 插件等待结果的最长时间，包含排队时间，默认 `90` 秒。 |

3. 在机器人使用的配置文件中打开「AI → 更多操作 → 更换执行方式」，选择 **Dify** 并启用 AI。应用类型选 **Chat**，API Base 填 `http://127.0.0.1:18767/v1`（如修改了端口，请同步调整），Dify API Key 填插件的 **`bridge_key`**。Dify 超时时间要大于插件超时，例如 **120 秒**。保存配置。如果 AstrBot 使用 HTTP 代理，把 `127.0.0.1` 加到 AstrBot 进程的 `NO_PROXY` 中。
4. 像平常一样私聊或 `@机器人`，再发送一条追问。两轮应出现在同一个 a13n Thread 下。发送 AstrBot 的 `/reset` 后，下一条消息会开启新的 Thread。

## 会话与当前范围

插件将 Dify 会话 ID 与 a13n Thread ID 的映射保存在 AstrBot 的插件数据目录。会话范围沿用 AstrBot 传给 Dify 的会话 ID。用于群聊前，请在 AstrBot 里配置需要的会话隔离方式。保留插件数据目录即可在更新或重启后续聊。

首版支持文本，Run 完成后通过 Dify SSE 返回最终回复。附件、实时文本增量、审批及客户端工具交互暂未接入。聊天超时或断开只结束本地等待，远端 Run 可能继续执行。

| 现象 | 检查项 |
| --- | --- |
| 连接被拒绝 | 重载插件，查看启动日志，确认本地端口与 Dify API Base 一致。 |
| 本地访问密钥无效 | Dify API Key 应填写插件的 `bridge_key`，a13n 工作区密钥填在插件配置中。 |
| a13n 拒绝访问 | 确认工作区密钥具备读取和运行所选 Agent 的权限。 |
| 会话不可用 | 更换 Service、Agent 或插件数据目录后，使用 `/reset` 开启新会话。 |
| 等待输入或超时 | 在 a13n 中打开对应 Run，查看状态并处理待完成的交互。 |

## 验证

已使用 Python 3.12 下的 AstrBot 4.29.4 内置 Dify Runner，与使用脚本模型的本地 a13n Service 联调。验证覆盖首轮回复、插件重载后的续聊，以及清除 Dify 会话 ID 后创建新 Thread。自动化测试还覆盖本地鉴权、会话隔离和复用幂等键重试提交。

```sh
python -m pip install -r requirements.txt
python -m unittest discover -s tests -v
```

## 原生 Runner 路线图

AstrBot 目前将此接入显示为 **Dify**。等 [Custom Agent Runner #9942](https://github.com/AstrBotDevs/AstrBot/issues/9942) 的插件注册接口正式发布后，计划通过同一个插件注册 **a13n** 执行方式。原生 Runner 将复用 a13n 客户端，并在会话标识可映射时沿用已有 Thread。届时会提供配置切换和会话迁移说明。

## 许可证

GNU Affero General Public License v3.0。本仓库从 [AstrBot 插件模板](https://github.com/Soulter/helloworld) 创建。
