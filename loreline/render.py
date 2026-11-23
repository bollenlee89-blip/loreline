"""Terminal rendering with optional ANSI colours (honours NO_COLOR)."""
from __future__ import annotations

import os
import sys
import textwrap

_USE_COLOR = sys.stdout.isatty() and not os.environ.get("NO_COLOR")


def _c(code: str, s: str) -> str:
    return f"\033[{code}m{s}\033[0m" if _USE_COLOR else s


bold = lambda s: _c("1", s)  # noqa: E731
dim = lambda s: _c("2", s)  # noqa: E731
cyan = lambda s: _c("36", s)  # noqa: E731
yellow = lambda s: _c("33", s)  # noqa: E731
green = lambda s: _c("32", s)  # noqa: E731
magenta = lambda s: _c("35", s)  # noqa: E731


def _wrap(text: str, indent: str = "    ", width: int = 96, max_lines: int = 8) -> str:
    lines: list[str] = []
    for para in (text or "").strip().splitlines():
        if not para.strip():
            continue
        lines.extend(textwrap.wrap(para, width - len(indent)) or [""])
    if len(lines) > max_lines:
        lines = lines[:max_lines] + ["…"]
    return "\n".join(indent + ln for ln in lines)


def why(ev: dict, narrative: str | None, verbose: bool = False) -> str:
    t = ev["target"]
    out: list[str] = []
    loc = t["path"] + (f":{t['line']}" if t.get("line") else "")
    out.append(bold(f"⟡ {loc}") + (dim(f"  ({t['symbol']})") if t.get("symbol") else ""))
    if t.get("text"):
        out.append(dim("  │ ") + t["text"].rstrip())
    out.append("")
    if narrative:
        out.append(bold(green("Why it exists")))
        out.append(_wrap(narrative, "  ", max_lines=40))
        out.append("")
    if not ev["commits"]:
        out.append(yellow("  No history found (uncommitted line or file not tracked)."))
        return "\n".join(out)
    for i, c in enumerate(ev["commits"], 1):
        tag = "introduced by" if i == 1 and ev.get("origin") else "changed in"
        out.append(f"{cyan(f'[C{i}]')} {dim(tag)} {yellow(c['short'])} {bold(c['subject'])}")
        out.append(dim(f"     {c['author']} · {c['date'][:10]}"))
        if c["body"] and (verbose or i == 1):
            out.append(_wrap(c["body"], "     ", max_lines=6 if not verbose else 30))
        pr = c.get("pr")
        if pr:
            title = pr["title"] or "(details not fetched — run `loreline index` with a GitHub token)"
            prlabel = magenta("PR #" + str(pr["number"]))
            out.append(f"     {prlabel} {title}" + (dim("  " + pr["url"]) if pr["url"] else ""))
            if pr["body"] and (verbose or i == 1):
                out.append(_wrap(pr["body"], "       ", max_lines=8 if not verbose else 40))
            for iss in pr["issues"][:3]:
                out.append("       " + magenta("issue #" + str(iss["number"])) + " " + iss["title"])
            for m in pr["discussion"][: (6 if verbose else 2)]:
                if m["text"].strip():
                    out.append(dim(f"       💬 {m['author']}: ") + m["text"].strip().splitlines()[0][:110])
            for m in pr["chat"][:3]:
                out.append(dim(f"       🗨 {m['channel']} · {m['author']}: ") + m["text"].strip()[:110])
        for m in c["chat"][:3]:
            out.append(dim(f"     🗨 {m['channel']} · {m['author']}: ") + m["text"].strip()[:110])
        out.append("")
    f = ev["file"]
    if f.get("created"):
        authors = ", ".join(f"{a['name']} ({a['commits']})" for a in f["authors"])
        out.append(dim(f"file: {f['commits']} commits · created {f['created']['date'][:10]} by {f['created']['author']} · {authors}"))
    if f.get("cochanged"):
        out.append(dim("often changes with: " + ", ".join(r["path"] for r in f["cochanged"][:5])))
    if not narrative:
        out.append(dim("tip: connect an LLM (e.g. `ollama serve`) for a written explanation — see `loreline doctor`."))
    return "\n".join(out)


def ask(res: dict) -> str:
    out = []
    if res["answer"]:
        out.append(bold(green("Answer")))
        out.append(_wrap(res["answer"], "  ", max_lines=60))
        out.append("")
    if not res["sources"]:
        out.append(yellow("No matching history. Try different words, or run `loreline index` first."))
        return "\n".join(out)
    out.append(bold("Sources"))
    for s in res["sources"][:12]:
        snip = (s.get("snip") or "").replace("\n", " ")
        out.append(f"  {cyan('[' + s['id'] + ']')} {s['title'][:90]}")
        if snip:
            out.append(dim("      " + snip[:140]))
    return "\n".join(out)
