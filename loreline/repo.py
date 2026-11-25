"""The Repo object ties together git, the local store, config, GitHub and the LLM."""
from __future__ import annotations

import os
import re
import sys
from functools import cached_property

from . import config as config_mod
from . import gitutil, llm as llm_mod
from .github import GitHub, find_token, linked_issues
from .store import Store, data_dir

PR_PATTERNS = [
    re.compile(r"Merge pull request #(\d+)"),
    re.compile(r"\(#(\d+)\)\s*$"),
    re.compile(r"(?i)\bPR\s*#?(\d+)\b"),
    re.compile(r"/pull/(\d+)"),
    re.compile(r"See merge request [\w./-]+!(\d+)"),
]


def extract_pr(subject: str, body: str = "") -> int | None:
    for pat in PR_PATTERNS:
        m = pat.search(subject)
        if m:
            return int(m.group(1))
    for pat in PR_PATTERNS[:1] + PR_PATTERNS[3:]:
        m = pat.search(body or "")
        if m:
            return int(m.group(1))
    return None


class Repo:
    def __init__(self, path: str = ".", offline: bool = False, quiet: bool = False):
        self.root = gitutil.repo_root(path)
        self.git_dir = gitutil.git_dir(self.root)
        self.data_dir = data_dir(self.git_dir)
        self.cfg = config_mod.load(self.data_dir)
        self.offline = offline
        self.quiet = quiet

    def log(self, msg: str) -> None:
        if not self.quiet:
            print(msg, file=sys.stderr)

    @cached_property
    def store(self) -> Store:
        return Store(os.path.join(self.data_dir, "lore.db"))

    @cached_property
    def llm(self) -> llm_mod.LLM:
        return llm_mod.from_config(self.cfg)

    @cached_property
    def github(self) -> GitHub | None:
        if self.offline or not self.cfg["github"].get("enabled", True):
            return None
        slug = gitutil.github_slug(gitutil.remote_url(self.root))
        if not slug:
            return None
        return GitHub(slug[0], slug[1], find_token(self.cfg), self.cfg["github"].get("api_url", "https://api.github.com"))

    def rel(self, path: str) -> str:
        """Turn a user-supplied path into a repo-relative POSIX path."""
        p = os.path.abspath(path)
        if os.path.exists(p) and p.startswith(self.root):
            return os.path.relpath(p, self.root).replace(os.sep, "/")
        return path.replace(os.sep, "/").lstrip("./") if path.startswith("./") else path.replace(os.sep, "/")

    # ------------------------------------------------------------------ index
    def index(self, fetch_prs: bool = True, max_commits: int | None = None, full: bool = False) -> dict:
        st = self.store
        head = gitutil.head(self.root)
        if head is None:
            return {"new_commits": 0, "prs": 0}
        limit = max_commits or self.cfg["index"].get("max_commits") or None
        last = st.get_meta("last_indexed_head")
        rev = "HEAD"
        if not full and last and st.get_meta("complete") == "1" and gitutil.has_object(self.root, last):
            rev = f"{last}..HEAD"
        known = set() if full else st.all_shas()
        new = 0
        pr_numbers: set[int] = set()
        for c in gitutil.iter_commits(self.root, rev, max_count=limit):
            if c.sha in known:
                continue
            pr = extract_pr(c.subject, c.body)
            st.add_commit(c, pr)
            if pr:
                pr_numbers.add(pr)
            new += 1
            if new % 2000 == 0:
                st.commit()
                self.log(f"  indexed {new} commits…")
        st.set_meta("last_indexed_head", head)
        if not limit and rev == "HEAD":
            st.set_meta("complete", "1")
        st.commit()
        fetched = 0
        if fetch_prs and self.github:
            missing = [n for n in sorted(pr_numbers) if not st.pr_row(n)]
            if missing:
                self.log(f"  fetching {len(missing)} pull requests from GitHub…")
            for n in missing:
                if self.fetch_pr(n):
                    fetched += 1
                if self.github.rate_limited:
                    self.log("  GitHub rate limit reached; set GITHUB_TOKEN for more. Continuing offline.")
                    break
            st.commit()
        return {"new_commits": new, "prs": fetched}

    def fetch_pr(self, number: int) -> bool:
        gh = self.github
        if not gh:
            return False
        pr = gh.pull(number)
        if not pr:
            return False
        st = self.store
        st.add_pr(pr)
        for c in pr.get("comments", []):
            st.add_message({**c, "source": "github", "channel": f"PR #{number}"}, [("pr", str(number))])
        for issue_no in linked_issues(pr.get("body", "") + "\n" + pr.get("title", "")):
            if issue_no == number:
                continue
            st.link_pr_issue(number, issue_no)
            if not st.db.execute("SELECT 1 FROM issues WHERE number=?", (issue_no,)).fetchone():
                issue = gh.issue(issue_no)
                if issue:
                    st.add_issue(issue)
        return True

    def pr_for_commit(self, sha: str) -> int | None:
        row = self.store.commit_row(sha)
        if row and row["pr"]:
            return row["pr"]
        if row is not None and self.store.get_meta(f"pr_probe:{sha}") is None:
            # Commit came in via a merge commit that names the PR ("Merge pull request #12 ...").
            merge = gitutil.merge_that_introduced(self.root, sha)
            self.store.set_meta(f"pr_probe:{sha}", merge or "")
            if merge:
                mrow = self.ensure_commit(merge)
                if mrow and mrow["pr"]:
                    self.store.db.execute("UPDATE commits SET pr=? WHERE sha=?", (mrow["pr"], sha))
                    self.store.commit()
                    return mrow["pr"]
            self.store.commit()
        # Squash/rebase merges don't always mention the PR; ask GitHub lazily and cache it.
        gh = self.github
        if gh and gh.token:
            nums = gh.prs_for_commit(sha)
            if nums:
                self.store.db.execute("UPDATE commits SET pr=? WHERE sha=?", (nums[0], sha))
                self.store.commit()
                return nums[0]
        return None

    def refresh(self) -> bool:
        """Cheap incremental index when HEAD has moved, so long-running servers never answer from stale history."""
        if self.store.get_meta("last_indexed_head") == gitutil.head(self.root):
            return False
        was = self.quiet
        self.quiet = True
        try:
            self.index(fetch_prs=False)
        finally:
            self.quiet = was
        return True

    def ensure_commit(self, sha: str):
        row = self.store.commit_row(sha)
        if row:
            return row
        c = gitutil.show_commit(self.root, sha)
        if not c:
            return None
        self.store.add_commit(c, extract_pr(c.subject, c.body))
        self.store.commit()
        return self.store.commit_row(sha)

    def ensure_pr(self, number: int):
        row = self.store.pr_row(number)
        if row is None and self.github:
            if self.fetch_pr(number):
                self.store.commit()
                row = self.store.pr_row(number)
        return row
