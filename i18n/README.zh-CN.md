<div align="center">

[English](../README.md) · **简体中文** · [繁體中文](README.zh-TW.md) · [日本語](README.ja.md) · [한국어](README.ko.md) · [Español](README.es.md) · [Français](README.fr.md) · [Deutsch](README.de.md) · [Português](README.pt-BR.md) · [Русский](README.ru.md)

# loreline

### `git blame` 告诉你是**谁**写的，`loreline` 告诉你**为什么**。

一个本地优先的智能体，把任何 git 仓库变成一个持续更新的知识库。<br>指向任意一行代码，它就能告诉你背后的决策、拉取请求（PR）、讨论和相关的人。

[![CI](https://github.com/bollenlee89-blip/loreline/actions/workflows/ci.yml/badge.svg)](https://github.com/bollenlee89-blip/loreline/actions/workflows/ci.yml)
![Python](https://img.shields.io/badge/python-3.9%2B-blue)
![Dependencies](https://img.shields.io/badge/dependencies-0-brightgreen)
![License](https://img.shields.io/badge/license-MIT-green)

<img src="../docs/screenshot.jpg" alt="loreline" width="100%">

<sub>真实开源仓库上的 Web 界面（<code>loreline serve</code>）。“Why it exists” 一栏的文字由你接入的 LLM 生成。</sub>

</div>

---

## 为什么需要它？

每个代码库里都有一些看起来不对劲、但其实有原因的代码：一个 `sleep(0.3)`、一个重试 3 次、为某个客户写的奇怪特例。原因往往藏在 2021 年的某个 PR 描述、某条代码评审意见、某段 Slack 讨论，或者某个人的脑子里。找不到原因时，大家要么永远不敢动它，要么“顺手清理”然后把旧 bug 重新引入。

`loreline` 把每一行代码和它背后的故事连接起来：

```console
$ loreline why app/upload.py:42

⟡ app/upload.py:42
  │     for attempt in range(3):  # S3 drops ~1% of PUTs

Why it exists
  Uploads are retried three times because S3 intermittently returned 503s under load
  [C1]. The fix came from issue #7 ("Uploads fail randomly") and was merged in [PR#42],
  where a reviewer noted 3 matches the AWS SDK default.
  Decision: retry failed uploads up to 3 times instead of failing the request.

[C1] introduced by 9f2c1e7a Retry uploads three times
     Ada Lovelace · 2024-03-02
     PR #42 Retry flaky uploads  https://github.com/acme/app/pull/42
       issue #7 Uploads fail randomly
       💬 cy: 3 matches the SDK default, approving
```

## 功能

- **任意行、函数或文件都能问 `why`。** 通过 `git blame -w -M -C` 和 `git log -L` 追踪这一行的完整历史，跳过代码移动和空白改动（并遵守 `.git-blame-ignore-revs`）。
- **离线也能找到 PR。** 从合并提交和 squash 提交中读取 PR 编号，并回溯到把某个提交带进来的那次合并。配置 GitHub token 后，还会拉取 PR 描述、评审意见和关联 issue。
- **聊天记录也是档案的一部分。** 导入 Slack 导出、Discord 导出、JSONL 或纯文本笔记。提到某个提交、PR 或文件的消息会自动关联到对应代码。
- **向历史提问。** `loreline ask "why did we drop Redis?"` 会检索提交、PR、issue 和聊天（SQLite FTS5），并给出带引用的回答。
- **始终最新。** `loreline init` 会安装 git hooks，每次提交、合并、变基后自动更新索引。也可以用 `loreline watch` 轮询。
- **知识地图。** `loreline map -o LORE.md` 为每个文件写一句“它为什么存在”。按文件缓存，只有文件变化时才重新生成。
- **支持任何 LLM，也可以不用。** Ollama、LM Studio、llama.cpp、vLLM、任何 OpenAI 兼容 API、Anthropic Claude。不接 LLM 也能看到完整的证据链。
- **接入你的编程智能体。** `loreline mcp` 是一个 MCP 服务器，Claude Code、Cursor、Windsurf、Zed 等可以在删除代码前先问一句“这为什么在这里？”。
- **本地优先，默认私密。** 所有数据都在 `.git/loreline/` 里。除非你接入托管 LLM，否则不会有任何数据离开你的电脑；发送给 LLM 的内容会自动隐去作者邮箱。
- **零依赖。** 纯 Python 标准库 + `git`，几秒钟装好。

## 安装

一条命令，用你已经有的工具即可：

```bash
pipx install git+https://github.com/bollenlee89-blip/loreline
# or
uv tool install git+https://github.com/bollenlee89-blip/loreline
# or
curl -fsSL https://raw.githubusercontent.com/bollenlee89-blip/loreline/main/install.sh | sh
```

需要 Python 3.9+ 和 git。同时会安装 `git-why` 命令，所以 `git why file.py:42` 也能用。

## 快速上手

```bash
cd your-repo
loreline init                       # index history + install auto-update hooks
loreline why src/server.py:120      # why does this line exist?
loreline why src/server.py:connect  # ...or this function?
loreline ask "why do we pin protobuf to 3.20?"
loreline serve                      # web UI at http://localhost:7777
```

### 接入 LLM（可选）

`loreline` 会自动选择：优先使用正在运行的 **Ollama**，其次 `ANTHROPIC_API_KEY`，再次 `OPENAI_API_KEY`。也可以手动指定：

```bash
# Local, fully private
ollama pull qwen2.5-coder && loreline config set llm.provider ollama && loreline config set llm.model qwen2.5-coder

# Any OpenAI-compatible server (LM Studio, llama.cpp, vLLM, OpenRouter, Groq...)
loreline config set llm.provider openai
loreline config set llm.base_url http://localhost:1234/v1
loreline config set llm.model your-model

# Anthropic
export ANTHROPIC_API_KEY=...
```

加上 `--global` 可以让设置对所有仓库生效。运行 `loreline doctor` 检查配置。

### PR 上下文（可选）

对于 GitHub 仓库，`loreline` 会使用 `GITHUB_TOKEN`、`GH_TOKEN` 或 `gh auth` 登录来获取 PR 描述、评审和关联 issue，结果缓存在本地。没有 token 时依然能从历史中识别 PR 编号。

### 团队聊天（可选）

```bash
loreline import ./slack-export/          # Slack workspace export folder
loreline import discord-channel.json     # DiscordChatExporter JSON
loreline import decisions.md notes.txt   # meeting notes, ADRs, "date name: message" logs
loreline import messages.jsonl           # {"author","date","text","channel"} per line
```

### 在 Claude Code、Cursor 等智能体中使用

```bash
claude mcp add loreline -- loreline mcp
```

Cursor、Windsurf 或其他 MCP 客户端：添加一个命令为 `loreline`、参数为 `["mcp"]` 的服务器。智能体会获得两个工具：`loreline_why` 和 `loreline_ask`。

## 命令

| 命令 | 作用 |
| --- | --- |
| `loreline init` | 索引仓库并安装自动更新的 git hooks |
| `loreline why <path>[:line\|:symbol]` | 解释一行、一个函数或一个文件为什么存在 |
| `loreline ask "<question>"` | 根据项目历史回答问题，并附上引用 |
| `loreline map [-o LORE.md]` | 生成知识地图：每个文件为什么存在 |
| `loreline serve` | 本地 Web 界面：浏览文件，点击任意一行 |
| `loreline import <path...>` | 导入 Slack、Discord、JSONL 或文本笔记 |
| `loreline mcp` | 作为 MCP 服务器供编程智能体使用 |
| `loreline index` / `watch` / `hooks` | 手动索引、轮询监视、管理 hooks |
| `loreline config show\|set` / `doctor` | 配置与健康检查 |

## 工作原理

```
 git history ──┐
 PRs/reviews ──┼──► index (.git/loreline/lore.db, SQLite + FTS5) ──► evidence pack ──► LLM (optional) ──► answer with citations
 issues ───────┤        ▲ updated by git hooks / watch                   ▲
 chat/notes ───┘        └──────────────────────────────────── blame + git log -L for the line you asked about
```

1. **索引：** 提交、改动的文件、PR 编号、PR 讨论、关联 issue 和聊天消息存入本地 SQLite 数据库，并建立全文索引。
2. **追踪：** 对你询问的那一行，`git blame` 找到引入它的提交，`git log -L` 找到之后每一次修改它的提交。
3. **关联：** 每个提交关联到它的 PR（来自提交信息、合并提交或 GitHub API），PR 再关联到 issue、评审意见和聊天。
4. **解释：** 直接展示这些证据，或交给你的 LLM，并严格要求它为每个结论标注引用、绝不编造事实。

## 隐私

- 数据库位于 `.git/` 内部，永远不会被提交，也不会出现在工作区。
- Web 界面只绑定 `127.0.0.1`，并拒绝其他主机名的请求，可防御 DNS 重绑定攻击。
- 使用本地模型（Ollama、llama.cpp 等）时，没有任何数据离开你的电脑。
- 发送给 LLM 的内容会隐去作者邮箱（`privacy.redact_emails`，默认开启）。

## 路线图

- [ ] GitLab / Gitea / Bitbucket 合并请求支持
- [ ] VS Code 和 JetBrains 插件（悬停一行 → why）
- [ ] 在 FTS5 之外增加向量检索
- [ ] “理由过期”提醒：当某行代码存在的理由不再成立时提醒你
- [ ] 由 CI 自动提交可分享的 `LORE.md` 知识地图

非常欢迎想法和 PR，请参阅 [CONTRIBUTING.md](../CONTRIBUTING.md)。

## 许可证

[MIT](../LICENSE)
