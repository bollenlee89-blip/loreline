"""Gather evidence for "why is this here?" and turn it into answers."""
from __future__ import annotations

import datetime as dt
import hashlib
import json
import os
import re

from . import PROJECT_URL, gitutil
from .llm import LLMError

SYSTEM_WHY = (
    "You are loreline, a careful code historian. Using ONLY the evidence provided (commits, pull requests, "
    "issues, review comments and team chat), explain WHY the given code exists: the problem it solved, the "
    "decision that was made, any alternatives or trade-offs mentioned, and who drove it. Cite evidence inline "
    "using the bracketed ids exactly as given, e.g. [C1] or [PR#42]. Never invent facts; if the evidence is "
    "thin, say so plainly. Answer in 3-6 sentences, then a final line starting with 'Decision:' that states the "
    "decision in one sentence."
)

SYSTEM_ASK = (
    "You are loreline, a code historian for this repository. Answer the question using ONLY the evidence "
    "provided. Cite evidence inline with the bracketed ids exactly as given. If the evidence does not answer the "
    "question, say what is missing. Be concise and concrete."
)

SYSTEM_FILE = (
    "You are loreline. In ONE sentence (max 30 words), state why this file exists and what role it plays, based "
    "only on its path, commit history and pull requests. No preamble."
)

EMAIL_RE = re.compile(r"[\w.+-]+@[\w-]+\.[\w.-]+")


def _clip(text: str, n: int) -> str:
    text = (text or "").strip()
    return text if len(text) <= n else text[: n - 1].rstrip() + "…"


def _short_date(iso: str) -> str:
    return (iso or "")[:10]


class Explainer:
    def __init__(self, repo):
        self.repo = repo
        self.store = repo.store

    # ------------------------------------------------------------ evidence
    def commit_card(self, sha: str, with_pr: bool = True) -> dict | None:
        row = self.repo.ensure_commit(sha)
        if not row:
            return None
        card = {
            "sha": row["sha"], "short": row["sha"][:8], "author": row["author"], "date": row["date"],
            "subject": row["subject"], "body": row["body"] or "",
            "files": [f["path"] for f in self.store.commit_files(sha)[:12]],
            "pr": None, "chat": [dict(m) for m in self.store.messages_for("commit", sha, 8)],
        }
        if with_pr:
            num = self.repo.pr_for_commit(sha)
            if num:
                card["pr"] = self.pr_card(num)
        return card

    def pr_card(self, number: int) -> dict:
        row = self.repo.ensure_pr(number)
        card = {"number": number, "title": "", "body": "", "url": "", "author": "", "issues": [], "discussion": [],
                "chat": []}
        if row:
            card.update({"title": row["title"], "body": row["body"], "url": row["url"], "author": row["author"]})
            card["issues"] = [dict(i) for i in self.store.pr_issues(number)]
        msgs = self.store.messages_for("pr", str(number), 30)
        card["discussion"] = [dict(m) for m in msgs if m["source"] == "github"]
        card["chat"] = [dict(m) for m in msgs if m["source"] != "github"]
        return card

    def why(self, path: str, line: int | None = None, symbol: str | None = None, depth: int = 5) -> dict:
        root = self.repo.root
        path = self.repo.rel(path)
        if gitutil.head(root) is None:
            raise gitutil.GitError("this repository has no commits yet, so there is no history to explain")
        if symbol and line is None:
            line = gitutil.find_function_line(root, path, symbol)
        target: dict = {"path": path, "line": line, "symbol": symbol, "text": ""}
        history: list[str] = []
        origin = None
        if line:
            try:
                bl = gitutil.blame_line(root, path, line)
            except gitutil.GitError as exc:
                # The line (or file) exists only in the working tree: blame that instead.
                if not os.path.exists(os.path.join(root, path)):
                    raise
                try:
                    bl = gitutil.blame_line(root, path, line, rev=None)
                except gitutil.GitError:
                    raise exc from None
            target["text"] = bl.text
            if bl.sha.startswith("0000000"):
                target["uncommitted"] = True
            if not bl.sha.startswith("0000000"):
                origin = bl.sha
            if symbol and not target.get("uncommitted"):
                history = gitutil.function_history(root, path, symbol, depth)
            if not history and not target.get("uncommitted"):
                history = gitutil.line_history(root, path, line, line, depth)
        else:
            history = gitutil.file_history(root, path, depth)
        shas: list[str] = []
        for s in ([origin] if origin else []) + history:
            if s and s not in shas:
                shas.append(s)
        commits = [c for c in (self.commit_card(s) for s in shas[: depth + 1]) if c]
        file_commits = self.store.commits_for_path(path, 200)
        followed = gitutil.file_history(root, path, 200)
        if len(followed) > len(file_commits):  # renamed file: the index only knows its current name
            file_commits = [r for r in (self.repo.ensure_commit(s) for s in followed) if r]
        created_sha = gitutil.creation_commit(root, path)
        created = (self.repo.ensure_commit(created_sha) if created_sha else None) or (file_commits[-1] if file_commits else None)
        return {
            "target": target,
            "origin": commits[0] if commits and origin else None,
            "commits": commits,
            "file": {
                "path": path,
                "commits": len(file_commits),
                "created": {"sha": created["sha"], "date": created["date"], "author": created["author"],
                            "subject": created["subject"]} if created else None,
                "authors": _top_authors(file_commits),
                "cochanged": [dict(r) for r in self.store.cochanged(path, 6)],
                "chat": [dict(m) for m in self.store.messages_for("path", path, 8)],
            },
        }

    # ------------------------------------------------------------ prompting
    def evidence_text(self, ev: dict) -> str:
        redact = self.repo.cfg.get("privacy", {}).get("redact_emails", True)
        out: list[str] = []
        t = ev["target"]
        where = f"{t['path']}" + (f":{t['line']}" if t.get("line") else "") + (f" (symbol {t['symbol']})" if t.get("symbol") else "")
        out.append(f"TARGET: {where}")
        if t.get("text"):
            out.append(f"CODE: {t['text'].strip()}")
        if t.get("uncommitted"):
            out.append("NOTE: this line is not committed yet, so no commit explains it.")
        seen_prs: set[int] = set()
        for i, c in enumerate(ev["commits"], 1):
            label = "introduced this line" if i == 1 and ev.get("origin") else "touched this code"
            out.append(f"\n[C{i}] commit {c['short']} by {c['author']} on {_short_date(c['date'])} ({label})")
            out.append(f"  subject: {c['subject']}")
            if c["body"]:
                out.append("  message: " + _clip(c["body"], 1200).replace("\n", "\n    "))
            for m in c["chat"][:4]:
                out.append(f"  [M:{m['id'][-6:]}] chat {m['channel']} {m['author']}: {_clip(m['text'], 300)}")
            pr = c.get("pr")
            if pr and pr["number"] not in seen_prs:
                seen_prs.add(pr["number"])
                out.append(f"\n[PR#{pr['number']}] {pr['title']} (by {pr['author']})")
                if pr["body"]:
                    out.append("  description: " + _clip(pr["body"], 1500).replace("\n", "\n    "))
                for iss in pr["issues"][:3]:
                    out.append(f"  [I#{iss['number']}] linked issue: {iss['title']} — {_clip(iss['body'], 500)}")
                for m in pr["discussion"][:8]:
                    out.append(f"  review {m['author']}: {_clip(m['text'], 300)}")
                for m in pr["chat"][:5]:
                    out.append(f"  [M:{m['id'][-6:]}] chat {m['channel']} {m['author']}: {_clip(m['text'], 300)}")
        f = ev["file"]
        for m in f["chat"][:4]:
            out.append(f"[M:{m['id'][-6:]}] chat about this file, {m['author']}: {_clip(m['text'], 300)}")
        if f.get("created"):
            out.append(f"\nFILE created {_short_date(f['created']['date'])} by {f['created']['author']}: {f['created']['subject']}")
        text = "\n".join(out)
        return EMAIL_RE.sub("<email>", text) if redact else text

    def narrate(self, ev: dict, use_cache: bool = True) -> str | None:
        llm = self.repo.llm
        if not llm.available():
            return None
        evidence = self.evidence_text(ev)
        key = hashlib.sha256(f"{llm.name}:{llm.model}:{evidence}".encode()).hexdigest()
        if use_cache:
            row = self.store.db.execute("SELECT answer FROM explain_cache WHERE key=?", (key,)).fetchone()
            if row:
                return row["answer"]
        try:
            answer = llm.complete(SYSTEM_WHY, evidence + "\n\nQuestion: Why does this code exist?")
        except LLMError as exc:
            return f"(LLM unavailable: {exc})"
        self.store.db.execute("INSERT OR REPLACE INTO explain_cache VALUES (?,?,?,?)",
                              (key, answer, f"{llm.name}/{llm.model}", dt.datetime.now(dt.timezone.utc).isoformat()))
        self.store.commit()
        return answer

    # ------------------------------------------------------------ ask
    def ask(self, question: str, k: int = 12) -> dict:
        hits = [dict(h) for h in self.store.search(question, k)]
        # Boost: files mentioned in the question
        files = gitutil.ls_files(self.repo.root)
        mentioned = [f for f in files if f in question or f.rsplit("/", 1)[-1] in question.split()]
        file_cards = []
        for f in mentioned[:2]:
            for r in self.store.commits_for_path(f, 5):
                hits.append({"kind": "commit", "ref": r["sha"], "title": r["subject"], "snip": _clip(r["body"], 200), "score": 0})
            file_cards.append(f)
        lines, sources = [], []
        seen = set()
        for h in hits:
            key = (h["kind"], h["ref"])
            if key in seen:
                continue
            seen.add(key)
            sid = _source_id(h)
            sources.append({**h, "id": sid})
            lines.append(f"[{sid}] {h['kind']} {h['title']}\n  {self._full_text(h)}")
        answer = None
        llm = self.repo.llm
        if llm.available() and lines:
            prompt = "EVIDENCE:\n" + "\n".join(lines) + f"\n\nQUESTION: {question}"
            if self.repo.cfg.get("privacy", {}).get("redact_emails", True):
                prompt = EMAIL_RE.sub("<email>", prompt)
            try:
                answer = llm.complete(SYSTEM_ASK, prompt)
            except LLMError as exc:
                answer = f"(LLM unavailable: {exc})"
        return {"question": question, "answer": answer, "sources": sources, "files": file_cards}

    def _full_text(self, h: dict) -> str:
        st = self.store.db
        if h["kind"] == "commit":
            r = st.execute("SELECT author, date, body FROM commits WHERE sha=?", (h["ref"],)).fetchone()
            return f"{r['author']} {_short_date(r['date'])}: {_clip(r['body'], 600)}" if r else ""
        if h["kind"] == "pr":
            r = st.execute("SELECT author, body FROM prs WHERE number=?", (int(h["ref"]),)).fetchone()
            return f"{r['author']}: {_clip(r['body'], 900)}" if r else ""
        if h["kind"] == "issue":
            r = st.execute("SELECT author, body FROM issues WHERE number=?", (int(h["ref"]),)).fetchone()
            return f"{r['author']}: {_clip(r['body'], 600)}" if r else ""
        r = st.execute("SELECT author, channel, date, text FROM messages WHERE id=?", (h["ref"],)).fetchone()
        return f"{r['channel']} {r['author']} {_short_date(r['date'])}: {_clip(r['text'], 500)}" if r else ""

    # ------------------------------------------------------------ map
    def build_map(self, use_llm: bool = True, limit: int | None = None, only_changed: bool = True) -> dict:
        root = self.repo.root
        files = gitutil.ls_files(root)
        llm = self.repo.llm if use_llm else None
        can_llm = bool(llm and llm.available())
        updated = 0
        entries = []
        for path in files:
            commits = self.store.commits_for_path(path, 30)
            if not commits:
                continue
            last_sha = commits[0]["sha"]
            note = self.store.db.execute("SELECT * FROM file_notes WHERE path=?", (path,)).fetchone()
            summary = note["summary"] if note else ""
            stale = not note or note["last_sha"] != last_sha
            if stale or not only_changed:
                if can_llm and (limit is None or updated < limit):
                    prs = {c["pr"] for c in commits if c["pr"]}
                    pr_titles = [r["title"] for r in (self.store.pr_row(n) for n in sorted(prs)[:8]) if r]
                    prompt = (f"PATH: {path}\nCOMMITS (newest first):\n" +
                              "\n".join(f"- {c['subject']}" for c in commits[:20]) +
                              ("\nPULL REQUESTS:\n" + "\n".join(f"- {t}" for t in pr_titles) if pr_titles else ""))
                    try:
                        summary = llm.complete(SYSTEM_FILE, prompt).strip().splitlines()[0]
                    except (LLMError, IndexError):
                        summary = summary or _heuristic_summary(commits)
                else:
                    summary = _heuristic_summary(commits)
                self.store.db.execute("INSERT OR REPLACE INTO file_notes VALUES (?,?,?,?,?)",
                                      (path, summary, last_sha, f"{llm.name}/{llm.model}" if can_llm else "heuristic",
                                       dt.datetime.now(dt.timezone.utc).isoformat()))
                updated += 1
            entries.append({"path": path, "summary": summary, "commits": len(commits),
                            "authors": _top_authors(commits, 3), "last": _short_date(commits[0]["date"]),
                            "created": _short_date(commits[-1]["date"])})
        self.store.commit()
        return {"files": entries, "updated": updated}


def _heuristic_summary(commits) -> str:
    first = commits[-1]
    subj = re.sub(r"\s*\(#\d+\)$", "", first["subject"])
    return f"Introduced in “{_clip(subj, 80)}” ({_short_date(first['date'])}); {len(commits) - 1} later change(s)."


def _top_authors(rows, n: int = 4) -> list[dict]:
    counts: dict[str, int] = {}
    for r in rows:
        counts[r["author"]] = counts.get(r["author"], 0) + 1
    return [{"name": k, "commits": v} for k, v in sorted(counts.items(), key=lambda kv: -kv[1])[:n]]


def _source_id(h: dict) -> str:
    if h["kind"] == "commit":
        return "C:" + h["ref"][:8]
    if h["kind"] == "pr":
        return "PR#" + h["ref"]
    if h["kind"] == "issue":
        return "I#" + h["ref"]
    return "M:" + h["ref"][-6:]


def render_map_markdown(m: dict, repo_name: str) -> str:
    out = [f"# {repo_name} — knowledge map", "",
           f"_Generated by [loreline]({PROJECT_URL}). Why each file exists, from its history._", ""]
    by_dir: dict[str, list[dict]] = {}
    for e in m["files"]:
        d = e["path"].rsplit("/", 1)[0] if "/" in e["path"] else "."
        by_dir.setdefault(d, []).append(e)
    for d in sorted(by_dir):
        out.append(f"## `{d}/`" if d != "." else "## (root)")
        out.append("")
        for e in by_dir[d]:
            who = ", ".join(a["name"] for a in e["authors"])
            out.append(f"- **`{e['path']}`** — {e['summary']}  ")
            out.append(f"  <sub>{e['commits']} commits · {e['created']} → {e['last']} · {who}</sub>")
        out.append("")
    return "\n".join(out)


def to_json(obj) -> str:
    return json.dumps(obj, indent=2, ensure_ascii=False, default=str)
