# Changelog

## 0.1.0

First public release.

- `why` for lines, functions and files using `git blame -w -M -C` and `git log -L`
- Offline PR discovery from merge/squash commits, with optional GitHub enrichment (PR body, reviews, linked issues)
- `ask` with SQLite FTS5 retrieval and cited answers
- `map` knowledge map with per-file caching
- Chat import: Slack, Discord, JSONL, text/markdown
- Auto-update git hooks and `watch`
- Local web UI (`serve`) and MCP server (`mcp`)
- LLM backends: Ollama, OpenAI-compatible, Anthropic, or none
