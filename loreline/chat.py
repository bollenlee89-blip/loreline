"""Import team chat (Slack / Discord exports, JSONL, plain text) and link it to commits, PRs and files."""
from __future__ import annotations

import datetime as dt
import glob
import hashlib
import json
import os
import re

from . import gitutil

PR_RE = re.compile(r"(?:#|/pull/|PR\s?#?)(\d{1,6})\b", re.I)
SHA_RE = re.compile(r"\b[0-9a-f]{7,40}\b")
PATH_RE = re.compile(r"[\w\-./]+\.[A-Za-z0-9]{1,8}")


def _id(*parts: str) -> str:
    return "chat-" + hashlib.sha1("\x00".join(parts).encode()).hexdigest()[:16]


def _ts(value) -> str:
    try:
        return dt.datetime.fromtimestamp(float(value), dt.timezone.utc).isoformat()
    except (TypeError, ValueError):
        return str(value or "")


def read_slack(path: str):
    users = {}
    users_file = os.path.join(path, "users.json")
    if os.path.exists(users_file):
        with open(users_file, encoding="utf-8") as fh:
            for u in json.load(fh):
                users[u.get("id")] = (u.get("real_name") or u.get("name") or u.get("id"))
    for f in sorted(glob.glob(os.path.join(path, "*", "*.json"))):
        channel = os.path.basename(os.path.dirname(f))
        with open(f, encoding="utf-8") as fh:
            try:
                msgs = json.load(fh)
            except ValueError:
                continue
        for m in msgs if isinstance(msgs, list) else []:
            text = m.get("text") or ""
            if not text:
                continue
            author = (m.get("user_profile") or {}).get("real_name") or users.get(m.get("user")) or m.get("user", "")
            yield {"id": _id("slack", channel, m.get("ts", ""), text[:50]), "source": "slack", "channel": channel,
                   "author": author, "date": _ts(m.get("ts")), "text": text,
                   "parent": m.get("thread_ts", "") if m.get("thread_ts") != m.get("ts") else ""}


def read_discord(path: str):
    with open(path, encoding="utf-8") as fh:
        data = json.load(fh)
    channel = (data.get("channel") or {}).get("name", "discord")
    for m in data.get("messages", []):
        text = m.get("content") or ""
        if text:
            yield {"id": _id("discord", m.get("id", ""), text[:50]), "source": "discord", "channel": channel,
                   "author": (m.get("author") or {}).get("name", ""), "date": m.get("timestamp", ""), "text": text}


def read_jsonl(path: str):
    with open(path, encoding="utf-8") as fh:
        for i, line in enumerate(fh):
            line = line.strip()
            if not line:
                continue
            try:
                m = json.loads(line)
            except ValueError:
                continue
            text = m.get("text") or m.get("content") or m.get("message") or ""
            if text:
                yield {"id": m.get("id") or _id(path, str(i), text[:50]), "source": m.get("source", "chat"),
                       "channel": m.get("channel", ""), "author": m.get("author") or m.get("user", ""),
                       "date": str(m.get("date") or m.get("ts") or ""), "text": text, "url": m.get("url", "")}


LINE_RE = re.compile(r"^\[?(?P<date>\d{4}-\d{2}-\d{2}[ T][\d:]+)?\]?\s*(?P<author>[^:\n]{1,40}):\s+(?P<text>.+)$")


def read_text(path: str):
    """Plain text/markdown. Lines like `2024-05-01 10:00 alice: message` become messages; otherwise paragraphs."""
    with open(path, encoding="utf-8", errors="replace") as fh:
        content = fh.read()
    name = os.path.basename(path)
    lines = content.splitlines()
    structured = [LINE_RE.match(ln) for ln in lines]
    if lines and sum(1 for m in structured if m) >= max(1, len(lines) // 3):
        for i, m in enumerate(structured):
            if m:
                yield {"id": _id(path, str(i)), "source": "notes", "channel": name, "author": m.group("author").strip(),
                       "date": m.group("date") or "", "text": m.group("text")}
        return
    for i, para in enumerate(re.split(r"\n\s*\n", content)):
        if para.strip():
            yield {"id": _id(path, str(i)), "source": "notes", "channel": name, "author": "", "date": "",
                   "text": para.strip()}


def detect_and_read(path: str):
    if os.path.isdir(path):
        return read_slack(path)
    if path.endswith(".jsonl"):
        return read_jsonl(path)
    if path.endswith(".json"):
        with open(path, encoding="utf-8") as fh:
            head = fh.read(4096)
        if '"messages"' in head and '"channel"' in head:
            return read_discord(path)
        return read_jsonl(path)
    return read_text(path)


def import_chat(repo, path: str) -> dict:
    st = repo.store
    files = set(gitutil.ls_files(repo.root))
    shas = st.all_shas()
    n = linked = 0
    for m in detect_and_read(path):
        links: set[tuple[str, str]] = set()
        text = m["text"]
        for num in PR_RE.findall(text):
            links.add(("pr", str(int(num))))
        for cand in SHA_RE.findall(text):
            if any(ch.isalpha() for ch in cand):
                full = next((s for s in shas if s.startswith(cand)), None) if len(cand) < 40 else (cand if cand in shas else None)
                if full:
                    links.add(("commit", full))
        for p in PATH_RE.findall(text):
            p = p.strip("./") if p.startswith("./") else p
            if p in files:
                links.add(("path", p))
        st.add_message(m, links)
        n += 1
        linked += bool(links)
    st.commit()
    return {"messages": n, "linked": linked}
