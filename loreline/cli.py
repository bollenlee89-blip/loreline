"""loreline command line interface."""
from __future__ import annotations

import argparse
import os
import re
import sys

from . import __version__, config as config_mod, gitutil, render
from .explain import Explainer, render_map_markdown, to_json
from .repo import Repo

TARGET_RE = re.compile(r"^(?P<path>.+?)(?::(?P<rest>[^:/\\]+))?$")


def parse_target(target: str) -> tuple[str, int | None, str | None]:
    """`file.py:42` → line 42, `file.py:parse_args` → symbol, `file.py` → whole file."""
    if os.path.exists(target):
        return target, None, None
    m = TARGET_RE.match(target)
    if not m or not m.group("rest"):
        return target, None, None
    rest = m.group("rest")
    if rest.isdigit():
        return m.group("path"), int(rest), None
    if "-" in rest and rest.split("-")[0].isdigit():
        return m.group("path"), int(rest.split("-")[0]), None
    return m.group("path"), None, rest


def _repo(args) -> Repo:
    return Repo(getattr(args, "repo", ".") or ".", offline=getattr(args, "offline", False),
                quiet=getattr(args, "quiet", False))


def _fresh(repo: Repo) -> None:
    """Cheap incremental index so answers always reflect HEAD."""
    if repo.store.get_meta("last_indexed_head") != gitutil.head(repo.root):
        was = repo.quiet
        repo.quiet = True
        repo.index(fetch_prs=False)
        repo.quiet = was


def cmd_init(args) -> int:
    repo = _repo(args)
    print(render.bold("loreline") + f" — building the knowledge base for {os.path.basename(repo.root)}")
    res = repo.index()
    print(f"  ✓ indexed {res['new_commits']} commits" + (f", {res['prs']} pull requests" if res["prs"] else ""))
    if not args.no_hooks:
        from .watch import install_hooks
        install_hooks(repo)
        print("  ✓ git hooks installed — the knowledge base updates itself on every commit, merge and rebase")
    if repo.github and not repo.github.token:
        print(render.dim("  · GitHub repo detected. Set GITHUB_TOKEN (or `gh auth login`) to pull PR discussions too."))
    llm = repo.llm
    print(f"  ✓ LLM: {llm.name}/{llm.model}" if llm.available() else
          render.dim("  · No LLM found — loreline will show raw evidence. Run `ollama serve` or set an API key for prose."))
    print("\nTry:\n  loreline why <file>:<line>\n  loreline ask \"why do we ...?\"\n  loreline serve")
    return 0


def cmd_index(args) -> int:
    repo = _repo(args)
    res = repo.index(fetch_prs=not args.no_prs, max_commits=args.max, full=args.full)
    if not args.quiet:
        print(f"indexed {res['new_commits']} new commits, fetched {res['prs']} pull requests")
    return 0


def cmd_why(args) -> int:
    repo = _repo(args)
    _fresh(repo)
    path, line, symbol = parse_target(args.target)
    if args.line:
        line = args.line
    ex = Explainer(repo)
    ev = ex.why(path, line, symbol, depth=args.depth)
    narrative = None if args.no_llm or not ev["commits"] else ex.narrate(ev, use_cache=not args.no_cache)
    if args.json:
        print(to_json({"evidence": ev, "narrative": narrative}))
    elif args.evidence:
        print(ex.evidence_text(ev))
    else:
        print(render.why(ev, narrative, verbose=args.verbose))
    return 0


def cmd_ask(args) -> int:
    repo = _repo(args)
    _fresh(repo)
    ex = Explainer(repo)
    if args.no_llm:
        repo.__dict__["llm"] = __import__("loreline.llm", fromlist=["LLM"]).LLM()
    res = ex.ask(" ".join(args.question), k=args.k)
    print(to_json(res) if args.json else render.ask(res))
    return 0


def cmd_map(args) -> int:
    repo = _repo(args)
    _fresh(repo)
    m = Explainer(repo).build_map(use_llm=not args.no_llm, limit=args.limit, only_changed=not args.rebuild)
    if args.json:
        out = to_json(m)
    else:
        out = render_map_markdown(m, os.path.basename(repo.root))
    if args.out:
        with open(args.out, "w", encoding="utf-8") as fh:
            fh.write(out + "\n")
        print(f"wrote {args.out} ({len(m['files'])} files, {m['updated']} refreshed)", file=sys.stderr)
    else:
        print(out)
    return 0


def cmd_watch(args) -> int:
    from .watch import watch
    watch(_repo(args), interval=args.interval, map_too=args.map)
    return 0


def cmd_hooks(args) -> int:
    from .watch import install_hooks, uninstall_hooks
    repo = _repo(args)
    if args.action == "install":
        print("installed: " + ", ".join(install_hooks(repo)))
    else:
        print("removed: " + (", ".join(uninstall_hooks(repo)) or "nothing"))
    return 0


def cmd_import(args) -> int:
    from .chat import import_chat
    repo = _repo(args)
    _fresh(repo)
    total = {"messages": 0, "linked": 0}
    for p in args.paths:
        res = import_chat(repo, p)
        total["messages"] += res["messages"]
        total["linked"] += res["linked"]
        print(f"{p}: {res['messages']} messages, {res['linked']} linked to commits/PRs/files")
    return 0


def cmd_serve(args) -> int:
    from .server import serve
    repo = _repo(args)
    _fresh(repo)
    serve(repo, host=args.host, port=args.port, open_browser=not args.no_open)
    return 0


def cmd_mcp(args) -> int:
    from .mcp import run
    repo = _repo(args)
    _fresh(repo)
    run(repo)
    return 0


def cmd_config(args) -> int:
    repo = None
    try:
        repo = _repo(args)
    except gitutil.GitError:
        if not args.global_:
            raise
    if args.action == "show":
        cfg = config_mod.load(repo.data_dir if repo else None)
        for sec in ("llm", "github"):
            if cfg[sec].get("api_key") or cfg[sec].get("token"):
                cfg[sec] = {**cfg[sec], **{k: "***" for k in ("api_key", "token") if cfg[sec].get(k)}}
        print(to_json(cfg))
        return 0
    if not args.key or args.value is None:
        print("usage: loreline config set <key> <value> [--global]", file=sys.stderr)
        return 2
    path = config_mod.global_path() if args.global_ else config_mod.local_path(repo.data_dir)
    config_mod.set_value(path, args.key, args.value)
    print(f"set {args.key} in {path}")
    return 0


def cmd_doctor(args) -> int:
    repo = _repo(args)
    ok = render.green("✓")
    no = render.yellow("·")
    st = repo.store.stats()
    print(f"{ok} repository  {repo.root}")
    print(f"{ok} store       {repo.store.path}")
    print(f"{ok if st['commits'] else no} indexed     {st['commits']} commits, {st['prs']} PRs, {st['issues']} issues, {st['messages']} messages")
    print(f"{ok if repo.store.has_fts else no} search      SQLite FTS5 {'available' if repo.store.has_fts else 'missing (search disabled)'}")
    gh = repo.github
    if gh:
        print(f"{ok if gh.token else no} github      {gh.owner}/{gh.repo} " + ("(token found)" if gh.token else "(no token: set GITHUB_TOKEN or `gh auth login`)"))
    else:
        print(f"{no} github      no GitHub remote (fine — loreline works on any git repo)")
    llm = repo.llm
    print(f"{ok if llm.available() else no} llm         " + (f"{llm.name}/{llm.model}" if llm.available() else
          "none — evidence only. Options: `ollama serve`, ANTHROPIC_API_KEY, OPENAI_API_KEY, or "
          "`loreline config set llm.provider openai` + llm.base_url for LM Studio/llama.cpp/vLLM"))
    from .watch import HOOKS, MARKER, hooks_dir
    installed = [h for h in HOOKS if os.path.exists(os.path.join(hooks_dir(repo), h))
                 and MARKER in open(os.path.join(hooks_dir(repo), h), encoding="utf-8").read()]
    print(f"{ok if installed else no} hooks       " + (", ".join(installed) if installed else "not installed (`loreline hooks install`)"))
    return 0


def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(prog="loreline", description="git blame tells you who. loreline tells you why.")
    p.add_argument("--version", action="version", version=f"loreline {__version__}")
    p.add_argument("-C", dest="repo", default=".", help="run as if started in this directory")
    p.add_argument("--offline", action="store_true", help="never contact GitHub")
    sub = p.add_subparsers(dest="cmd", metavar="<command>")

    s = sub.add_parser("init", help="index this repo and install auto-update hooks (start here)")
    s.add_argument("--no-hooks", action="store_true")
    s.set_defaults(fn=cmd_init)

    s = sub.add_parser("index", help="index new commits and pull requests")
    s.add_argument("--full", action="store_true", help="re-index everything")
    s.add_argument("--no-prs", action="store_true", help="skip GitHub pull request fetch")
    s.add_argument("--max", type=int, help="only the N most recent commits")
    s.add_argument("-q", "--quiet", action="store_true")
    s.set_defaults(fn=cmd_index)

    s = sub.add_parser("why", help="explain why a line, function or file exists")
    s.add_argument("target", help="path[:line] or path:function")
    s.add_argument("-L", "--line", type=int)
    s.add_argument("--depth", type=int, default=5, help="how many past commits to follow (default 5)")
    s.add_argument("--no-llm", action="store_true", help="show evidence only")
    s.add_argument("--no-cache", action="store_true")
    s.add_argument("--json", action="store_true")
    s.add_argument("--evidence", action="store_true", help="print the evidence pack sent to the LLM")
    s.add_argument("-v", "--verbose", action="store_true")
    s.set_defaults(fn=cmd_why)

    s = sub.add_parser("ask", help="ask a question about the project's history")
    s.add_argument("question", nargs="+")
    s.add_argument("-k", type=int, default=12, help="number of sources to retrieve")
    s.add_argument("--no-llm", action="store_true")
    s.add_argument("--json", action="store_true")
    s.set_defaults(fn=cmd_ask)

    s = sub.add_parser("map", help="generate a knowledge map: why every file exists")
    s.add_argument("-o", "--out", help="write to file (e.g. LORE.md)")
    s.add_argument("--no-llm", action="store_true")
    s.add_argument("--limit", type=int, help="max files to (re)summarise with the LLM")
    s.add_argument("--rebuild", action="store_true", help="ignore cached summaries")
    s.add_argument("--json", action="store_true")
    s.set_defaults(fn=cmd_map)

    s = sub.add_parser("watch", help="keep the knowledge base current (polling)")
    s.add_argument("--interval", type=float, default=30)
    s.add_argument("--map", action="store_true", help="also refresh the knowledge map")
    s.set_defaults(fn=cmd_watch)

    s = sub.add_parser("hooks", help="install/uninstall git hooks for automatic updates")
    s.add_argument("action", choices=["install", "uninstall"])
    s.set_defaults(fn=cmd_hooks)

    s = sub.add_parser("import", help="import chat (Slack export dir, Discord JSON, .jsonl, .md/.txt)")
    s.add_argument("paths", nargs="+")
    s.set_defaults(fn=cmd_import)

    s = sub.add_parser("serve", help="open the local web UI")
    s.add_argument("--host", default="127.0.0.1")
    s.add_argument("--port", type=int, default=7777)
    s.add_argument("--no-open", action="store_true")
    s.set_defaults(fn=cmd_serve)

    s = sub.add_parser("mcp", help="run as an MCP server for Claude Code, Cursor and other agents")
    s.set_defaults(fn=cmd_mcp)

    s = sub.add_parser("config", help="show or set configuration")
    s.add_argument("action", choices=["show", "set"])
    s.add_argument("key", nargs="?")
    s.add_argument("value", nargs="?")
    s.add_argument("--global", dest="global_", action="store_true")
    s.set_defaults(fn=cmd_config)

    s = sub.add_parser("doctor", help="check setup")
    s.set_defaults(fn=cmd_doctor)
    return p


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    if not getattr(args, "fn", None):
        parser.print_help()
        return 0
    try:
        return args.fn(args) or 0
    except gitutil.GitError as exc:
        print(f"loreline: {exc}", file=sys.stderr)
        return 1
    except KeyboardInterrupt:
        return 130


def git_why() -> int:
    """Entry point for `git why <path>:<line>` (installed as the git-why executable)."""
    return main(["why", *sys.argv[1:]])


if __name__ == "__main__":
    sys.exit(main())
