<div align="center">

[English](../README.md) · [简体中文](README.zh-CN.md) · [繁體中文](README.zh-TW.md) · [日本語](README.ja.md) · [한국어](README.ko.md) · [Español](README.es.md) · [Français](README.fr.md) · [Deutsch](README.de.md) · [Português](README.pt-BR.md) · **Русский**

# loreline

### `git blame` говорит **кто**. `loreline` говорит **почему**.

Local-first агент, который превращает любой git-репозиторий в живую базу знаний.<br>Укажите на любую строку, и он расскажет о решении, пул-реквесте, обсуждении и людях, которые за ней стоят.

[![CI](https://github.com/bollenlee89-blip/loreline/actions/workflows/ci.yml/badge.svg)](https://github.com/bollenlee89-blip/loreline/actions/workflows/ci.yml)
![Python](https://img.shields.io/badge/python-3.9%2B-blue)
![Dependencies](https://img.shields.io/badge/dependencies-0-brightgreen)
![License](https://img.shields.io/badge/license-MIT-green)

<img src="../docs/screenshot.jpg" alt="loreline" width="100%">

<sub>Веб-интерфейс (<code>loreline serve</code>) на реальном open source репозитории. Текст «Why it exists» пишет подключённая вами LLM.</sub>

</div>

---

## Зачем?

В любом коде полно строк, которые выглядят странно, но появились не просто так: `sleep(0.3)`, три повторные попытки, необычный особый случай для одного клиента. Причина спрятана в описании PR 2021 года, в комментарии на ревью, в ветке Slack или в чьей-то голове. Когда её никто не может найти, код либо боятся трогать, либо «чистят» и возвращают старый баг.

`loreline` связывает каждую строку кода с историей, которая за ней стоит:

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

## Возможности

- **`why` для любой строки, функции или файла.** Прослеживает строку по истории с помощью `git blame -w -M -C` и `git log -L`, пропуская перемещения и изменения пробелов (и учитывая `.git-blame-ignore-revs`).
- **Находит пул-реквест даже офлайн.** Читает номера PR из merge- и squash-коммитов и доходит до слияния, которое принесло коммит. С токеном GitHub также подтягивает описание PR, комментарии ревью и связанные issue.
- **Чат тоже часть истории.** Импортируйте экспорты Slack и Discord, JSONL или текстовые заметки. Сообщения, где упоминается коммит, PR или файл, автоматически связываются с этим кодом.
- **Спросите историю.** `loreline ask "why did we drop Redis?"` ищет по коммитам, PR, issue и чату (SQLite FTS5) и отвечает со ссылками на источники.
- **Всегда актуально.** `loreline init` ставит git-хуки, и индекс обновляется при каждом коммите, слиянии и ребейзе. Если удобнее опрос, есть `loreline watch`.
- **Карта знаний.** `loreline map -o LORE.md` пишет по одной строке на файл о том, зачем он существует. Кэшируется по файлам и пересоздаётся только при изменении файла.
- **Работает с любой LLM или без неё.** Ollama, LM Studio, llama.cpp, vLLM, любое OpenAI-совместимое API, Anthropic Claude. Без LLM вы всё равно видите всю цепочку доказательств.
- **Встраивается в вашего агента для кода.** `loreline mcp` это MCP-сервер, поэтому Claude Code, Cursor, Windsurf, Zed и другие могут спросить «зачем это здесь?» прежде чем что-то удалить.
- **Local-first и приватно по умолчанию.** Всё хранится в `.git/loreline/`. Ничего не покидает ваш компьютер, если вы не подключили облачную LLM, а e-mail авторов удаляется из промптов.
- **Ноль зависимостей.** Только стандартная библиотека Python и `git`. Устанавливается за секунды.

## Установка

Одна команда, тем инструментом, который у вас уже есть:

```bash
pipx install git+https://github.com/bollenlee89-blip/loreline
# or
uv tool install git+https://github.com/bollenlee89-blip/loreline
# or
curl -fsSL https://raw.githubusercontent.com/bollenlee89-blip/loreline/main/install.sh | sh
```

Нужны Python 3.9+ и git. Также устанавливается команда `git-why`, так что работает и `git why file.py:42`.

## Быстрый старт

```bash
cd your-repo
loreline init                       # index history + install auto-update hooks
loreline why src/server.py:120      # why does this line exist?
loreline why src/server.py:connect  # ...or this function?
loreline ask "why do we pin protobuf to 3.20?"
loreline serve                      # web UI at http://localhost:7777
```

### Подключение LLM (по желанию)

`loreline` выбирает автоматически: сначала запущенный **Ollama**, затем `ANTHROPIC_API_KEY`, затем `OPENAI_API_KEY`. Чтобы выбрать явно:

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

Добавьте `--global`, чтобы настройка действовала для всех репозиториев. `loreline doctor` проверит конфигурацию.

### Контекст пул-реквестов (по желанию)

Для репозиториев на GitHub `loreline` использует `GITHUB_TOKEN`, `GH_TOKEN` или ваш вход через `gh auth`, чтобы получить описания PR, ревью и связанные issue, и кэширует их локально. Без токена номера PR всё равно находятся по истории.

### Командный чат (по желанию)

```bash
loreline import ./slack-export/          # Slack workspace export folder
loreline import discord-channel.json     # DiscordChatExporter JSON
loreline import decisions.md notes.txt   # meeting notes, ADRs, "date name: message" logs
loreline import messages.jsonl           # {"author","date","text","channel"} per line
```

### Использование из Claude Code, Cursor и других агентов

```bash
claude mcp add loreline -- loreline mcp
```

Для Cursor, Windsurf или другого MCP-клиента добавьте сервер с командой `loreline` и аргументами `["mcp"]`. Агенты получат два инструмента: `loreline_why` и `loreline_ask`.

## Команды

| Команда | Что делает |
| --- | --- |
| `loreline init` | Индексирует репозиторий и ставит git-хуки для автообновления |
| `loreline why <path>[:line\|:symbol]` | Объясняет, зачем существует строка, функция или файл |
| `loreline ask "<question>"` | Отвечает на вопросы по истории проекта со ссылками |
| `loreline map [-o LORE.md]` | Пишет карту знаний: зачем существует каждый файл |
| `loreline serve` | Локальный веб-интерфейс: просмотр файлов, клик по любой строке |
| `loreline import <path...>` | Импорт Slack, Discord, JSONL или текстовых заметок |
| `loreline mcp` | Запуск MCP-сервера для агентов |
| `loreline index` / `watch` / `hooks` | Ручная индексация, наблюдение опросом, управление хуками |
| `loreline config show\|set` / `doctor` | Настройки и диагностика |

## Как это работает

```
 git history ──┐
 PRs/reviews ──┼──► index (.git/loreline/lore.db, SQLite + FTS5) ──► evidence pack ──► LLM (optional) ──► answer with citations
 issues ───────┤        ▲ updated by git hooks / watch                   ▲
 chat/notes ───┘        └──────────────────────────────────── blame + git log -L for the line you asked about
```

1. **Индексация:** коммиты, изменённые файлы, номера PR, обсуждения PR, связанные issue и сообщения чата сохраняются в локальную базу SQLite с полнотекстовым поиском.
2. **Трассировка:** для выбранной строки `git blame` находит коммит, который её добавил, а `git log -L` все последующие коммиты, которые её меняли.
3. **Связывание:** каждый коммит привязывается к своему PR (по сообщению, merge-коммиту или через API GitHub), а PR к issue, ревью и чату.
4. **Объяснение:** доказательства показываются напрямую или передаются вашей LLM со строгой инструкцией подкреплять каждое утверждение источником и ничего не выдумывать.

## Приватность

- База данных лежит внутри `.git/`, поэтому никогда не попадает в коммиты и не видна в рабочей копии.
- Веб-интерфейс слушает только `127.0.0.1` и отклоняет запросы с другими именами хостов, что блокирует атаки DNS rebinding.
- С локальной моделью (Ollama, llama.cpp…) ничего не покидает ваш компьютер.
- E-mail авторов удаляется из всего, что отправляется в LLM (`privacy.redact_emails`, включено по умолчанию).

## Планы

- [ ] Merge request'ы GitLab / Gitea / Bitbucket
- [ ] Расширения для VS Code и JetBrains (наведите на строку → why)
- [ ] Поиск по эмбеддингам вместе с FTS5
- [ ] Оповещения «устаревшая причина»: когда причина существования строки больше не актуальна
- [ ] Общие карты `LORE.md`, которые генерирует CI

Идеи и PR очень приветствуются. См. [CONTRIBUTING.md](../CONTRIBUTING.md).

## Лицензия

[MIT](../LICENSE)
