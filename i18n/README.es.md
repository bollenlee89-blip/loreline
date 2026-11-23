<div align="center">

[English](../README.md) · [简体中文](README.zh-CN.md) · [繁體中文](README.zh-TW.md) · [日本語](README.ja.md) · [한국어](README.ko.md) · **Español** · [Français](README.fr.md) · [Deutsch](README.de.md) · [Português](README.pt-BR.md) · [Русский](README.ru.md)

# loreline

### `git blame` te dice **quién**. `loreline` te dice **por qué**.

Un agente local-first que convierte cualquier repositorio git en una base de conocimiento viva.<br>Señala cualquier línea y te cuenta la decisión, el pull request, la discusión y las personas detrás de ella.

[![CI](https://github.com/bollenlee89-blip/loreline/actions/workflows/ci.yml/badge.svg)](https://github.com/bollenlee89-blip/loreline/actions/workflows/ci.yml)
![Python](https://img.shields.io/badge/python-3.9%2B-blue)
![Dependencies](https://img.shields.io/badge/dependencies-0-brightgreen)
![License](https://img.shields.io/badge/license-MIT-green)

<img src="../docs/screenshot.jpg" alt="loreline" width="100%">

<sub>La interfaz web (<code>loreline serve</code>) sobre un repositorio open source real. El texto de "Why it exists" lo escribe el LLM que conectes.</sub>

</div>

---

## ¿Por qué?

Todo código está lleno de líneas que parecen incorrectas pero existen por una razón: un `sleep(0.3)`, un reintento de 3 veces, un caso especial raro para un cliente. La razón vive en la descripción de un PR de 2021, en un comentario de revisión, en un hilo de Slack o en la cabeza de alguien. Cuando nadie la encuentra, o nadie se atreve a tocar ese código, o alguien lo "limpia" y vuelve a introducir el bug.

`loreline` conecta cada línea de código con la historia que hay detrás:

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

## Funcionalidades

- **`why` para cualquier línea, función o archivo.** Sigue la línea a través del historial con `git blame -w -M -C` y `git log -L`, ignorando movimientos y cambios de espacios (y respetando `.git-blame-ignore-revs`).
- **Encuentra el pull request, incluso sin conexión.** Lee los números de PR de los commits de merge y squash, y retrocede hasta el merge que introdujo cada commit. Con un token de GitHub también trae la descripción del PR, los comentarios de revisión y los issues vinculados.
- **El chat también es parte del registro.** Importa exportaciones de Slack o Discord, JSONL o notas en texto. Los mensajes que mencionan un commit, un PR o un archivo se vinculan automáticamente a ese código.
- **Pregúntale al historial.** `loreline ask "why did we drop Redis?"` busca en commits, PRs, issues y chat (SQLite FTS5) y responde con citas.
- **Siempre al día.** `loreline init` instala hooks de git para que el índice se actualice en cada commit, merge y rebase. También está `loreline watch` si prefieres sondeo periódico.
- **Mapa de conocimiento.** `loreline map -o LORE.md` escribe una línea por archivo explicando por qué existe. Se guarda en caché por archivo y solo se regenera cuando ese archivo cambia.
- **Funciona con cualquier LLM, o sin ninguno.** Ollama, LM Studio, llama.cpp, vLLM, cualquier API compatible con OpenAI, Anthropic Claude. Sin LLM igual ves todo el rastro de evidencias.
- **Se integra con tu agente de código.** `loreline mcp` es un servidor MCP, así que Claude Code, Cursor, Windsurf, Zed y otros pueden preguntar "¿por qué está esto aquí?" antes de borrar algo.
- **Local-first y privado por defecto.** Todo vive en `.git/loreline/`. Nada sale de tu máquina salvo que uses un LLM alojado, y los emails de los autores se eliminan de los prompts.
- **Cero dependencias.** Solo la biblioteca estándar de Python más `git`. Se instala en segundos.

## Instalación

Un solo comando, con la herramienta que ya tengas:

```bash
pipx install git+https://github.com/bollenlee89-blip/loreline
# or
uv tool install git+https://github.com/bollenlee89-blip/loreline
# or
curl -fsSL https://raw.githubusercontent.com/bollenlee89-blip/loreline/main/install.sh | sh
```

Necesitas Python 3.9+ y git. También se instala un comando `git-why`, así que `git why file.py:42` funciona.

## Inicio rápido

```bash
cd your-repo
loreline init                       # index history + install auto-update hooks
loreline why src/server.py:120      # why does this line exist?
loreline why src/server.py:connect  # ...or this function?
loreline ask "why do we pin protobuf to 3.20?"
loreline serve                      # web UI at http://localhost:7777
```

### Conectar un LLM (opcional)

`loreline` elige uno automáticamente: primero un **Ollama** en ejecución, luego `ANTHROPIC_API_KEY`, luego `OPENAI_API_KEY`. Para elegir explícitamente:

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

Añade `--global` para guardar un ajuste para todos los repositorios. Ejecuta `loreline doctor` para revisar tu configuración.

### Contexto de pull requests (opcional)

En repositorios de GitHub, `loreline` usa `GITHUB_TOKEN`, `GH_TOKEN` o tu sesión de `gh auth` para obtener descripciones de PR, revisiones e issues vinculados, y lo guarda en caché localmente. Sin token, igual encuentra los números de PR en el historial.

### Chat del equipo (opcional)

```bash
loreline import ./slack-export/          # Slack workspace export folder
loreline import discord-channel.json     # DiscordChatExporter JSON
loreline import decisions.md notes.txt   # meeting notes, ADRs, "date name: message" logs
loreline import messages.jsonl           # {"author","date","text","channel"} per line
```

### Úsalo desde Claude Code, Cursor y otros agentes

```bash
claude mcp add loreline -- loreline mcp
```

En Cursor, Windsurf u otro cliente MCP, añade un servidor con el comando `loreline` y los argumentos `["mcp"]`. Los agentes obtienen dos herramientas: `loreline_why` y `loreline_ask`.

## Comandos

| Comando | Qué hace |
| --- | --- |
| `loreline init` | Indexa el repo e instala hooks de git de actualización automática |
| `loreline why <path>[:line\|:symbol]` | Explica por qué existe una línea, función o archivo |
| `loreline ask "<question>"` | Responde preguntas con el historial del proyecto, con citas |
| `loreline map [-o LORE.md]` | Escribe un mapa de por qué existe cada archivo |
| `loreline serve` | Interfaz web local: explora archivos y haz clic en cualquier línea |
| `loreline import <path...>` | Importa Slack, Discord, JSONL o notas de texto |
| `loreline mcp` | Ejecuta un servidor MCP para agentes de código |
| `loreline index` / `watch` / `hooks` | Indexado manual, vigilancia por sondeo, gestión de hooks |
| `loreline config show\|set` / `doctor` | Configuración y diagnóstico |

## Cómo funciona

```
 git history ──┐
 PRs/reviews ──┼──► index (.git/loreline/lore.db, SQLite + FTS5) ──► evidence pack ──► LLM (optional) ──► answer with citations
 issues ───────┤        ▲ updated by git hooks / watch                   ▲
 chat/notes ───┘        └──────────────────────────────────── blame + git log -L for the line you asked about
```

1. **Indexar:** commits, archivos tocados, números de PR, discusiones de PR, issues vinculados y mensajes de chat se guardan en una base SQLite local con búsqueda de texto completo.
2. **Rastrear:** para la línea que preguntas, `git blame` encuentra el commit que la introdujo y `git log -L` cada commit posterior que la cambió.
3. **Vincular:** cada commit se asocia a su PR (por el mensaje, el commit de merge o la API de GitHub), y el PR a sus issues, comentarios de revisión y chat.
4. **Explicar:** esa evidencia se muestra directamente, o se entrega a tu LLM con instrucciones estrictas de citar cada afirmación y nunca inventar datos.

## Privacidad

- La base de datos vive dentro de `.git/`, así que nunca se commitea ni aparece en tu árbol de trabajo.
- La interfaz web escucha solo en `127.0.0.1` y rechaza peticiones para otros hostnames, lo que bloquea ataques de DNS rebinding.
- Con un modelo local (Ollama, llama.cpp…) nada sale de tu máquina.
- Los emails de los autores se eliminan de todo lo que se envía a un LLM (`privacy.redact_emails`, activado por defecto).

## Hoja de ruta

- [ ] Soporte de merge requests de GitLab / Gitea / Bitbucket
- [ ] Extensiones para VS Code y JetBrains (pasa el cursor sobre una línea → why)
- [ ] Búsqueda por embeddings junto a FTS5
- [ ] Alertas de "razón caducada": cuando la razón de una línea ya no aplica
- [ ] Mapas `LORE.md` compartibles generados por CI

Las ideas y los PRs son muy bienvenidos. Consulta [CONTRIBUTING.md](../CONTRIBUTING.md).

## Licencia

[MIT](../LICENSE)
