#!/bin/zsh
set -euo pipefail

REPO_ROOT="/Users/emilygao/LocalDocuments/Projects/langchain/deep-agents"
PLIST_SOURCE="$REPO_ROOT/launchd/com.emilyg888.deep-agents.login.plist"
LAUNCH_AGENTS_DIR="$HOME/Library/LaunchAgents"
PLIST_TARGET="$LAUNCH_AGENTS_DIR/com.emilyg888.deep-agents.login.plist"

mkdir -p "$LAUNCH_AGENTS_DIR"
mkdir -p "$REPO_ROOT/logs"
cp "$PLIST_SOURCE" "$PLIST_TARGET"

launchctl unload "$PLIST_TARGET" >/dev/null 2>&1 || true
launchctl load "$PLIST_TARGET"

echo "Installed LaunchAgent at $PLIST_TARGET"
echo "It will run once at login and is loaded now."
