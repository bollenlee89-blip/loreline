<div align="center">

[English](../README.md) · [简体中文](README.zh-CN.md) · [繁體中文](README.zh-TW.md) · **日本語** · [한국어](README.ko.md) · [Español](README.es.md) · [Français](README.fr.md) · [Deutsch](README.de.md) · [Português](README.pt-BR.md) · [Русский](README.ru.md)

# loreline

### `git blame` は**誰が**書いたかを教えてくれる。`loreline` は**なぜ**かを教えてくれる。

あらゆる git リポジトリを、常に最新の「ナレッジベース」に変えるローカルファーストのエージェント。<br>任意の行を指すだけで、その背景にある意思決定、プルリクエスト、議論、関わった人を教えてくれます。

[![CI](https://github.com/bollenlee89-blip/loreline/actions/workflows/ci.yml/badge.svg)](https://github.com/bollenlee89-blip/loreline/actions/workflows/ci.yml)
![Python](https://img.shields.io/badge/python-3.9%2B-blue)
![Dependencies](https://img.shields.io/badge/dependencies-0-brightgreen)
![License](https://img.shields.io/badge/license-MIT-green)

<img src="../docs/screenshot.jpg" alt="loreline" width="100%">

<sub>実際のオープンソースリポジトリでの Web UI（<code>loreline serve</code>）。「Why it exists」の文章は接続した LLM が書きます。</sub>

</div>

---

## なぜ必要？

どのコードベースにも、一見おかしいけれど理由があるコードがあります。`sleep(0.3)`、リトライ回数 3、特定の顧客だけの妙な分岐。その理由は 2021 年の PR の説明文、レビューコメント、Slack のスレッド、あるいは誰かの頭の中にしかありません。理由が見つからないと、誰も触れずに放置されるか、「きれいにした」結果、昔のバグが復活します。

`loreline` はコードの各行を、その背景にあるストーリーと結びつけます：

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

## 機能

- **どの行・関数・ファイルにも `why`。** `git blame -w -M -C` と `git log -L` で行の履歴をたどり、移動や空白だけの変更はスキップします（`.git-blame-ignore-revs` にも対応）。
- **オフラインでも PR を特定。** マージコミットや squash コミットから PR 番号を読み取り、そのコミットを取り込んだマージまでさかのぼります。GitHub トークンがあれば、PR の説明、レビューコメント、関連 issue も取得します。
- **チャットも記録の一部。** Slack・Discord のエクスポート、JSONL、テキストのメモを取り込めます。コミット、PR、ファイルに言及したメッセージは自動でそのコードに紐づきます。
- **履歴に質問できる。** `loreline ask "why did we drop Redis?"` はコミット・PR・issue・チャットを検索し（SQLite FTS5）、出典付きで回答します。
- **常に最新。** `loreline init` が git hooks を入れるので、コミット・マージ・リベースのたびにインデックスが更新されます。ポーリングがよければ `loreline watch` も使えます。
- **ナレッジマップ。** `loreline map -o LORE.md` で各ファイルが「なぜ存在するか」を 1 行ずつ書き出します。ファイル単位でキャッシュし、変更されたファイルだけ再生成します。
- **どんな LLM でも、なしでも。** Ollama、LM Studio、llama.cpp、vLLM、OpenAI 互換 API、Anthropic Claude。LLM なしでも証拠の一覧はすべて見られます。
- **コーディングエージェントと連携。** `loreline mcp` は MCP サーバーなので、Claude Code、Cursor、Windsurf、Zed などがコードを消す前に「これはなぜここに？」と聞けます。
- **ローカルファースト、デフォルトでプライベート。** データはすべて `.git/loreline/` に保存。ホスト型 LLM を使わない限り外部には何も送られず、LLM へのプロンプトから作者のメールアドレスは除去されます。
- **依存ゼロ。** Python 標準ライブラリと `git` だけ。数秒でインストールできます。

## インストール

お手持ちのツールで、コマンド 1 つ：

```bash
pipx install git+https://github.com/bollenlee89-blip/loreline
# or
uv tool install git+https://github.com/bollenlee89-blip/loreline
# or
curl -fsSL https://raw.githubusercontent.com/bollenlee89-blip/loreline/main/install.sh | sh
```

Python 3.9 以上と git が必要です。`git-why` コマンドも入るので、`git why file.py:42` も使えます。

## クイックスタート

```bash
cd your-repo
loreline init                       # index history + install auto-update hooks
loreline why src/server.py:120      # why does this line exist?
loreline why src/server.py:connect  # ...or this function?
loreline ask "why do we pin protobuf to 3.20?"
loreline serve                      # web UI at http://localhost:7777
```

### LLM を接続する（任意）

`loreline` は自動で選びます：起動中の **Ollama** → `ANTHROPIC_API_KEY` → `OPENAI_API_KEY` の順。明示的に指定するには：

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

`--global` を付けると全リポジトリ共通の設定になります。`loreline doctor` で設定を確認できます。

### プルリクエストの文脈（任意）

GitHub のリポジトリでは、`GITHUB_TOKEN`、`GH_TOKEN`、または `gh auth` のログインを使って PR の説明、レビュー、関連 issue を取得し、ローカルにキャッシュします。トークンがなくても履歴から PR 番号は特定できます。

### チームチャット（任意）

```bash
loreline import ./slack-export/          # Slack workspace export folder
loreline import discord-channel.json     # DiscordChatExporter JSON
loreline import decisions.md notes.txt   # meeting notes, ADRs, "date name: message" logs
loreline import messages.jsonl           # {"author","date","text","channel"} per line
```

### Claude Code・Cursor などのエージェントから使う

```bash
claude mcp add loreline -- loreline mcp
```

Cursor、Windsurf などの MCP クライアントでは、コマンド `loreline`、引数 `["mcp"]` のサーバーを追加してください。エージェントは `loreline_why` と `loreline_ask` の 2 つのツールを使えるようになります。

## コマンド

| コマンド | 説明 |
| --- | --- |
| `loreline init` | リポジトリをインデックスし、自動更新用の git hooks を入れる |
| `loreline why <path>[:line\|:symbol]` | 行・関数・ファイルがなぜ存在するかを説明する |
| `loreline ask "<question>"` | プロジェクトの履歴から出典付きで質問に答える |
| `loreline map [-o LORE.md]` | 全ファイルの存在理由をまとめたナレッジマップを書き出す |
| `loreline serve` | ローカル Web UI：ファイルを見て任意の行をクリック |
| `loreline import <path...>` | Slack・Discord・JSONL・テキストのメモを取り込む |
| `loreline mcp` | コーディングエージェント向け MCP サーバーとして動かす |
| `loreline index` / `watch` / `hooks` | 手動インデックス、ポーリング監視、hooks の管理 |
| `loreline config show\|set` / `doctor` | 設定とヘルスチェック |

## 仕組み

```
 git history ──┐
 PRs/reviews ──┼──► index (.git/loreline/lore.db, SQLite + FTS5) ──► evidence pack ──► LLM (optional) ──► answer with citations
 issues ───────┤        ▲ updated by git hooks / watch                   ▲
 chat/notes ───┘        └──────────────────────────────────── blame + git log -L for the line you asked about
```

1. **インデックス：** コミット、変更ファイル、PR 番号、PR の議論、関連 issue、チャットを、全文検索付きのローカル SQLite に保存します。
2. **追跡：** 対象の行について、`git blame` が導入したコミットを、`git log -L` がその後に変更したすべてのコミットを見つけます。
3. **関連付け：** 各コミットを PR（コミットメッセージ、マージコミット、または GitHub API から）に、PR を issue・レビュー・チャットに結びつけます。
4. **説明：** 証拠をそのまま表示するか、すべての主張に出典を付け事実を作らないよう厳しく指示したうえで LLM に渡します。

## プライバシー

- データベースは `.git/` の中にあるので、コミットされることも作業ツリーに現れることもありません。
- Web UI は `127.0.0.1` にのみバインドし、他のホスト名へのリクエストを拒否して DNS リバインディング攻撃を防ぎます。
- ローカルモデル（Ollama、llama.cpp など）なら、何もマシンの外に出ません。
- LLM に送る内容から作者のメールアドレスを除去します（`privacy.redact_emails`、デフォルトで有効）。

## ロードマップ

- [ ] GitLab / Gitea / Bitbucket のマージリクエスト対応
- [ ] VS Code・JetBrains 拡張（行にホバー → why）
- [ ] FTS5 に加えて埋め込み検索
- [ ] 「理由の期限切れ」アラート：行の存在理由が成り立たなくなったら通知
- [ ] CI がコミットする共有用 `LORE.md` マップ

アイデアや PR を大歓迎します。[CONTRIBUTING.md](../CONTRIBUTING.md) をご覧ください。

## ライセンス

[MIT](../LICENSE)
