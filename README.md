# tmux-claude-sessions

A tmux popup that lists every [Claude Code](https://claude.com/claude-code) session you've had, in every directory, newest first. Pick one and it opens in a new tmux window, in the session's directory, with `claude --resume`.

## Usage

Press `prefix + e`. The popup lists one session per line: the last update time, the directory, and the session's title or, for an untitled session, its first prompt.

- **Search.** Type to fuzzy-search across the date, directory, title and first prompt.
- **Preview.** The right side shows the session's directory, git branch, last update, prompt count and its last 8 prompts.
- **Open.** Enter opens a new tmux window in the session's directory and runs `claude --resume <session id>`. The window takes the session's title as its name, or the directory's name for an untitled session.
- **Jump to a running session.** A green `●` marks a session that is open in a tmux pane right now. Enter on it switches to that pane instead of starting a second `claude` on the same session.
- **Close.** Esc closes the popup.

A session whose directory no longer exists, such as a removed git worktree, shows `(gone)`. Picking it shows a tmux message instead of opening a window.

The list leaves out sessions started under `/tmp`, `/private/tmp`, `/private/var` or `/var/folders`, and sessions with no typed prompt, such as one opened and closed straight away.

## Requirements

- tmux 3.2 or later, for `display-popup`. Tested on tmux 3.6b.
- [fzf](https://github.com/junegunn/fzf). Tested on fzf 0.70.
- Python 3.8 or later as `python3`. The picker uses only the standard library.
- Claude Code. Tested on version 2.1.

## Install

With [tpm](https://github.com/tmux-plugins/tpm), add to `~/.tmux.conf`:

```tmux
set -g @plugin 'perzhul/tmux-claude-sessions'
```

Then press `prefix + I`.

Without tpm, clone the repository and run the plugin from `~/.tmux.conf`:

```sh
git clone https://github.com/perzhul/tmux-claude-sessions ~/.tmux/plugins/tmux-claude-sessions
```

```tmux
run-shell ~/.tmux/plugins/tmux-claude-sessions/claude-sessions.tmux
```

## Options

Set an option before the plugin line in `~/.tmux.conf` to override it.

| Option | Default | Description |
| ------ | ------- | ----------- |
| `@claude-sessions-key` | `e` | Key after the prefix that opens the popup |
| `@claude-sessions-width` | `80%` | Popup width, in cells or as a percentage of the client |
| `@claude-sessions-height` | `80%` | Popup height, in cells or as a percentage of the client |
| `@claude-sessions-command` | `claude` | Command that resumes a session; the picker appends `--resume <session id>` |

Use `@claude-sessions-command` to add flags, for example `claude --permission-mode plan`.

## How it works

- Claude Code writes each session to `~/.claude/projects/<directory>/<session id>.jsonl`. The picker reads the directory, git branch and first prompt from the start of each file, and the latest title from its last megabyte. `CLAUDE_CONFIG_DIR` replaces `~/.claude` when it is set.
- These files can add up to gigabytes, so the picker caches what it read in `~/.cache/tmux-claude-sessions.json`, keyed by each file's modification time and size. On one machine with 1.7 GB of sessions, the first run took 2.1 s and a cached run 0.01 s.
- A running Claude Code writes `~/.claude/sessions/<pid>.json` with its session id and tmux pane. The picker marks a session as running only while that process is alive.
- These file formats are Claude Code internals, not a documented API. A Claude Code update can change them and break the picker.

## Uninstall

Remove the plugin line from `~/.tmux.conf`, press `prefix + alt + u` to let tpm delete the plugin, and delete `~/.cache/tmux-claude-sessions.json`. tmux keeps the key binding until the server restarts.
