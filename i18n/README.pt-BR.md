<div align="center">

[English](../README.md) · [简体中文](README.zh-CN.md) · [繁體中文](README.zh-TW.md) · [日本語](README.ja.md) · [한국어](README.ko.md) · [Español](README.es.md) · [Français](README.fr.md) · [Deutsch](README.de.md) · **Português** · [Русский](README.ru.md)

# loreline

### `git blame` diz **quem**. `loreline` diz **por quê**.

Um agente local-first que transforma qualquer repositório git em uma base de conhecimento viva.<br>Aponte para qualquer linha e ele mostra a decisão, o pull request, a discussão e as pessoas por trás dela.

[![CI](https://github.com/bollenlee89-blip/loreline/actions/workflows/ci.yml/badge.svg)](https://github.com/bollenlee89-blip/loreline/actions/workflows/ci.yml)
![Python](https://img.shields.io/badge/python-3.9%2B-blue)
![Dependencies](https://img.shields.io/badge/dependencies-0-brightgreen)
![License](https://img.shields.io/badge/license-MIT-green)

<img src="../docs/screenshot.jpg" alt="loreline" width="100%">

<sub>A interface web (<code>loreline serve</code>) em um repositório open source real. O texto de "Why it exists" é escrito pelo LLM que você conectar.</sub>

</div>

---

## Por quê?

Todo código tem linhas que parecem erradas mas existem por um motivo: um `sleep(0.3)`, 3 tentativas de retry, um caso especial estranho para um cliente. O motivo está na descrição de um PR de 2021, num comentário de revisão, numa thread do Slack ou na cabeça de alguém. Quando ninguém encontra, ou ninguém mexe naquele código nunca mais, ou alguém "limpa" e traz o bug de volta.

`loreline` conecta cada linha de código à história por trás dela:

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

## Recursos

- **`why` para qualquer linha, função ou arquivo.** Segue a linha pelo histórico com `git blame -w -M -C` e `git log -L`, ignorando movimentações e mudanças de espaço (e respeitando `.git-blame-ignore-revs`).
- **Encontra o pull request, mesmo offline.** Lê números de PR em commits de merge e squash e volta até o merge que trouxe cada commit. Com um token do GitHub, também busca a descrição do PR, comentários de revisão e issues vinculadas.
- **O chat faz parte do registro.** Importe exportações do Slack ou Discord, JSONL ou notas em texto. Mensagens que mencionam um commit, um PR ou um arquivo são vinculadas automaticamente ao código.
- **Pergunte ao histórico.** `loreline ask "why did we drop Redis?"` busca em commits, PRs, issues e chat (SQLite FTS5) e responde com citações.
- **Sempre atualizado.** `loreline init` instala hooks do git para atualizar o índice a cada commit, merge e rebase. Se preferir polling, use `loreline watch`.
- **Mapa de conhecimento.** `loreline map -o LORE.md` escreve uma linha por arquivo explicando por que ele existe. Tem cache por arquivo e só é regenerado quando o arquivo muda.
- **Funciona com qualquer LLM, ou nenhum.** Ollama, LM Studio, llama.cpp, vLLM, qualquer API compatível com OpenAI, Anthropic Claude. Sem LLM você ainda vê toda a trilha de evidências.
- **Integra com seu agente de código.** `loreline mcp` é um servidor MCP, então Claude Code, Cursor, Windsurf, Zed e outros podem perguntar "por que isso está aqui?" antes de apagar algo.
- **Local-first e privado por padrão.** Tudo fica em `.git/loreline/`. Nada sai da sua máquina a menos que você use um LLM hospedado, e os e-mails dos autores são removidos dos prompts.
- **Zero dependências.** Só a biblioteca padrão do Python e o `git`. Instala em segundos.

## Instalação

Um único comando, com a ferramenta que você já tem:

```bash
pipx install git+https://github.com/bollenlee89-blip/loreline
# or
uv tool install git+https://github.com/bollenlee89-blip/loreline
# or
curl -fsSL https://raw.githubusercontent.com/bollenlee89-blip/loreline/main/install.sh | sh
```

Requer Python 3.9+ e git. Também instala o comando `git-why`, então `git why file.py:42` funciona.

## Início rápido

```bash
cd your-repo
loreline init                       # index history + install auto-update hooks
loreline why src/server.py:120      # why does this line exist?
loreline why src/server.py:connect  # ...or this function?
loreline ask "why do we pin protobuf to 3.20?"
loreline serve                      # web UI at http://localhost:7777
```

### Conectar um LLM (opcional)

`loreline` escolhe automaticamente: primeiro um **Ollama** em execução, depois `ANTHROPIC_API_KEY`, depois `OPENAI_API_KEY`. Para escolher manualmente:

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

Adicione `--global` para salvar a configuração para todos os repositórios. Rode `loreline doctor` para verificar o setup.

### Contexto de pull requests (opcional)

Em repositórios do GitHub, `loreline` usa `GITHUB_TOKEN`, `GH_TOKEN` ou seu login do `gh auth` para buscar descrições de PR, revisões e issues vinculadas, com cache local. Sem token, ainda encontra os números de PR no histórico.

### Chat do time (opcional)

```bash
loreline import ./slack-export/          # Slack workspace export folder
loreline import discord-channel.json     # DiscordChatExporter JSON
loreline import decisions.md notes.txt   # meeting notes, ADRs, "date name: message" logs
loreline import messages.jsonl           # {"author","date","text","channel"} per line
```

### Use no Claude Code, Cursor e outros agentes

```bash
claude mcp add loreline -- loreline mcp
```

No Cursor, Windsurf ou outro cliente MCP, adicione um servidor com o comando `loreline` e os argumentos `["mcp"]`. Os agentes ganham duas ferramentas: `loreline_why` e `loreline_ask`.

## Comandos

| Comando | O que faz |
| --- | --- |
| `loreline init` | Indexa o repo e instala hooks do git de atualização automática |
| `loreline why <path>[:line\|:symbol]` | Explica por que uma linha, função ou arquivo existe |
| `loreline ask "<question>"` | Responde perguntas com base no histórico, com citações |
| `loreline map [-o LORE.md]` | Gera um mapa de por que cada arquivo existe |
| `loreline serve` | Interface web local: navegue nos arquivos e clique em qualquer linha |
| `loreline import <path...>` | Importa Slack, Discord, JSONL ou notas em texto |
| `loreline mcp` | Roda como servidor MCP para agentes de código |
| `loreline index` / `watch` / `hooks` | Indexação manual, monitoramento por polling, gestão de hooks |
| `loreline config show\|set` / `doctor` | Configuração e diagnóstico |

## Como funciona

```
 git history ──┐
 PRs/reviews ──┼──► index (.git/loreline/lore.db, SQLite + FTS5) ──► evidence pack ──► LLM (optional) ──► answer with citations
 issues ───────┤        ▲ updated by git hooks / watch                   ▲
 chat/notes ───┘        └──────────────────────────────────── blame + git log -L for the line you asked about
```

1. **Indexar:** commits, arquivos alterados, números de PR, discussões de PR, issues vinculadas e mensagens de chat vão para um banco SQLite local com busca de texto completo.
2. **Rastrear:** para a linha perguntada, `git blame` acha o commit que a introduziu e `git log -L` cada commit posterior que a alterou.
3. **Vincular:** cada commit é ligado ao seu PR (pela mensagem, pelo commit de merge ou pela API do GitHub), e o PR às issues, revisões e chat.
4. **Explicar:** a evidência é mostrada diretamente ou entregue ao seu LLM com instruções rígidas para citar cada afirmação e nunca inventar fatos.

## Privacidade

- O banco fica dentro de `.git/`, então nunca é commitado nem aparece na sua árvore de trabalho.
- A interface web escuta só em `127.0.0.1` e rejeita requisições para outros hostnames, bloqueando ataques de DNS rebinding.
- Com um modelo local (Ollama, llama.cpp…), nada sai da sua máquina.
- E-mails dos autores são removidos de tudo que vai para um LLM (`privacy.redact_emails`, ativado por padrão).

## Roadmap

- [ ] Merge requests do GitLab / Gitea / Bitbucket
- [ ] Extensões para VS Code e JetBrains (passe o mouse numa linha → why)
- [ ] Busca por embeddings junto com FTS5
- [ ] Alertas de "motivo vencido": quando o motivo de uma linha não vale mais
- [ ] Mapas `LORE.md` compartilháveis gerados pela CI

Ideias e PRs são muito bem-vindos. Veja [CONTRIBUTING.md](../CONTRIBUTING.md).

## Licença

[MIT](../LICENSE)
