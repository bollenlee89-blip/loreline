<div align="center">

**English** · [简体中文](i18n/README.zh-CN.md) · [繁體中文](i18n/README.zh-TW.md) · [日本語](i18n/README.ja.md) · [한국어](i18n/README.ko.md) · [Español](i18n/README.es.md) · [Français](i18n/README.fr.md) · [Deutsch](i18n/README.de.md) · [Português](i18n/README.pt-BR.md) · [Русский](i18n/README.ru.md)

# loreline

### `git blame` tells you **who**. `loreline` tells you **why**.

A local-first agent that turns any git repository into a living knowledge base.<br>
Point it at any line, and it tells you the decision, the pull request, the discussion and the people behind it.

[![CI](https://github.com/bollenlee89-blip/loreline/actions/workflows/ci.yml/badge.svg)](https://github.com/bollenlee89-blip/loreline/actions/workflows/ci.yml)
![Python](https://img.shields.io/badge/python-3.9%2B-blue)
![Dependencies](https://img.shields.io/badge/dependencies-0-brightgreen)
![License](https://img.shields.io/badge/license-MIT-green)
![Local first](https://img.shields.io/badge/local--first-private%20by%20default-8a63d2)

<img src="docs/screenshot.jpg" alt="loreline web UI: click a line, see why it exists" width="100%">

<sub>The web UI (<code>loreline serve</code>) on a real open-source repo. The "Why it exists" text is written by whichever LLM you connect.</sub>

</div>

---

## Why?

Every codebase is full of lines that look wrong but are there for a reason: a `sleep(0.3)`, a retry count of 3, a weird special case for one customer. The reason lives in a PR description from 2021, a review comment, a Slack thread, or someone's head. When nobody can find it, people either leave the code alone forever or "clean it up" and reintroduce the bug.

`loreline` connects every line of code to the story behind it.

### A real example

Here is a line from [psf/requests](https://github.com/psf/requests), one of the most downloaded Python packages. It's a "special case" in the code that decides whether your password survives a redirect. Any reader might wonder whether it's safe to remove.

`git blame` tells you who and when:

```console
$ git blame -L 160,160 src/requests/sessions.py
857e9b7ac requests/sessions.py (Bruce Merry 2018-08-14 13:30:43 +0200 160)         # Special case: allow http -> https redirect when using the standard
```

`loreline` tells you why:

```console
$ loreline why src/requests/sessions.py:160 --no-llm

⟡ src/requests/sessions.py:160
  │         # Special case: allow http -> https redirect when using the standard

[C1] introduced by 857e9b7a Rework authorization stripping logic as discussed
     Bruce Merry · 2018-08-14
     The exception for http->https upgrade now requires the standard HTTP(S)
     ports to be used, either implicitly (no port specified) or explicitly.
     PR #4718 Strip Authorization header whenever root URL changes  https://github.com/psf/requests/pull/4718
       Previously the header was stripped only if the hostname changed, but in
       an https -> http redirect that can leak the credentials on the wire
       (#4716). Based on with RFC 7235 section 2.2, the header is now stripped
       if the "canonical root URL" (scheme+authority) has changed.
       Closes #4716.
       issue #4716 Should Authorization header be cleared in https -> http redirect?
       💬 nateprewitt: [requests/sessions.py] We may want to do the explicit check on scheme, hostname, and port here. Otherwise a ur
       💬 nateprewitt: [tests/test_requests.py] We should be explicit here and validate that `Authorization` is not in the request he

file: 200 commits · created 2011-08-15 by Tom Hogans · Ian Cordasco (29), Nate Prewitt (22), Cory Benfield (21), Kenneth Reitz (14)
often changes with: src/requests/models.py, src/requests/utils.py, src/requests/help.py, src/requests/auth.py, src/requests/adapters.py
```

That is the whole story in one screen. The line comes from a security fix: requests used to keep your `Authorization` header when an HTTPS site redirected to plain HTTP on the same host, which sent the credentials over the wire unencrypted ([#4716](https://github.com/psf/requests/issues/4716)). The fix in [PR #4718](https://github.com/psf/requests/pull/4718), later assigned CVE-2018-18074, strips the header whenever the origin changes. The http → https upgrade on standard ports is the one exception that maintainers kept on purpose, so existing users wouldn't break. Remove it and you break those users. Loosen it and you can reopen the leak.

This is real output from requests at commit `3c7baaa`, with PR details pulled from GitHub. Only the closing setup tip is left out. To reproduce it, clone requests, set `GITHUB_TOKEN`, then run `loreline init` and the command above. With an LLM connected, `loreline` also writes a short cited "Why it exists" summary above the evidence.

## Features

- **`why` for any line, function or file.** Follows the line through history with `git blame -w -M -C` and `git log -L`, skipping moves and whitespace noise (and honouring `.git-blame-ignore-revs`).
- **Finds the pull request, even offline.** It reads PR numbers from merge and squash commits and walks back to the merge that brought a commit in. With a GitHub token it also pulls the PR description, review comments and linked issues.
- **Chat is part of the record.** Import Slack exports, Discord exports, JSONL or plain notes. Messages that mention a commit, a PR or a file get linked to that code automatically.
- **Ask the history.** `loreline ask "why did we drop Redis?"` searches commits, PRs, issues and chat (SQLite FTS5) and answers with citations.
- **Always current.** `loreline init` installs git hooks so the index updates on every commit, merge and rebase. `loreline watch` is there too if you prefer polling.
- **Knowledge map.** `loreline map -o LORE.md` writes one line per file on why it exists. It's cached per file and only regenerated when that file changes.
- **Works with any LLM, or none.** Ollama, LM Studio, llama.cpp, vLLM, any OpenAI-compatible API, Anthropic Claude. With no LLM you still get the full evidence trail.
- **Plugs into your coding agent.** `loreline mcp` is an MCP server, so Claude Code, Cursor, Windsurf, Zed and others can ask "why is this here?" before they delete something.
- **Local-first and private by default.** Everything lives in `.git/loreline/`. Nothing leaves your machine unless you point it at a hosted LLM, and author emails are redacted from LLM prompts.
- **Zero dependencies.** Pure Python standard library plus `git`. Installs in seconds.

## Install

One command, using whichever tool you already have:

```bash
pipx install git+https://github.com/bollenlee89-blip/loreline
# or
uv tool install git+https://github.com/bollenlee89-blip/loreline
# or
curl -fsSL https://raw.githubusercontent.com/bollenlee89-blip/loreline/main/install.sh | sh
```

You need Python 3.9+ and git. This also installs a `git-why` command, so `git why file.py:42` works.

## Quick start

```bash
cd your-repo
loreline init                       # index history + install auto-update hooks
loreline why src/server.py:120      # why does this line exist?
loreline why src/server.py:connect  # ...or this function?
loreline ask "why do we pin protobuf to 3.20?"
loreline serve                      # web UI at http://localhost:7777
```

### Connect an LLM (optional)

`loreline` picks one automatically: a running **Ollama** first, then `ANTHROPIC_API_KEY`, then `OPENAI_API_KEY`. To choose explicitly:

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

Add `--global` to save a setting for all repositories. Run `loreline doctor` to check your setup.

### Pull request context (optional)

For GitHub repos, `loreline` uses `GITHUB_TOKEN`, `GH_TOKEN` or your `gh auth` login to fetch PR descriptions, reviews and linked issues. Results are cached locally. Without a token it still finds PR numbers from history.

### Team chat (optional)

```bash
loreline import ./slack-export/          # Slack workspace export folder
loreline import discord-channel.json     # DiscordChatExporter JSON
loreline import decisions.md notes.txt   # meeting notes, ADRs, "date name: message" logs
loreline import messages.jsonl           # {"author","date","text","channel"} per line
```

### Use it from Claude Code, Cursor and other agents

```bash
claude mcp add loreline -- loreline mcp
```

For Cursor, Windsurf or another MCP client, add a server with command `loreline` and args `["mcp"]`. Agents get two tools: `loreline_why` and `loreline_ask`.

## Commands

| Command | What it does |
| --- | --- |
| `loreline init` | Index the repo and install auto-update git hooks |
| `loreline why <path>[:line\|:symbol]` | Explain why a line, function or file exists (`--json`, `--no-llm`, `-v`, `--depth N`) |
| `loreline ask "<question>"` | Answer a question from the project's history, with citations |
| `loreline map [-o LORE.md]` | Write a knowledge map of why every file exists |
| `loreline serve` | Local web UI: browse files and click any line |
| `loreline import <path...>` | Import Slack, Discord, JSONL or text notes |
| `loreline mcp` | Run as an MCP server for coding agents |
| `loreline index` / `watch` / `hooks` | Manual indexing, polling watcher, hook management |
| `loreline config show\|set` / `doctor` | Configuration and health check |

## How it works

```
 git history ──┐
 PRs/reviews ──┼──► index (.git/loreline/lore.db, SQLite + FTS5) ──► evidence pack ──► LLM (optional) ──► answer with citations
 issues ───────┤        ▲ updated by git hooks / watch                   ▲
 chat/notes ───┘        └──────────────────────────────────── blame + git log -L for the line you asked about
```

1. **Index:** commits, touched files, PR numbers, PR discussions, linked issues and chat messages are stored in a local SQLite database with full-text search.
2. **Trace:** for the line you ask about, `git blame` finds the commit that introduced it and `git log -L` finds every later commit that changed it.
3. **Link:** each commit is tied to its PR (from the message, the merge commit, or the GitHub API), and the PR to its issues, review comments and chat.
4. **Explain:** that evidence is shown directly, or handed to your LLM with strict instructions to cite every claim and never invent facts.

## Privacy

- The database lives inside `.git/`, so it's never committed and never shows up in your working tree.
- The web UI binds to `127.0.0.1` and rejects requests for other hostnames, which blocks DNS-rebinding attacks.
- With a local model (Ollama, llama.cpp…) nothing leaves your machine.
- Author emails are redacted from anything sent to an LLM (`privacy.redact_emails`, on by default).

## Roadmap

- [ ] GitLab / Gitea / Bitbucket merge-request enrichment
- [ ] VS Code and JetBrains extensions (hover a line → why)
- [ ] Embedding search alongside FTS5
- [ ] "Stale reason" alerts: when the reason for a line no longer applies
- [ ] Shareable `LORE.md` maps committed by CI

Ideas and PRs are very welcome. See [CONTRIBUTING.md](CONTRIBUTING.md).

## License

[MIT](LICENSE)
