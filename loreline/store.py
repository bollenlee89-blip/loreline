"""Local SQLite knowledge store. Lives inside .git/loreline so it never pollutes the working tree."""
from __future__ import annotations

import json
import os
import re
import sqlite3
from typing import Any, Iterable

SCHEMA = """
CREATE TABLE IF NOT EXISTS meta (key TEXT PRIMARY KEY, value TEXT);
CREATE TABLE IF NOT EXISTS commits (
    sha TEXT PRIMARY KEY, author TEXT, email TEXT, date TEXT,
    subject TEXT, body TEXT, parents TEXT, pr INTEGER
);
CREATE INDEX IF NOT EXISTS commits_pr ON commits(pr);
CREATE TABLE IF NOT EXISTS commit_files (
    sha TEXT, path TEXT, added INTEGER, deleted INTEGER, PRIMARY KEY (sha, path)
);
CREATE INDEX IF NOT EXISTS commit_files_path ON commit_files(path);
CREATE TABLE IF NOT EXISTS prs (
    number INTEGER PRIMARY KEY, title TEXT, body TEXT, author TEXT, url TEXT,
    state TEXT, merged_at TEXT, labels TEXT, fetched INTEGER DEFAULT 0
);
CREATE TABLE IF NOT EXISTS issues (
    number INTEGER PRIMARY KEY, title TEXT, body TEXT, author TEXT, url TEXT, state TEXT
);
CREATE TABLE IF NOT EXISTS pr_issues (pr INTEGER, issue INTEGER, PRIMARY KEY (pr, issue));
CREATE TABLE IF NOT EXISTS messages (
    id TEXT PRIMARY KEY, source TEXT, channel TEXT, author TEXT, date TEXT,
    text TEXT, url TEXT, parent TEXT
);
CREATE TABLE IF NOT EXISTS links (
    message_id TEXT, kind TEXT, ref TEXT, PRIMARY KEY (message_id, kind, ref)
);
CREATE INDEX IF NOT EXISTS links_ref ON links(kind, ref);
CREATE TABLE IF NOT EXISTS file_notes (
    path TEXT PRIMARY KEY, summary TEXT, last_sha TEXT, model TEXT, updated TEXT
);
CREATE TABLE IF NOT EXISTS explain_cache (
    key TEXT PRIMARY KEY, answer TEXT, model TEXT, created TEXT
);
"""

FTS = """
CREATE VIRTUAL TABLE IF NOT EXISTS docs USING fts5(
    kind UNINDEXED, ref UNINDEXED, title, text, tokenize = 'unicode61 remove_diacritics 2'
);
"""


def data_dir(git_dir: str) -> str:
    d = os.path.join(git_dir, "loreline")
    os.makedirs(d, exist_ok=True)
    return d


class Store:
    def __init__(self, path: str):
        self.path = path
        self.db = sqlite3.connect(path, check_same_thread=False)
        self.db.row_factory = sqlite3.Row
        self.db.execute("PRAGMA journal_mode=WAL")
        self.db.executescript(SCHEMA)
        try:
            self.db.executescript(FTS)
            self.has_fts = True
        except sqlite3.OperationalError:  # pragma: no cover - sqlite without fts5
            self.has_fts = False
        self.db.commit()

    # ---- meta -----------------------------------------------------------
    def get_meta(self, key: str, default: str | None = None) -> str | None:
        row = self.db.execute("SELECT value FROM meta WHERE key=?", (key,)).fetchone()
        return row["value"] if row else default

    def set_meta(self, key: str, value: str) -> None:
        self.db.execute("INSERT OR REPLACE INTO meta(key, value) VALUES (?, ?)", (key, value))

    # ---- writes ---------------------------------------------------------
    def has_commit(self, sha: str) -> bool:
        return self.db.execute("SELECT 1 FROM commits WHERE sha=?", (sha,)).fetchone() is not None

    def add_commit(self, c: Any, pr: int | None) -> None:
        self.db.execute(
            "INSERT OR REPLACE INTO commits VALUES (?,?,?,?,?,?,?,?)",
            (c.sha, c.author, c.email, c.date, c.subject, c.body, " ".join(c.parents), pr),
        )
        self.db.executemany(
            "INSERT OR REPLACE INTO commit_files VALUES (?,?,?,?)",
            [(c.sha, p, a, d) for p, a, d in c.files],
        )
        self._doc("commit", c.sha, c.subject, c.body + "\n" + " ".join(p for p, _, _ in c.files))

    def add_pr(self, pr: dict) -> None:
        self.db.execute(
            "INSERT OR REPLACE INTO prs VALUES (?,?,?,?,?,?,?,?,?)",
            (pr["number"], pr.get("title", ""), pr.get("body") or "", pr.get("author", ""), pr.get("url", ""),
             pr.get("state", ""), pr.get("merged_at") or "", json.dumps(pr.get("labels", [])), 1),
        )
        self._doc("pr", str(pr["number"]), pr.get("title", ""), pr.get("body") or "")

    def add_issue(self, issue: dict) -> None:
        self.db.execute(
            "INSERT OR REPLACE INTO issues VALUES (?,?,?,?,?,?)",
            (issue["number"], issue.get("title", ""), issue.get("body") or "", issue.get("author", ""),
             issue.get("url", ""), issue.get("state", "")),
        )
        self._doc("issue", str(issue["number"]), issue.get("title", ""), issue.get("body") or "")

    def link_pr_issue(self, pr: int, issue: int) -> None:
        self.db.execute("INSERT OR IGNORE INTO pr_issues VALUES (?,?)", (pr, issue))

    def add_message(self, m: dict, links: Iterable[tuple[str, str]] = ()) -> None:
        self.db.execute(
            "INSERT OR REPLACE INTO messages VALUES (?,?,?,?,?,?,?,?)",
            (m["id"], m.get("source", ""), m.get("channel", ""), m.get("author", ""), m.get("date", ""),
             m.get("text", ""), m.get("url", ""), m.get("parent", "")),
        )
        self.db.executemany("INSERT OR IGNORE INTO links VALUES (?,?,?)", [(m["id"], k, r) for k, r in links])
        title = f"{m.get('source', '')} {m.get('channel', '')} {m.get('author', '')}".strip()
        self._doc("message", m["id"], title, m.get("text", ""))

    def _doc(self, kind: str, ref: str, title: str, text: str) -> None:
        if not self.has_fts:
            return
        self.db.execute("DELETE FROM docs WHERE kind=? AND ref=?", (kind, ref))
        self.db.execute("INSERT INTO docs(kind, ref, title, text) VALUES (?,?,?,?)", (kind, ref, title, text))

    def commit(self) -> None:
        self.db.commit()

    # ---- reads ----------------------------------------------------------
    def commit_row(self, sha: str) -> sqlite3.Row | None:
        return self.db.execute("SELECT * FROM commits WHERE sha=?", (sha,)).fetchone()

    def commit_files(self, sha: str) -> list[sqlite3.Row]:
        return self.db.execute("SELECT * FROM commit_files WHERE sha=? ORDER BY added+deleted DESC", (sha,)).fetchall()

    def pr_row(self, number: int) -> sqlite3.Row | None:
        return self.db.execute("SELECT * FROM prs WHERE number=?", (number,)).fetchone()

    def pr_issues(self, number: int) -> list[sqlite3.Row]:
        return self.db.execute(
            "SELECT i.* FROM issues i JOIN pr_issues p ON p.issue=i.number WHERE p.pr=?", (number,)
        ).fetchall()

    def messages_for(self, kind: str, ref: str, limit: int = 20) -> list[sqlite3.Row]:
        return self.db.execute(
            "SELECT m.* FROM messages m JOIN links l ON l.message_id=m.id WHERE l.kind=? AND l.ref=? "
            "ORDER BY m.date LIMIT ?",
            (kind, ref, limit),
        ).fetchall()

    def commits_for_path(self, path: str, limit: int = 50) -> list[sqlite3.Row]:
        return self.db.execute(
            "SELECT c.*, f.added, f.deleted FROM commits c JOIN commit_files f ON f.sha=c.sha "
            "WHERE f.path=? ORDER BY c.date DESC, c.rowid ASC LIMIT ?",
            (path, limit),
        ).fetchall()

    def cochanged(self, path: str, limit: int = 8) -> list[sqlite3.Row]:
        return self.db.execute(
            "SELECT f2.path AS path, COUNT(*) AS n FROM commit_files f1 JOIN commit_files f2 "
            "ON f1.sha=f2.sha AND f2.path<>f1.path WHERE f1.path=? GROUP BY f2.path ORDER BY n DESC LIMIT ?",
            (path, limit),
        ).fetchall()

    def search(self, query: str, limit: int = 12) -> list[sqlite3.Row]:
        if not self.has_fts:
            return []
        terms = [t for t in re.findall(r"[\w\-\.]+", query, flags=re.UNICODE) if len(t) > 1]
        if not terms:
            return []
        stop = {"the", "a", "an", "is", "are", "why", "what", "how", "was", "were", "do", "does", "did",
                "we", "our", "this", "that", "to", "of", "in", "on", "for", "and", "or", "it", "who", "when"}
        terms = [t for t in terms if t.lower() not in stop] or terms
        fts_q = " OR ".join('"' + t.replace('"', "") + '"' for t in terms)
        try:
            return self.db.execute(
                "SELECT kind, ref, title, snippet(docs, 3, '[', ']', ' … ', 24) AS snip, bm25(docs, 0, 0, 3.0, 1.0) AS score "
                "FROM docs WHERE docs MATCH ? ORDER BY score LIMIT ?",
                (fts_q, limit),
            ).fetchall()
        except sqlite3.OperationalError:
            return []

    def stats(self) -> dict:
        q = lambda sql: self.db.execute(sql).fetchone()[0]  # noqa: E731
        return {
            "commits": q("SELECT COUNT(*) FROM commits"),
            "prs": q("SELECT COUNT(*) FROM prs"),
            "issues": q("SELECT COUNT(*) FROM issues"),
            "messages": q("SELECT COUNT(*) FROM messages"),
            "files_with_notes": q("SELECT COUNT(*) FROM file_notes"),
            "last_indexed": self.get_meta("last_indexed_head"),
        }

    def all_shas(self) -> set[str]:
        return {r[0] for r in self.db.execute("SELECT sha FROM commits")}

    def resolve_sha_prefix(self, prefix: str) -> str | None:
        rows = self.db.execute("SELECT sha FROM commits WHERE sha LIKE ? LIMIT 2", (prefix + "%",)).fetchall()
        return rows[0][0] if len(rows) == 1 else None
