<div align="center">

[English](../README.md) · [简体中文](README.zh-CN.md) · **繁體中文** · [日本語](README.ja.md) · [한국어](README.ko.md) · [Español](README.es.md) · [Français](README.fr.md) · [Deutsch](README.de.md) · [Português](README.pt-BR.md) · [Русский](README.ru.md)

# loreline

### `git blame` 告訴你是**誰**寫的，`loreline` 告訴你**為什麼**。

一個本機優先的智慧代理，把任何 git 儲存庫變成持續更新的知識庫。<br>指向任意一行程式碼，它就能告訴你背後的決策、拉取請求（PR）、討論與相關的人。

[![CI](https://github.com/bollenlee89-blip/loreline/actions/workflows/ci.yml/badge.svg)](https://github.com/bollenlee89-blip/loreline/actions/workflows/ci.yml)
![Python](https://img.shields.io/badge/python-3.9%2B-blue)
![Dependencies](https://img.shields.io/badge/dependencies-0-brightgreen)
![License](https://img.shields.io/badge/license-MIT-green)

<img src="../docs/screenshot.jpg" alt="loreline" width="100%">

<sub>真實開源儲存庫上的 Web 介面（<code>loreline serve</code>）。「Why it exists」一欄的文字由你接入的 LLM 產生。</sub>

</div>

---

## 為什麼需要它？

每個程式碼庫裡都有一些看起來怪怪的、但其實有原因的程式碼：一個 `sleep(0.3)`、一個重試 3 次、為某個客戶寫的奇怪特例。原因往往藏在 2021 年的某個 PR 描述、某則程式碼審查意見、某段 Slack 討論，或某個人的腦袋裡。找不到原因時，大家要麼永遠不敢動它，要麼「順手清理」然後把舊 bug 帶回來。

`loreline` 把每一行程式碼和它背後的故事連結起來：

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

- **任意行、函式或檔案都能問 `why`。** 透過 `git blame -w -M -C` 與 `git log -L` 追蹤這一行的完整歷史，略過程式碼搬移與空白變更（並遵守 `.git-blame-ignore-revs`）。
- **離線也能找到 PR。** 從合併提交與 squash 提交讀取 PR 編號，並回溯到把某個提交帶進來的那次合併。設定 GitHub token 後，還會抓取 PR 描述、審查意見與關聯 issue。
- **聊天紀錄也是檔案的一部分。** 匯入 Slack 匯出、Discord 匯出、JSONL 或純文字筆記。提到某個提交、PR 或檔案的訊息會自動關聯到對應程式碼。
- **向歷史提問。** `loreline ask "why did we drop Redis?"` 會搜尋提交、PR、issue 與聊天（SQLite FTS5），並給出附引用的回答。
- **永遠是最新的。** `loreline init` 會安裝 git hooks，每次提交、合併、rebase 後自動更新索引。也可以用 `loreline watch` 輪詢。
- **知識地圖。** `loreline map -o LORE.md` 為每個檔案寫一句「它為什麼存在」。依檔案快取，只有檔案變動時才重新產生。
- **支援任何 LLM，也可以不用。** Ollama、LM Studio、llama.cpp、vLLM、任何 OpenAI 相容 API、Anthropic Claude。不接 LLM 也能看到完整的證據鏈。
- **接入你的程式設計代理。** `loreline mcp` 是一個 MCP 伺服器，Claude Code、Cursor、Windsurf、Zed 等可以在刪除程式碼前先問一句「這為什麼在這裡？」。
- **本機優先，預設私密。** 所有資料都在 `.git/loreline/` 裡。除非你接入雲端 LLM，否則沒有任何資料離開你的電腦；送給 LLM 的內容會自動隱藏作者電子郵件。
- **零相依套件。** 純 Python 標準函式庫 + `git`，幾秒鐘裝好。

## 安裝

一行指令，用你已經有的工具即可：

```bash
pipx install git+https://github.com/bollenlee89-blip/loreline
# or
uv tool install git+https://github.com/bollenlee89-blip/loreline
# or
curl -fsSL https://raw.githubusercontent.com/bollenlee89-blip/loreline/main/install.sh | sh
```

需要 Python 3.9+ 與 git。同時會安裝 `git-why` 指令，所以 `git why file.py:42` 也能用。

## 快速開始

```bash
cd your-repo
loreline init                       # index history + install auto-update hooks
loreline why src/server.py:120      # why does this line exist?
loreline why src/server.py:connect  # ...or this function?
loreline ask "why do we pin protobuf to 3.20?"
loreline serve                      # web UI at http://localhost:7777
```

### 接入 LLM（選用）

`loreline` 會自動選擇：優先使用執行中的 **Ollama**，其次 `ANTHROPIC_API_KEY`，再來是 `OPENAI_API_KEY`。也可以手動指定：

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

加上 `--global` 可讓設定套用到所有儲存庫。執行 `loreline doctor` 檢查設定。

### PR 脈絡（選用）

對於 GitHub 儲存庫，`loreline` 會使用 `GITHUB_TOKEN`、`GH_TOKEN` 或 `gh auth` 登入來抓取 PR 描述、審查與關聯 issue，結果快取在本機。沒有 token 時依然能從歷史中辨識 PR 編號。

### 團隊聊天（選用）

```bash
loreline import ./slack-export/          # Slack workspace export folder
loreline import discord-channel.json     # DiscordChatExporter JSON
loreline import decisions.md notes.txt   # meeting notes, ADRs, "date name: message" logs
loreline import messages.jsonl           # {"author","date","text","channel"} per line
```

### 在 Claude Code、Cursor 等代理中使用

```bash
claude mcp add loreline -- loreline mcp
```

Cursor、Windsurf 或其他 MCP 用戶端：新增一個指令為 `loreline`、參數為 `["mcp"]` 的伺服器。代理會獲得兩個工具：`loreline_why` 與 `loreline_ask`。

## 指令

| 指令 | 用途 |
| --- | --- |
| `loreline init` | 索引儲存庫並安裝自動更新的 git hooks |
| `loreline why <path>[:line\|:symbol]` | 解釋一行、一個函式或一個檔案為什麼存在 |
| `loreline ask "<question>"` | 根據專案歷史回答問題，並附上引用 |
| `loreline map [-o LORE.md]` | 產生知識地圖：每個檔案為什麼存在 |
| `loreline serve` | 本機 Web 介面：瀏覽檔案，點擊任意一行 |
| `loreline import <path...>` | 匯入 Slack、Discord、JSONL 或文字筆記 |
| `loreline mcp` | 作為 MCP 伺服器供程式設計代理使用 |
| `loreline index` / `watch` / `hooks` | 手動索引、輪詢監看、管理 hooks |
| `loreline config show\|set` / `doctor` | 設定與健康檢查 |

## 運作原理

```
 git history ──┐
 PRs/reviews ──┼──► index (.git/loreline/lore.db, SQLite + FTS5) ──► evidence pack ──► LLM (optional) ──► answer with citations
 issues ───────┤        ▲ updated by git hooks / watch                   ▲
 chat/notes ───┘        └──────────────────────────────────── blame + git log -L for the line you asked about
```

1. **索引：** 提交、變動的檔案、PR 編號、PR 討論、關聯 issue 與聊天訊息存入本機 SQLite 資料庫，並建立全文索引。
2. **追蹤：** 對你詢問的那一行，`git blame` 找出引入它的提交，`git log -L` 找出之後每一次修改它的提交。
3. **關聯：** 每個提交連結到它的 PR（來自提交訊息、合併提交或 GitHub API），PR 再連結到 issue、審查意見與聊天。
4. **解釋：** 直接呈現這些證據，或交給你的 LLM，並嚴格要求它為每個論點標註引用、絕不捏造事實。

## 隱私

- 資料庫位於 `.git/` 內部，永遠不會被提交，也不會出現在工作目錄。
- Web 介面只綁定 `127.0.0.1`，並拒絕其他主機名稱的請求，可防禦 DNS rebinding 攻擊。
- 使用本機模型（Ollama、llama.cpp 等）時，沒有任何資料離開你的電腦。
- 送給 LLM 的內容會隱藏作者電子郵件（`privacy.redact_emails`，預設開啟）。

## 路線圖

- [ ] GitLab / Gitea / Bitbucket 合併請求支援
- [ ] VS Code 與 JetBrains 擴充套件（滑過一行 → why）
- [ ] 在 FTS5 之外加入向量搜尋
- [ ] 「理由過期」提醒：當某行程式碼存在的理由不再成立時提醒你
- [ ] 由 CI 自動提交可分享的 `LORE.md` 知識地圖

非常歡迎想法與 PR，請參閱 [CONTRIBUTING.md](../CONTRIBUTING.md)。

## 授權條款

[MIT](../LICENSE)
