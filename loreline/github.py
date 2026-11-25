"""Optional GitHub enrichment: pull request, review and issue context."""
from __future__ import annotations

import json
import os
import re
import shutil
import subprocess
import urllib.error
import urllib.request

# CI and coverage bots that post comments as regular users (older ones) or as Bot accounts.
KNOWN_BOTS = {"codecov-io", "codecov-commenter", "coveralls", "sonarcloud", "netlify", "vercel", "changeset-bot"}


def is_bot(user: dict | None) -> bool:
    user = user or {}
    login = (user.get("login") or "").lower()
    return user.get("type") == "Bot" or login.endswith("[bot]") or login in KNOWN_BOTS


ISSUE_REF = re.compile(r"(?i)\b(?:close[sd]?|fix(?:e[sd])?|resolve[sd]?|refs?|see|related to)\s*:?\s+#(\d+)")


def find_token(cfg: dict) -> str:
    tok = cfg.get("github", {}).get("token") or os.environ.get("GITHUB_TOKEN") or os.environ.get("GH_TOKEN")
    if tok:
        return tok
    if shutil.which("gh"):
        try:
            out = subprocess.run(["gh", "auth", "token"], capture_output=True, text=True, timeout=5)
            if out.returncode == 0:
                return out.stdout.strip()
        except (OSError, subprocess.SubprocessError):
            pass
    return ""


class GitHub:
    def __init__(self, owner: str, repo: str, token: str = "", api_url: str = "https://api.github.com"):
        self.owner, self.repo, self.token = owner, repo, token
        self.api = api_url.rstrip("/")
        self.rate_limited = False

    def _get(self, path: str):
        if self.rate_limited:
            return None
        headers = {"Accept": "application/vnd.github+json", "User-Agent": "loreline"}
        if self.token:
            headers["Authorization"] = f"Bearer {self.token}"
        req = urllib.request.Request(f"{self.api}/repos/{self.owner}/{self.repo}{path}", headers=headers)
        try:
            with urllib.request.urlopen(req, timeout=20) as resp:
                return json.loads(resp.read().decode())
        except urllib.error.HTTPError as exc:
            if exc.code == 401 and self.token:
                self.token = ""  # bad token: fall back to anonymous access
                return self._get(path)
            if exc.code in (403, 429):
                self.rate_limited = True
            return None
        except (urllib.error.URLError, TimeoutError, OSError, ValueError):
            return None

    def pull(self, number: int) -> dict | None:
        pr = self._get(f"/pulls/{number}")
        if not pr or "number" not in pr:
            return None
        comments: list[dict] = []
        for c in (self._get(f"/issues/{number}/comments?per_page=100") or []):
            if is_bot(c.get("user")):
                continue
            comments.append({"id": f"gh-ic-{c['id']}", "author": (c.get("user") or {}).get("login", ""),
                             "date": c.get("created_at", ""), "text": c.get("body") or "", "url": c.get("html_url", "")})
        for c in (self._get(f"/pulls/{number}/comments?per_page=100") or []):
            if is_bot(c.get("user")):
                continue
            text = c.get("body") or ""
            if c.get("path"):
                text = f"[{c['path']}] {text}"
            comments.append({"id": f"gh-rc-{c['id']}", "author": (c.get("user") or {}).get("login", ""),
                             "date": c.get("created_at", ""), "text": text, "url": c.get("html_url", "")})
        for r in (self._get(f"/pulls/{number}/reviews?per_page=100") or []):
            if r.get("body") and not is_bot(r.get("user")):
                comments.append({"id": f"gh-rv-{r['id']}", "author": (r.get("user") or {}).get("login", ""),
                                 "date": r.get("submitted_at", ""), "text": f"({r.get('state', '').lower()}) {r['body']}",
                                 "url": r.get("html_url", "")})
        return {
            "number": pr["number"], "title": pr.get("title", ""), "body": pr.get("body") or "",
            "author": (pr.get("user") or {}).get("login", ""), "url": pr.get("html_url", ""),
            "state": pr.get("state", ""), "merged_at": pr.get("merged_at"),
            "labels": [lb.get("name") for lb in pr.get("labels", [])], "comments": comments,
        }

    def issue(self, number: int) -> dict | None:
        it = self._get(f"/issues/{number}")
        if not it or "number" not in it or it.get("pull_request"):
            return None
        return {"number": it["number"], "title": it.get("title", ""), "body": it.get("body") or "",
                "author": (it.get("user") or {}).get("login", ""), "url": it.get("html_url", ""),
                "state": it.get("state", "")}

    def prs_for_commit(self, sha: str) -> list[int]:
        data = self._get(f"/commits/{sha}/pulls") or []
        return [p["number"] for p in data if isinstance(p, dict) and "number" in p]


def linked_issues(text: str) -> list[int]:
    return sorted({int(n) for n in ISSUE_REF.findall(text or "")})
