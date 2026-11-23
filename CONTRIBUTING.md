# Contributing to loreline

Thanks for helping! loreline is intentionally small and dependency-free.

## Ground rules

- **Standard library only.** No runtime dependencies. If you need something, write the 30 lines.
- **Local-first.** Nothing may leave the user's machine unless they configured a hosted LLM or GitHub token.
- **Never invent history.** Every claim shown to the user must trace back to a commit, PR, issue or message.
- Python 3.9+.

## Development

```bash
git clone https://github.com/bollenlee89-blip/loreline && cd loreline
python3 -m venv .venv && . .venv/bin/activate
pip install -e .
python -m unittest discover -s tests
```

Try it on any repository: `loreline -C ../some-repo init && loreline -C ../some-repo serve`.

## Good first issues

- New chat importers (Mattermost, Teams, Zulip, Matrix)
- GitLab / Gitea merge-request enrichment (`loreline/github.py` is the model)
- Editor integrations that call `loreline why --json`
- Translations of the README (see `i18n/`)
