#!/usr/bin/env python3
"""Render demo/screenshot.png: the picker over seeded sessions.

Seeds a fake home and Claude config dir in a temp dir, runs the picker on a
private tmux server, captures the pane and draws it with JetBrains Mono.

Usage: uv run --with pyte --with pillow demo/make-screenshot.py [--font-dir DIR] [--out PATH]
"""
import argparse
import json
import os
import pathlib
import subprocess
import tempfile
import time
import uuid

import pyte
from PIL import Image, ImageDraw, ImageFont

COLS, ROWS = 132, 20
REPO = pathlib.Path(__file__).resolve().parent.parent
SERVER = "tmux-claude-sessions-demo"

# Claude Code writes compact JSON; the picker matches '"type":"user"' without spaces.
# (dir under the fake home, branch, title, prompts, minutes ago, dir exists)
SESSIONS = [
    ("code/api", "fix/retry-backoff", "fix-flaky-retry-test", [
        "TestRetry fails about 1 run in 20 on CI, find out why",
        "so jitter can make the 2nd wait shorter than the 1st?",
        "cap jitter at half the base delay, add a test",
        "run the queue package 50 times and show failures",
    ], 3, True),
    ("code/web", "main", "", ["add a dark mode toggle to the settings page, keep the choice in localStorage"], 41, True),
    ("code/api", "main", "", ["why does GET /invoices return 500 when the cursor is empty?"], 95, True),
    ("dotfiles", "main", "tmux-popup-keys", ["bind prefix + g to open lazygit in a popup"], 60 * 5, True),
    ("code/billing", "cents", "invoices-in-cents", ["migrate invoice amounts from float dollars to integer cents"], 60 * 26, True),
    ("code/api-auth-wt", "rotate-tokens", "", ["rotate session tokens when the user changes their password"], 60 * 49, False),
    ("notes", "", "", ["summarize this week's standup notes into five bullets"], 60 * 74, True),
    ("code/cli", "release", "release-1.4", ["write the changelog for v1.4.0 from the merged PRs"], 60 * 24 * 6, True),
]

PALETTE = {
    "black": (40, 42, 46), "red": (224, 108, 117), "green": (152, 195, 121), "brown": (229, 192, 123),
    "yellow": (229, 192, 123), "blue": (97, 175, 239), "magenta": (198, 120, 221), "cyan": (86, 182, 194),
    "white": (220, 223, 228),
}
BG, FG = (30, 31, 34), (204, 206, 210)
CAPTION_BAR = 40


def seed(tmp):
    """Fake home with session logs; the first session counts as running."""
    home, claude = tmp / "home", tmp / "claude"
    (claude / "sessions").mkdir(parents=True)
    now = time.time()
    for i, (rel, branch, title, prompts, ago, exists) in enumerate(SESSIONS):
        cwd = home / rel
        if exists:
            cwd.mkdir(parents=True, exist_ok=True)
        sid = str(uuid.uuid5(uuid.NAMESPACE_URL, f"demo-{i}"))
        project = claude / "projects" / str(cwd).replace("/", "-")
        project.mkdir(parents=True, exist_ok=True)
        lines = [{"type": "user", "cwd": str(cwd), "gitBranch": branch, "sessionId": sid,
                  "message": {"role": "user", "content": p}} for p in prompts]
        if title:
            lines.append({"type": "custom-title", "customTitle": title, "sessionId": sid})
        log = project / f"{sid}.jsonl"
        log.write_text("".join(json.dumps(line, separators=(",", ":")) + "\n" for line in lines))
        os.utime(log, (now - ago * 60, now - ago * 60))
        if i == 0:  # this script's own pid stays alive while the picker reads it
            (claude / "sessions" / f"{os.getpid()}.json").write_text(json.dumps(
                {"pid": os.getpid(), "sessionId": sid, "tmux": "demo:@1.%1"}))
    return home, claude


def tmux(*args):
    return subprocess.run(["tmux", "-L", SERVER, "-f", "/dev/null", *args],
                          check=True, capture_output=True, text=True).stdout


def color(value, default):
    if value == "default":
        return default
    name = value.removeprefix("bright")
    if name in PALETTE:
        return PALETTE[name]
    return tuple(int(value[i:i + 2], 16) for i in (0, 2, 4))


def render(screen, font_dir, caption):
    font = ImageFont.truetype(str(font_dir / "JetBrainsMono-Regular.ttf"), 16)
    bold = ImageFont.truetype(str(font_dir / "JetBrainsMono-Bold.ttf"), 16)
    ascent, descent = font.getmetrics()
    cw, ch = font.getlength("M"), ascent + descent
    width, height = round(cw * COLS) + 24, round(ch * ROWS) + CAPTION_BAR + 12
    img = Image.new("RGB", (width, height), BG)
    draw = ImageDraw.Draw(img)
    draw.rectangle([0, 0, width, CAPTION_BAR], fill=(22, 23, 25))
    for i, dot in enumerate([(255, 95, 87), (254, 188, 46), (40, 200, 64)]):
        draw.ellipse([14 + i * 20, 14, 26 + i * 20, 26], fill=dot)
    draw.text((width / 2, CAPTION_BAR / 2), caption, font=bold, fill=(235, 236, 238), anchor="mm")
    ox, oy = 12, CAPTION_BAR + 6
    for y in range(ROWS):
        for x in range(COLS):
            char = screen.buffer[y][x]
            fg, bg = color(char.fg, FG), color(char.bg, BG)
            if char.reverse:
                fg, bg = bg, fg
            left, top = ox + x * cw, oy + y * ch
            if bg != BG:
                draw.rectangle([left, top, left + cw, top + ch], fill=bg)
            if char.data.strip():
                draw.text((left, top), char.data, font=bold if char.bold else font, fill=fg)
    return img


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--font-dir", type=pathlib.Path, default=pathlib.Path.home() / "Library/Fonts")
    parser.add_argument("--out", type=pathlib.Path, default=REPO / "demo" / "screenshot.png")
    args = parser.parse_args()

    # Not under /tmp or /var/folders: the picker hides sessions started there.
    with tempfile.TemporaryDirectory(dir=REPO / "demo") as tmp:
        tmp = pathlib.Path(tmp)
        home, claude = seed(tmp)
        picker = REPO / "scripts" / "claude-sessions.py"
        env = f"env HOME={home} CLAUDE_CONFIG_DIR={claude} XDG_CACHE_HOME={tmp / 'cache'}"
        tmux("new-session", "-d", "-s", "demo", "-x", str(COLS), "-y", str(ROWS), f"{env} {picker}")
        tmux("set", "-g", "status", "off")
        try:
            screen = None
            for _ in range(60):  # wait for the list and the preview of the top row
                time.sleep(0.1)
                screen = pyte.Screen(COLS, ROWS)
                pyte.Stream(screen).feed("\r\n".join(tmux("capture-pane", "-e", "-p", "-t", "demo").split("\n")[:ROWS]))
                text = "\n".join(screen.display)
                if "fix-flaky-retry-test" in text and "run the queue package" in text:
                    break
            else:
                raise RuntimeError("picker never drew:\n" + "\n".join(screen.display))
        finally:
            tmux("kill-server")

    img = render(screen, args.font_dir, "prefix + e")
    # A 64-colour palette PNG keeps it small. Octree keeps the one-pixel-wide accent
    # colours (the green dot, the red cross) that median cut merges into the background.
    img.quantize(colors=64, method=Image.Quantize.FASTOCTREE, dither=Image.Dither.NONE).save(args.out, optimize=True)
    print(f"{args.out} {args.out.stat().st_size // 1024} KB")


if __name__ == "__main__":
    main()
