# tmux-claude-sessions

A tmux popup that lists your [Claude Code](https://claude.com/claude-code) sessions from every directory, newest first, and resumes the one you pick in a new window.

![The picker listing eight sessions, with a preview of the selected one](demo/screenshot.png)

## Usage

Press `prefix + e` and type to fuzzy-search dates, directories, titles and first prompts. The preview shows the session's branch, prompt count and last prompts.

Enter opens a tmux window in the session's directory and runs `claude --resume <id>`. A green `●` marks a session already open in a pane; Enter switches to that pane. A red `✗` marks a session whose directory is gone.

The list skips sessions started under `/tmp` or `/var/folders` and sessions with no typed prompt.

## Install

Requires tmux 3.2+, [fzf](https://github.com/junegunn/fzf) and `python3`. With [tpm](https://github.com/tmux-plugins/tpm), add to `~/.tmux.conf` and press `prefix + I`:

```tmux
set -g @plugin 'perzhul/tmux-claude-sessions'
```

## Options

| Option | Default | |
| ------ | ------- | - |
| `@claude-sessions-key` | `e` | Key after the prefix |
| `@claude-sessions-width` | `80%` | Popup width |
| `@claude-sessions-height` | `80%` | Popup height |
| `@claude-sessions-command` | `claude` | Command the picker appends `--resume <id>` to |

## How it works

The picker reads Claude Code's session logs in `~/.claude/projects` (or `$CLAUDE_CONFIG_DIR`) and caches what it needs in `~/.cache/tmux-claude-sessions.json`, so a 1.7 GB history lists in 0.01 s after the first 2 s run. Running sessions come from `~/.claude/sessions/<pid>.json`. Both are Claude Code internals, so an update can break the picker.
