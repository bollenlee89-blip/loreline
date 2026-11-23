"""Keep the knowledge base current: git hooks and a polling watcher."""
from __future__ import annotations

import os
import stat
import sys
import time

from . import gitutil

HOOKS = ("post-commit", "post-merge", "post-rewrite", "post-checkout")
MARKER = "# >>> loreline >>>"
END = "# <<< loreline <<<"


def _snippet() -> str:
    exe = sys.executable.replace("\\", "/")
    return (f"{MARKER}\n"
            f"( \"{exe}\" -m loreline index --quiet >/dev/null 2>&1 & ) 2>/dev/null || true\n"
            f"{END}\n")


def hooks_dir(repo) -> str:
    custom = gitutil.git(["config", "--get", "core.hooksPath"], cwd=repo.root, check=False).strip()
    if custom:
        return custom if os.path.isabs(custom) else os.path.join(repo.root, custom)
    return os.path.join(repo.git_dir, "hooks")


def install_hooks(repo) -> list[str]:
    d = hooks_dir(repo)
    os.makedirs(d, exist_ok=True)
    done = []
    for name in HOOKS:
        p = os.path.join(d, name)
        content = ""
        if os.path.exists(p):
            with open(p, encoding="utf-8") as fh:
                content = fh.read()
            if MARKER in content:
                done.append(name)
                continue
        if not content:
            content = "#!/bin/sh\n"
        content = content.rstrip("\n") + "\n" + _snippet()
        with open(p, "w", encoding="utf-8") as fh:
            fh.write(content)
        os.chmod(p, os.stat(p).st_mode | stat.S_IXUSR | stat.S_IXGRP | stat.S_IXOTH)
        done.append(name)
    return done


def uninstall_hooks(repo) -> list[str]:
    d = hooks_dir(repo)
    removed = []
    for name in HOOKS:
        p = os.path.join(d, name)
        if not os.path.exists(p):
            continue
        with open(p, encoding="utf-8") as fh:
            content = fh.read()
        if MARKER not in content:
            continue
        start, end = content.index(MARKER), content.index(END) + len(END)
        content = (content[:start] + content[end:]).strip("\n") + "\n"
        if content.strip() in ("#!/bin/sh", ""):
            os.remove(p)
        else:
            with open(p, "w", encoding="utf-8") as fh:
                fh.write(content)
        removed.append(name)
    return removed


def watch(repo, interval: float = 30.0, map_too: bool = False) -> None:  # pragma: no cover - loop
    from .explain import Explainer

    last = None
    repo.log(f"watching {repo.root} every {interval:.0f}s (Ctrl+C to stop)")
    while True:
        h = gitutil.head(repo.root)
        if h != last:
            res = repo.index()
            if res["new_commits"] or res["prs"]:
                repo.log(f"  +{res['new_commits']} commits, +{res['prs']} PRs")
                if map_too:
                    Explainer(repo).build_map()
            last = h
        time.sleep(interval)
