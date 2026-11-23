"""Configuration: defaults < ~/.config/loreline/config.json < .git/loreline/config.json < environment."""
from __future__ import annotations

import json
import os
from typing import Any

DEFAULTS: dict[str, Any] = {
    "llm": {
        # none | ollama | openai | anthropic
        "provider": "auto",
        "model": "",
        "base_url": "",
        "api_key": "",
        "temperature": 0.2,
        "timeout": 120,
    },
    "github": {
        # Fetch PR / issue context from the GitHub API when a token is available.
        "enabled": True,
        "token": "",
        "api_url": "https://api.github.com",
    },
    "index": {
        "max_commits": 0,  # 0 = unlimited
    },
    "privacy": {
        # Never send author e-mail addresses to an LLM.
        "redact_emails": True,
    },
}

ENV_MAP = {
    "LORELINE_LLM_PROVIDER": ("llm", "provider"),
    "LORELINE_LLM_MODEL": ("llm", "model"),
    "LORELINE_LLM_BASE_URL": ("llm", "base_url"),
    "LORELINE_LLM_API_KEY": ("llm", "api_key"),
    "LORELINE_GITHUB_TOKEN": ("github", "token"),
}


def _merge(base: dict, extra: dict) -> dict:
    out = dict(base)
    for k, v in extra.items():
        if isinstance(v, dict) and isinstance(out.get(k), dict):
            out[k] = _merge(out[k], v)
        else:
            out[k] = v
    return out


def global_path() -> str:
    base = os.environ.get("XDG_CONFIG_HOME") or os.path.join(os.path.expanduser("~"), ".config")
    return os.path.join(base, "loreline", "config.json")


def local_path(data_dir: str) -> str:
    return os.path.join(data_dir, "config.json")


def _load(path: str) -> dict:
    try:
        with open(path, encoding="utf-8") as fh:
            return json.load(fh)
    except (OSError, ValueError):
        return {}


def load(data_dir: str | None) -> dict:
    cfg = _merge(DEFAULTS, _load(global_path()))
    if data_dir:
        cfg = _merge(cfg, _load(local_path(data_dir)))
    for env, (sec, key) in ENV_MAP.items():
        if os.environ.get(env):
            cfg[sec][key] = os.environ[env]
    return cfg


def set_value(path: str, dotted: str, value: str) -> None:
    data = _load(path)
    keys = dotted.split(".")
    cur = data
    for k in keys[:-1]:
        cur = cur.setdefault(k, {})
    parsed: Any = value
    if value.lower() in ("true", "false"):
        parsed = value.lower() == "true"
    else:
        try:
            parsed = float(value) if "." in value else int(value)
        except ValueError:
            parsed = value
    cur[keys[-1]] = parsed
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "w", encoding="utf-8") as fh:
        json.dump(data, fh, indent=2)
