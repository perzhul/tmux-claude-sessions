#!/usr/bin/env bash

CURRENT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PICKER="$CURRENT_DIR/scripts/claude-sessions.py"
chmod +x "$PICKER"

# Defaults only when unset: respect user overrides.
default() { [ -n "$(tmux show-options -gqv "$1")" ] || tmux set-option -g "$1" "$2"; }
default @claude-sessions-key 'e'
default @claude-sessions-width '80%'
default @claude-sessions-height '80%'
default @claude-sessions-command 'claude'

opt() { tmux show-options -gv "$1"; }
tmux bind-key "$(opt @claude-sessions-key)" display-popup -E \
    -w "$(opt @claude-sessions-width)" -h "$(opt @claude-sessions-height)" "$PICKER"
