"""Thin, dependency-free wrappers around the git CLI."""
from __future__ import annotations

import os
import re
import subprocess
from dataclasses import dataclass, field
from typing import Iterator

FIELD = "\x1f"
RECORD = "\x1e"


class GitError(RuntimeError):
    pass


def git(args: list[str], cwd: str, check: bool = True, input: str | None = None) -> str:
    try:
        proc = subprocess.run(
            ["git", *args],
            cwd=cwd,
            input=input,
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
        )
    except FileNotFoundError as exc:  # pragma: no cover
        raise GitError("git is not installed or not on PATH") from exc
    if check and proc.returncode != 0:
        raise GitError(proc.stderr.strip() or f"git {' '.join(args)} failed")
    return proc.stdout


def repo_root(path: str = ".") -> str:
    try:
        return git(["rev-parse", "--show-toplevel"], cwd=path).strip()
    except GitError as exc:
        raise GitError(f"{os.path.abspath(path)} is not inside a git repository") from exc


def git_dir(root: str) -> str:
    d = git(["rev-parse", "--git-common-dir"], cwd=root).strip()
    return d if os.path.isabs(d) else os.path.normpath(os.path.join(root, d))


def head(root: str) -> str | None:
    out = git(["rev-parse", "--verify", "-q", "HEAD"], cwd=root, check=False).strip()
    return out or None


def has_object(root: str, sha: str) -> bool:
    try:
        git(["cat-file", "-e", f"{sha}^{{commit}}"], cwd=root)
        return True
    except GitError:
        return False


@dataclass
class Commit:
    sha: str
    author: str
    email: str
    date: str  # ISO 8601
    subject: str
    body: str
    parents: list[str] = field(default_factory=list)
    files: list[tuple[str, int, int]] = field(default_factory=list)  # path, added, deleted


_LOG_FORMAT = RECORD + FIELD.join(["%H", "%an", "%ae", "%aI", "%P", "%s", "%b"]) + FIELD


def iter_commits(root: str, rev_range: str | None = None, max_count: int | None = None) -> Iterator[Commit]:
    """Yield commits (newest first) with per-file numstat."""
    if head(root) is None:
        return
    args = ["-c", "core.quotepath=off", "log", "--topo-order", f"--format={_LOG_FORMAT}", "--numstat", "--no-renames"]
    if max_count:
        args.append(f"-n{max_count}")
    args.append(rev_range or "HEAD")
    out = git(args, cwd=root)
    for chunk in out.split(RECORD):
        if FIELD not in chunk:
            continue
        parts = chunk.split(FIELD)
        if len(parts) < 8:
            continue
        sha, an, ae, ad, parents, subject, body = parts[:7]
        numstat = FIELD.join(parts[7:])
        yield Commit(sha=sha.strip(), author=an, email=ae, date=ad, subject=subject,
                     body=body.strip(), parents=parents.split(), files=_parse_numstat(numstat))


def _parse_numstat(text: str) -> list[tuple[str, int, int]]:
    files = []
    for item in text.splitlines():
        m = re.match(r"^(\d+|-)\t(\d+|-)\t(.+)$", item.strip("\r"))
        if m:
            a = 0 if m.group(1) == "-" else int(m.group(1))
            d = 0 if m.group(2) == "-" else int(m.group(2))
            files.append((m.group(3), a, d))
    return files


def show_commit(root: str, sha: str) -> Commit | None:
    for c in iter_commits(root, rev_range=sha, max_count=1):
        return c
    return None


@dataclass
class BlameLine:
    sha: str
    orig_line: int
    orig_path: str
    author: str
    date: str
    summary: str
    text: str


def blame_line(root: str, path: str, line: int, rev: str | None = "HEAD") -> BlameLine:
    """Blame one line at `rev`; rev=None blames the working tree (uncommitted lines get a zero SHA)."""
    args = ["blame", "--porcelain", "-w", "-M", "-C", "-L", f"{line},{line}"]
    ignore = os.path.join(root, ".git-blame-ignore-revs")
    if os.path.exists(ignore):
        args += ["--ignore-revs-file", ignore]
    args += ([rev] if rev else []) + ["--", path]
    out = git(args, cwd=root)
    lines = out.splitlines()
    if not lines:
        raise GitError(f"no blame output for {path}:{line}")
    first = lines[0].split()
    sha, orig_line = first[0], int(first[1])
    info: dict[str, str] = {}
    text = ""
    for ln in lines[1:]:
        if ln.startswith("\t"):
            text = ln[1:]
            break
        k, _, v = ln.partition(" ")
        info[k] = v
    import datetime as _dt

    ts = int(info.get("author-time", "0") or 0)
    date = _dt.datetime.fromtimestamp(ts, _dt.timezone.utc).isoformat() if ts else ""
    return BlameLine(sha=sha, orig_line=orig_line, orig_path=info.get("filename", path),
                     author=info.get("author", ""), date=date, summary=info.get("summary", ""), text=text)


def line_history(root: str, path: str, start: int, end: int | None = None, limit: int = 8) -> list[str]:
    """Return SHAs (newest first) of commits that touched the given line range, via git log -L."""
    end = end or start
    out = git(["log", f"-n{limit}", "--format=%x1e%H", "-s", f"-L{start},{end}:{path}"], cwd=root, check=False)
    return _shas(out)


def function_history(root: str, path: str, func: str, limit: int = 8) -> list[str]:
    out = git(["log", f"-n{limit}", "--format=%x1e%H", "-s", f"-L:{func}:{path}"], cwd=root, check=False)
    return _shas(out)


def _shas(out: str) -> list[str]:
    shas = []
    for chunk in out.split(RECORD):
        cand = chunk.strip()[:40]
        if re.fullmatch(r"[0-9a-f]{40}", cand):
            shas.append(cand)
    return shas


def file_history(root: str, path: str, limit: int | None = 50) -> list[str]:
    args = ["log", "--follow", "--format=%H"] + ([f"-n{limit}"] if limit else [])
    out = git(args + ["--", path], cwd=root, check=False)
    return [s for s in out.split() if s]


def merge_that_introduced(root: str, sha: str, max_checks: int = 25) -> str | None:
    """Find the merge commit that brought `sha` into the current branch (offline PR discovery)."""
    out = git(["rev-list", "--ancestry-path", "--merges", "--reverse", f"{sha}..HEAD"], cwd=root, check=False)
    for merge in out.split()[:max_checks]:
        parents = git(["rev-list", "--parents", "-n1", merge], cwd=root, check=False).split()[1:]
        if len(parents) < 2:
            continue
        if _is_ancestor(root, sha, parents[0]):
            continue
        if any(_is_ancestor(root, sha, p) for p in parents[1:]):
            return merge
    return None


def _is_ancestor(root: str, a: str, b: str) -> bool:
    return subprocess.run(["git", "merge-base", "--is-ancestor", a, b], cwd=root,
                          capture_output=True).returncode == 0


def creation_commit(root: str, path: str) -> str | None:
    """The commit that first added this file, following renames back to the original name."""
    out = git(["log", "--follow", "--diff-filter=A", "--format=%H", "--", path], cwd=root, check=False).split()
    if not out:
        out = git(["log", "--diff-filter=A", "--format=%H", "--", path], cwd=root, check=False).split()
    return out[-1] if out else None


def ls_files(root: str) -> list[str]:
    out = git(["ls-files", "-z"], cwd=root)
    return [p for p in out.split("\x00") if p]


def read_file(root: str, path: str, rev: str | None = None) -> str:
    if rev:
        return git(["show", f"{rev}:{path}"], cwd=root)
    full = os.path.join(root, path)
    with open(full, encoding="utf-8", errors="replace") as fh:
        return fh.read()


def remote_url(root: str, name: str = "origin") -> str | None:
    out = git(["remote", "get-url", name], cwd=root, check=False).strip()
    return out or None


def github_slug(url: str | None) -> tuple[str, str] | None:
    if not url:
        return None
    m = re.search(r"github\.com[:/]([^/\s]+)/([^/\s]+?)(?:\.git)?/?$", url)
    return (m.group(1), m.group(2)) if m else None


def find_function_line(root: str, path: str, name: str) -> int | None:
    """Best-effort: find the first line defining a symbol called `name`."""
    try:
        text = read_file(root, path)
    except OSError:
        return None
    pat = re.compile(
        rf"^\s*(?:export\s+)?(?:async\s+)?(?:def|function|func|fn|class|struct|interface|type|const|let|var|pub\s+fn|public|private|protected|static)?[\w\s\*<>,\[\]:&]*\b{re.escape(name)}\b\s*[\(=:<{{]"
    )
    for i, line in enumerate(text.splitlines(), 1):
        if pat.search(line):
            return i
    return None
