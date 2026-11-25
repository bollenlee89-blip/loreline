"""Minimal Model Context Protocol server (stdio) so coding agents can ask loreline "why?".

Works with Claude Code, Cursor, Windsurf, Zed, Continue and any MCP client:
    claude mcp add loreline -- loreline mcp
"""
from __future__ import annotations

import json
import sys

from . import __version__
from .explain import Explainer, to_json

TOOLS = [
    {
        "name": "loreline_why",
        "description": "Explain WHY a line, function or file exists in this repository, using its git history, "
                       "pull requests, linked issues, review comments and imported team chat. Use this before "
                       "changing or deleting code whose purpose is unclear.",
        "inputSchema": {
            "type": "object",
            "properties": {
                "path": {"type": "string", "description": "Repo-relative file path"},
                "line": {"type": "integer", "description": "1-based line number (optional)"},
                "symbol": {"type": "string", "description": "Function/class name instead of a line (optional)"},
            },
            "required": ["path"],
        },
        "annotations": {"title": "Why does this code exist?", "readOnlyHint": True, "openWorldHint": False},
    },
    {
        "name": "loreline_ask",
        "description": "Search the repository's history (commits, PRs, issues, discussions, chat) and answer a "
                       "question such as 'why did we switch from X to Y?' with cited sources.",
        "inputSchema": {"type": "object", "properties": {"question": {"type": "string"}}, "required": ["question"]},
        "annotations": {"title": "Ask the repository's history", "readOnlyHint": True, "openWorldHint": False},
    },
]


def _result(id_, result):
    return {"jsonrpc": "2.0", "id": id_, "result": result}


def _error(id_, code, msg):
    return {"jsonrpc": "2.0", "id": id_, "error": {"code": code, "message": msg}}


def handle(repo, explainer: Explainer, msg: dict):
    method, id_ = msg.get("method"), msg.get("id")
    if method == "initialize":
        return _result(id_, {
            "protocolVersion": (msg.get("params") or {}).get("protocolVersion", "2024-11-05"),
            "capabilities": {"tools": {}},
            "serverInfo": {"name": "loreline", "version": __version__},
        })
    if method == "ping":
        return _result(id_, {})
    if method == "tools/list":
        return _result(id_, {"tools": TOOLS})
    if method == "tools/call":
        params = msg.get("params") or {}
        name, args = params.get("name"), params.get("arguments") or {}
        try:
            repo.refresh()  # pick up commits made since the server started
            if name == "loreline_why":
                ev = explainer.why(args["path"], args.get("line"), args.get("symbol"))
                narrative = explainer.narrate(ev)
                text = (f"{narrative}\n\n---\nEVIDENCE\n" if narrative else "") + explainer.evidence_text(ev)
            elif name == "loreline_ask":
                res = explainer.ask(args["question"])
                text = (res["answer"] + "\n\n---\n" if res["answer"] else "") + to_json(res["sources"])
            else:
                return _error(id_, -32602, f"unknown tool {name}")
            return _result(id_, {"content": [{"type": "text", "text": text}]})
        except Exception as exc:  # noqa: BLE001
            return _result(id_, {"content": [{"type": "text", "text": f"error: {exc}"}], "isError": True})
    if id_ is None:  # notification
        return None
    return _error(id_, -32601, f"method not found: {method}")


def run(repo) -> None:  # pragma: no cover - stdio loop
    repo.quiet = True
    explainer = Explainer(repo)
    for line in sys.stdin:
        line = line.strip()
        if not line:
            continue
        try:
            msg = json.loads(line)
        except ValueError:
            resp = _error(None, -32700, "parse error: expected one JSON-RPC message per line")
        else:
            resp = handle(repo, explainer, msg) if isinstance(msg, dict) else _error(None, -32600, "invalid request")
        if resp is not None:
            sys.stdout.write(json.dumps(resp) + "\n")
            sys.stdout.flush()
