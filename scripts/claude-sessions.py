#!/usr/bin/env python3
"""fzf picker over every Claude Code session, newest first.

Enter opens the session in a new tmux window: cd into the session's directory
and run `<command> --resume <id>`. A session that is already running (green
dot) is focused in its pane instead.

Sessions live in <claude config dir>/projects/<dir>/<session-id>.jsonl and grow
to gigabytes, so the per-file facts (cwd, title, first prompt) are cached by
path + mtime + size.
"""
import json
import os
import re
import shlex
import subprocess
import sys
import time
from pathlib import Path

CLAUDE_DIR = Path(os.environ.get("CLAUDE_CONFIG_DIR") or Path.home() / ".claude")
PROJECTS = CLAUDE_DIR / "projects"
CACHE = Path(os.environ.get("XDG_CACHE_HOME") or Path.home() / ".cache") / "tmux-claude-sessions.json"
HEAD_BYTES = 2 << 20  # cwd and the first prompt sit in the first lines
TAIL_BYTES = 1 << 20  # the latest custom-title record is re-written near the end
SKIP_CWD = ("/private/tmp/", "/tmp/", "/private/var/", "/var/folders/")  # throwaway runs


def prompt_text(rec):
    """The typed text of a human prompt record, or None for tool results."""
    if rec.get("type") != "user" or rec.get("isSidechain") or rec.get("isMeta") \
            or rec.get("isCompactSummary"):
        return None
    content = rec.get("message", {}).get("content")
    if isinstance(content, list):
        content = " ".join(c.get("text", "") for c in content if c.get("type") == "text")
    if not isinstance(content, str):
        return None
    text = " ".join(content.split())
    if not text or text.startswith("<"):  # <command-name>, <local-command-stdout>, ...
        return None
    return text


def scan(path):
    """Read cwd, branch and first prompt from the head, the title from the tail."""
    info = {"cwd": None, "branch": "", "first": "", "title": ""}
    with open(path, "rb") as f:
        for line in f.read(HEAD_BYTES).splitlines():
            if info["cwd"] and info["first"]:
                break
            if b'"cwd"' not in line and b'"type":"user"' not in line:
                continue
            try:
                rec = json.loads(line)
            except ValueError:
                continue
            if not info["cwd"] and rec.get("cwd"):
                info["cwd"] = rec["cwd"]
                info["branch"] = rec.get("gitBranch") or ""
            if not info["first"]:
                info["first"] = prompt_text(rec) or ""
        size = f.seek(0, os.SEEK_END)
        f.seek(max(0, size - TAIL_BYTES))
        for line in reversed(f.read().splitlines()):
            if b'"custom-title"' in line:
                try:
                    info["title"] = json.loads(line).get("customTitle") or ""
                    break
                except ValueError:
                    continue
    return info


def load_sessions():
    try:
        cache = json.loads(CACHE.read_text())
    except (OSError, ValueError):
        cache = {}
    fresh, sessions = {}, []
    for path in PROJECTS.glob("*/*.jsonl"):
        st = path.stat()
        key = str(path)
        stamp = [st.st_mtime, st.st_size]
        hit = cache.get(key)
        info = hit["info"] if hit and hit["stamp"] == stamp else scan(path)
        fresh[key] = {"stamp": stamp, "info": info}
        cwd = info["cwd"]
        if not cwd or not info["first"] or cwd.startswith(SKIP_CWD):
            continue
        sessions.append((st.st_mtime, path, info))
    CACHE.parent.mkdir(parents=True, exist_ok=True)
    CACHE.write_text(json.dumps(fresh))
    sessions.sort(key=lambda s: s[0], reverse=True)
    return sessions


def live_panes():
    """Session id -> tmux target for each running claude, from <claude dir>/sessions/<pid>.json.

    The record's "tmux" field reads "<session>:<window id>.<pane id>", e.g. "0:@203.%244".
    """
    live = {}
    for f in (CLAUDE_DIR / "sessions").glob("*.json"):
        try:
            rec = json.loads(f.read_text())
            os.kill(rec["pid"], 0)  # stale file of an exited claude raises
        except (OSError, ValueError, KeyError):
            continue
        if rec.get("tmux") and rec.get("sessionId"):
            live[rec["sessionId"]] = rec["tmux"]
    return live


def ago(ts):
    s = time.time() - ts
    for unit, n in (("d", 86400), ("h", 3600), ("m", 60)):
        if s >= n:
            return f"{int(s // n)}{unit} ago"
    return "now"


def preview(path):
    """Session facts plus its last human prompts, for the fzf preview pane."""
    info = scan(path)
    prompts = []
    with open(path, "rb") as f:
        for line in f:
            if b'"type":"user"' not in line:
                continue
            try:
                text = prompt_text(json.loads(line))
            except ValueError:
                continue
            if text:
                prompts.append(text)
    mtime = os.path.getmtime(path)
    print(f"\033[1m{info['title'] or Path(path).stem}\033[0m")
    print(f"dir:     {info['cwd']}" + ("" if os.path.isdir(info["cwd"] or "") else "  (missing)"))
    print(f"branch:  {info['branch']}")
    print(f"updated: {time.strftime('%Y-%m-%d %H:%M', time.localtime(mtime))} ({ago(mtime)})")
    print(f"prompts: {len(prompts)}\n")
    for p in prompts[-8:]:
        print(f"\033[36m❯\033[0m {p[:400]}\n")


def main():
    if len(sys.argv) == 3 and sys.argv[1] == "--preview":
        return preview(sys.argv[2])

    home = str(Path.home())
    live = live_panes()
    rows = []
    # Fields: path, session id, cwd, title (hidden; read back on Enter), display line.
    for mtime, path, info in load_sessions():
        cwd = info["cwd"]
        short = cwd.replace(home, "~", 1)
        label = info["title"] or info["first"]
        when = time.strftime("%m-%d %H:%M", time.localtime(mtime))
        mark = "" if os.path.isdir(cwd) else " \033[31m(gone)\033[0m"
        dot = "\033[32m●\033[0m" if path.stem in live else " "
        rows.append("\t".join([
            str(path), path.stem, cwd, info["title"].replace("\t", " "),
            f"{dot} \033[33m{when}\033[0m  \033[34m{short[-38:]:<38}\033[0m  {label[:120]}{mark}",
        ]))

    me = shlex.quote(os.path.abspath(__file__))
    out = subprocess.run(
        ["fzf", "--ansi", "--height=100%", "--layout=reverse", "--prompt=claude ❯ ",
         "--delimiter=\t", "--with-nth=5", "--no-sort",
         "--preview", f"{me} --preview {{1}}",
         "--preview-window=right,45%,border-left,wrap"],
        input="\n".join(rows), stdout=subprocess.PIPE, text=True,
    )
    if out.returncode != 0 or not out.stdout.strip():
        return
    _, sid, cwd, title, _ = out.stdout.rstrip("\n").split("\t", 4)
    if sid in live:
        # Already running: jump to its pane instead of a second claude on the same log.
        sess, rest = live[sid].split(":", 1)
        window, pane = rest.split(".", 1)
        subprocess.run(["tmux", "switch-client", "-t", sess, ";",
                        "select-window", "-t", window, ";", "select-pane", "-t", pane])
        return
    if not os.path.isdir(cwd):
        subprocess.run(["tmux", "display-message", f"claude session dir is gone: {cwd}"])
        return
    # A trailing "(...)" is a status some setups append to the title ("fix-login (CI passed)").
    name = re.sub(r" \([^)]*\)$", "", title) or os.path.basename(cwd) or "claude"
    command = subprocess.run(["tmux", "show-option", "-gqv", "@claude-sessions-command"],
                             stdout=subprocess.PIPE, text=True).stdout.strip() or "claude"
    subprocess.run(["tmux", "new-window", "-n", name, "-c", cwd,
                    f"{command} --resume {shlex.quote(sid)}"])


if __name__ == "__main__":
    main()
