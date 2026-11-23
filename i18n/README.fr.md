<div align="center">

[English](../README.md) · [简体中文](README.zh-CN.md) · [繁體中文](README.zh-TW.md) · [日本語](README.ja.md) · [한국어](README.ko.md) · [Español](README.es.md) · **Français** · [Deutsch](README.de.md) · [Português](README.pt-BR.md) · [Русский](README.ru.md)

# loreline

### `git blame` vous dit **qui**. `loreline` vous dit **pourquoi**.

Un agent local-first qui transforme n'importe quel dépôt git en base de connaissances vivante.<br>Pointez une ligne, il vous donne la décision, la pull request, la discussion et les personnes derrière.

[![CI](https://github.com/bollenlee89-blip/loreline/actions/workflows/ci.yml/badge.svg)](https://github.com/bollenlee89-blip/loreline/actions/workflows/ci.yml)
![Python](https://img.shields.io/badge/python-3.9%2B-blue)
![Dependencies](https://img.shields.io/badge/dependencies-0-brightgreen)
![License](https://img.shields.io/badge/license-MIT-green)

<img src="../docs/screenshot.jpg" alt="loreline" width="100%">

<sub>L'interface web (<code>loreline serve</code>) sur un vrai dépôt open source. Le texte « Why it exists » est rédigé par le LLM que vous connectez.</sub>

</div>

---

## Pourquoi ?

Chaque base de code est pleine de lignes qui semblent fausses mais existent pour une raison : un `sleep(0.3)`, 3 tentatives de reconnexion, un cas particulier bizarre pour un client. La raison se cache dans la description d'une PR de 2021, un commentaire de revue, un fil Slack ou la tête de quelqu'un. Quand personne ne la retrouve, soit on n'ose plus toucher au code, soit on le « nettoie » et on réintroduit le bug.

`loreline` relie chaque ligne de code à l'histoire qui l'explique :

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

## Fonctionnalités

- **`why` pour n'importe quelle ligne, fonction ou fichier.** Suit la ligne dans l'historique avec `git blame -w -M -C` et `git log -L`, en ignorant les déplacements et les changements d'espaces (et en respectant `.git-blame-ignore-revs`).
- **Retrouve la pull request, même hors ligne.** Lit les numéros de PR dans les commits de merge et de squash, et remonte jusqu'au merge qui a introduit un commit. Avec un token GitHub, récupère aussi la description de la PR, les commentaires de revue et les issues liées.
- **Le chat fait partie de l'historique.** Importez des exports Slack ou Discord, du JSONL ou des notes texte. Les messages qui mentionnent un commit, une PR ou un fichier sont automatiquement liés au code concerné.
- **Interrogez l'historique.** `loreline ask "why did we drop Redis?"` cherche dans les commits, PR, issues et le chat (SQLite FTS5) et répond avec des citations.
- **Toujours à jour.** `loreline init` installe des hooks git pour mettre l'index à jour à chaque commit, merge et rebase. `loreline watch` existe aussi si vous préférez le polling.
- **Carte des connaissances.** `loreline map -o LORE.md` écrit une ligne par fichier expliquant pourquoi il existe. Mise en cache par fichier, régénérée seulement quand le fichier change.
- **Fonctionne avec n'importe quel LLM, ou aucun.** Ollama, LM Studio, llama.cpp, vLLM, toute API compatible OpenAI, Anthropic Claude. Sans LLM, vous avez quand même toutes les preuves.
- **S'intègre à votre agent de code.** `loreline mcp` est un serveur MCP : Claude Code, Cursor, Windsurf, Zed et d'autres peuvent demander « pourquoi ce code est-il là ? » avant de supprimer quelque chose.
- **Local-first et privé par défaut.** Tout est stocké dans `.git/loreline/`. Rien ne quitte votre machine sauf si vous utilisez un LLM hébergé, et les e-mails des auteurs sont retirés des prompts.
- **Zéro dépendance.** Bibliothèque standard Python et `git`, c'est tout. S'installe en quelques secondes.

## Installation

Une seule commande, avec l'outil que vous avez déjà :

```bash
pipx install git+https://github.com/bollenlee89-blip/loreline
# or
uv tool install git+https://github.com/bollenlee89-blip/loreline
# or
curl -fsSL https://raw.githubusercontent.com/bollenlee89-blip/loreline/main/install.sh | sh
```

Il faut Python 3.9+ et git. Une commande `git-why` est aussi installée, donc `git why file.py:42` fonctionne.

## Démarrage rapide

```bash
cd your-repo
loreline init                       # index history + install auto-update hooks
loreline why src/server.py:120      # why does this line exist?
loreline why src/server.py:connect  # ...or this function?
loreline ask "why do we pin protobuf to 3.20?"
loreline serve                      # web UI at http://localhost:7777
```

### Connecter un LLM (optionnel)

`loreline` en choisit un automatiquement : d'abord un **Ollama** en cours d'exécution, puis `ANTHROPIC_API_KEY`, puis `OPENAI_API_KEY`. Pour choisir explicitement :

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

Ajoutez `--global` pour enregistrer un réglage pour tous les dépôts. Lancez `loreline doctor` pour vérifier votre configuration.

### Contexte des pull requests (optionnel)

Pour les dépôts GitHub, `loreline` utilise `GITHUB_TOKEN`, `GH_TOKEN` ou votre session `gh auth` pour récupérer descriptions de PR, revues et issues liées, mises en cache localement. Sans token, il retrouve quand même les numéros de PR dans l'historique.

### Chat d'équipe (optionnel)

```bash
loreline import ./slack-export/          # Slack workspace export folder
loreline import discord-channel.json     # DiscordChatExporter JSON
loreline import decisions.md notes.txt   # meeting notes, ADRs, "date name: message" logs
loreline import messages.jsonl           # {"author","date","text","channel"} per line
```

### Utilisation depuis Claude Code, Cursor et d'autres agents

```bash
claude mcp add loreline -- loreline mcp
```

Pour Cursor, Windsurf ou un autre client MCP, ajoutez un serveur avec la commande `loreline` et les arguments `["mcp"]`. Les agents obtiennent deux outils : `loreline_why` et `loreline_ask`.

## Commandes

| Commande | Rôle |
| --- | --- |
| `loreline init` | Indexe le dépôt et installe les hooks git de mise à jour automatique |
| `loreline why <path>[:line\|:symbol]` | Explique pourquoi une ligne, une fonction ou un fichier existe |
| `loreline ask "<question>"` | Répond à une question à partir de l'historique, avec citations |
| `loreline map [-o LORE.md]` | Écrit une carte expliquant pourquoi chaque fichier existe |
| `loreline serve` | Interface web locale : parcourez les fichiers, cliquez sur une ligne |
| `loreline import <path...>` | Importe Slack, Discord, JSONL ou notes texte |
| `loreline mcp` | Lance un serveur MCP pour les agents de code |
| `loreline index` / `watch` / `hooks` | Indexation manuelle, surveillance par polling, gestion des hooks |
| `loreline config show\|set` / `doctor` | Configuration et diagnostic |

## Fonctionnement

```
 git history ──┐
 PRs/reviews ──┼──► index (.git/loreline/lore.db, SQLite + FTS5) ──► evidence pack ──► LLM (optional) ──► answer with citations
 issues ───────┤        ▲ updated by git hooks / watch                   ▲
 chat/notes ───┘        └──────────────────────────────────── blame + git log -L for the line you asked about
```

1. **Indexer :** commits, fichiers touchés, numéros de PR, discussions de PR, issues liées et messages de chat sont stockés dans une base SQLite locale avec recherche plein texte.
2. **Tracer :** pour la ligne demandée, `git blame` trouve le commit qui l'a introduite et `git log -L` chaque commit qui l'a modifiée ensuite.
3. **Relier :** chaque commit est rattaché à sa PR (via le message, le commit de merge ou l'API GitHub), et la PR à ses issues, revues et messages de chat.
4. **Expliquer :** ces preuves sont affichées directement, ou confiées à votre LLM avec la consigne stricte de citer chaque affirmation et de ne jamais inventer.

## Confidentialité

- La base de données vit dans `.git/` : elle n'est jamais commitée et n'apparaît jamais dans votre arbre de travail.
- L'interface web n'écoute que sur `127.0.0.1` et rejette les requêtes pour d'autres noms d'hôte, ce qui bloque les attaques par DNS rebinding.
- Avec un modèle local (Ollama, llama.cpp…), rien ne quitte votre machine.
- Les e-mails des auteurs sont retirés de tout ce qui est envoyé à un LLM (`privacy.redact_emails`, activé par défaut).

## Feuille de route

- [ ] Merge requests GitLab / Gitea / Bitbucket
- [ ] Extensions VS Code et JetBrains (survolez une ligne → why)
- [ ] Recherche par embeddings en plus de FTS5
- [ ] Alertes « raison périmée » : quand la raison d'une ligne ne tient plus
- [ ] Cartes `LORE.md` partageables générées par la CI

Idées et PR bienvenues ! Voir [CONTRIBUTING.md](../CONTRIBUTING.md).

## Licence

[MIT](../LICENSE)
