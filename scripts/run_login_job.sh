#!/bin/zsh
set -euo pipefail

REPO_ROOT="/Users/emilygao/LocalDocuments/Projects/langchain/deep-agents"
PYTHON_BIN="$REPO_ROOT/.venv/bin/python"

cd "$REPO_ROOT"
export PYTHONDONTWRITEBYTECODE=1
export DEEP_AGENTS_SOURCE_MODE=live

exec "$PYTHON_BIN" main.py --live-email --live-discord
