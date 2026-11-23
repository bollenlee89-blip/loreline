<div align="center">

[English](../README.md) · [简体中文](README.zh-CN.md) · [繁體中文](README.zh-TW.md) · [日本語](README.ja.md) · [한국어](README.ko.md) · [Español](README.es.md) · [Français](README.fr.md) · **Deutsch** · [Português](README.pt-BR.md) · [Русский](README.ru.md)

# loreline

### `git blame` sagt dir, **wer**. `loreline` sagt dir, **warum**.

Ein Local-first-Agent, der jedes git-Repository in eine lebendige Wissensdatenbank verwandelt.<br>Zeig auf eine beliebige Zeile, und er nennt dir die Entscheidung, den Pull Request, die Diskussion und die Menschen dahinter.

[![CI](https://github.com/bollenlee89-blip/loreline/actions/workflows/ci.yml/badge.svg)](https://github.com/bollenlee89-blip/loreline/actions/workflows/ci.yml)
![Python](https://img.shields.io/badge/python-3.9%2B-blue)
![Dependencies](https://img.shields.io/badge/dependencies-0-brightgreen)
![License](https://img.shields.io/badge/license-MIT-green)

<img src="../docs/screenshot.jpg" alt="loreline" width="100%">

<sub>Die Web-Oberfläche (<code>loreline serve</code>) auf einem echten Open-Source-Repository. Den Text unter „Why it exists“ schreibt das LLM, das du anbindest.</sub>

</div>

---

## Warum?

Jede Codebasis ist voller Zeilen, die falsch aussehen, aber einen Grund haben: ein `sleep(0.3)`, drei Wiederholungsversuche, ein seltsamer Sonderfall für einen Kunden. Der Grund steckt in einer PR-Beschreibung von 2021, einem Review-Kommentar, einem Slack-Thread oder im Kopf einer Person. Findet ihn niemand, traut sich entweder keiner mehr an den Code, oder jemand „räumt auf“ und bringt den alten Bug zurück.

`loreline` verbindet jede Codezeile mit der Geschichte dahinter:

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

## Funktionen

- **`why` für jede Zeile, Funktion oder Datei.** Verfolgt die Zeile mit `git blame -w -M -C` und `git log -L` durch die Historie und überspringt Verschiebungen und reine Whitespace-Änderungen (inklusive `.git-blame-ignore-revs`).
- **Findet den Pull Request, auch offline.** Liest PR-Nummern aus Merge- und Squash-Commits und geht zurück bis zu dem Merge, der einen Commit eingebracht hat. Mit einem GitHub-Token holt es zusätzlich PR-Beschreibung, Review-Kommentare und verknüpfte Issues.
- **Chat gehört zur Historie.** Importiere Slack- und Discord-Exporte, JSONL oder Textnotizen. Nachrichten, die einen Commit, einen PR oder eine Datei erwähnen, werden automatisch mit dem Code verknüpft.
- **Frag die Historie.** `loreline ask "why did we drop Redis?"` durchsucht Commits, PRs, Issues und Chat (SQLite FTS5) und antwortet mit Quellenangaben.
- **Immer aktuell.** `loreline init` installiert git-Hooks, damit der Index bei jedem Commit, Merge und Rebase aktualisiert wird. Wer Polling bevorzugt, nimmt `loreline watch`.
- **Wissenskarte.** `loreline map -o LORE.md` schreibt pro Datei eine Zeile, warum sie existiert. Pro Datei gecacht und nur neu erzeugt, wenn sich die Datei ändert.
- **Funktioniert mit jedem LLM, oder ganz ohne.** Ollama, LM Studio, llama.cpp, vLLM, jede OpenAI-kompatible API, Anthropic Claude. Ohne LLM bekommst du trotzdem die komplette Beweiskette.
- **Passt in deinen Coding-Agenten.** `loreline mcp` ist ein MCP-Server, damit Claude Code, Cursor, Windsurf, Zed und andere fragen können „warum steht das hier?“, bevor sie etwas löschen.
- **Local-first und standardmäßig privat.** Alles liegt in `.git/loreline/`. Nichts verlässt deinen Rechner, außer du nutzt ein gehostetes LLM, und Autoren-E-Mails werden aus Prompts entfernt.
- **Keine Abhängigkeiten.** Nur die Python-Standardbibliothek und `git`. In Sekunden installiert.

## Installation

Ein Befehl, mit dem Tool, das du schon hast:

```bash
pipx install git+https://github.com/bollenlee89-blip/loreline
# or
uv tool install git+https://github.com/bollenlee89-blip/loreline
# or
curl -fsSL https://raw.githubusercontent.com/bollenlee89-blip/loreline/main/install.sh | sh
```

Benötigt Python 3.9+ und git. Zusätzlich wird ein `git-why`-Befehl installiert, also funktioniert auch `git why file.py:42`.

## Schnellstart

```bash
cd your-repo
loreline init                       # index history + install auto-update hooks
loreline why src/server.py:120      # why does this line exist?
loreline why src/server.py:connect  # ...or this function?
loreline ask "why do we pin protobuf to 3.20?"
loreline serve                      # web UI at http://localhost:7777
```

### Ein LLM anbinden (optional)

`loreline` wählt automatisch: zuerst ein laufendes **Ollama**, dann `ANTHROPIC_API_KEY`, dann `OPENAI_API_KEY`. Explizit festlegen:

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

Mit `--global` gilt eine Einstellung für alle Repositories. `loreline doctor` prüft dein Setup.

### Pull-Request-Kontext (optional)

Bei GitHub-Repositories nutzt `loreline` `GITHUB_TOKEN`, `GH_TOKEN` oder deinen `gh auth`-Login, um PR-Beschreibungen, Reviews und verknüpfte Issues zu holen, und cacht sie lokal. Ohne Token findet es PR-Nummern trotzdem in der Historie.

### Team-Chat (optional)

```bash
loreline import ./slack-export/          # Slack workspace export folder
loreline import discord-channel.json     # DiscordChatExporter JSON
loreline import decisions.md notes.txt   # meeting notes, ADRs, "date name: message" logs
loreline import messages.jsonl           # {"author","date","text","channel"} per line
```

### Aus Claude Code, Cursor und anderen Agenten nutzen

```bash
claude mcp add loreline -- loreline mcp
```

Für Cursor, Windsurf oder andere MCP-Clients einen Server mit dem Befehl `loreline` und den Argumenten `["mcp"]` hinzufügen. Agenten bekommen zwei Tools: `loreline_why` und `loreline_ask`.

## Befehle

| Befehl | Funktion |
| --- | --- |
| `loreline init` | Repo indexieren und git-Hooks für automatische Updates installieren |
| `loreline why <path>[:line\|:symbol]` | Erklärt, warum eine Zeile, Funktion oder Datei existiert |
| `loreline ask "<question>"` | Beantwortet Fragen aus der Projekthistorie, mit Quellen |
| `loreline map [-o LORE.md]` | Schreibt eine Wissenskarte: warum jede Datei existiert |
| `loreline serve` | Lokale Web-Oberfläche: Dateien durchsuchen, auf jede Zeile klicken |
| `loreline import <path...>` | Slack, Discord, JSONL oder Textnotizen importieren |
| `loreline mcp` | Als MCP-Server für Coding-Agenten laufen |
| `loreline index` / `watch` / `hooks` | Manuelles Indexieren, Polling-Watcher, Hook-Verwaltung |
| `loreline config show\|set` / `doctor` | Konfiguration und Diagnose |

## So funktioniert es

```
 git history ──┐
 PRs/reviews ──┼──► index (.git/loreline/lore.db, SQLite + FTS5) ──► evidence pack ──► LLM (optional) ──► answer with citations
 issues ───────┤        ▲ updated by git hooks / watch                   ▲
 chat/notes ───┘        └──────────────────────────────────── blame + git log -L for the line you asked about
```

1. **Indexieren:** Commits, geänderte Dateien, PR-Nummern, PR-Diskussionen, verknüpfte Issues und Chat-Nachrichten landen in einer lokalen SQLite-Datenbank mit Volltextsuche.
2. **Verfolgen:** Für die gefragte Zeile findet `git blame` den Commit, der sie eingeführt hat, und `git log -L` jeden späteren Commit, der sie geändert hat.
3. **Verknüpfen:** Jeder Commit wird seinem PR zugeordnet (über die Nachricht, den Merge-Commit oder die GitHub-API), der PR seinen Issues, Reviews und Chats.
4. **Erklären:** Die Belege werden direkt angezeigt oder an dein LLM übergeben, mit der strikten Anweisung, jede Aussage zu belegen und nichts zu erfinden.

## Datenschutz

- Die Datenbank liegt in `.git/`, wird also nie committet und taucht nie im Arbeitsverzeichnis auf.
- Die Web-Oberfläche lauscht nur auf `127.0.0.1` und lehnt Anfragen für andere Hostnamen ab, was DNS-Rebinding-Angriffe blockiert.
- Mit einem lokalen Modell (Ollama, llama.cpp…) verlässt nichts deinen Rechner.
- Autoren-E-Mails werden aus allem entfernt, was an ein LLM geht (`privacy.redact_emails`, standardmäßig an).

## Roadmap

- [ ] Merge Requests für GitLab / Gitea / Bitbucket
- [ ] Erweiterungen für VS Code und JetBrains (über eine Zeile hovern → why)
- [ ] Embedding-Suche zusätzlich zu FTS5
- [ ] „Veralteter Grund“-Warnungen: wenn der Grund für eine Zeile nicht mehr gilt
- [ ] Teilbare `LORE.md`-Karten, von der CI erzeugt

Ideen und PRs sind sehr willkommen. Siehe [CONTRIBUTING.md](../CONTRIBUTING.md).

## Lizenz

[MIT](../LICENSE)
