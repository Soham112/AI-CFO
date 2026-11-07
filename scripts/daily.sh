#!/usr/bin/env bash
# Daily DICFO run for macOS/Linux. Schedule with:  crontab -e
#   30 8 * * 1-5  /path/to/DICFO/scripts/daily.sh dad >> /path/to/DICFO/daily.log 2>&1
set -euo pipefail
cd "$(dirname "$0")/.."
PROFILE="${1:-${DICFO_PROFILE:-dad}}"
# Optional: let Claude Code add today's news/policy judgement first (needs Claude Code installed + signed in)
if command -v claude >/dev/null 2>&1 && [ "${DICFO_USE_CLAUDE:-0}" = "1" ]; then
  claude -p "Use the cfo-market-data and cfo-news-policy skills to write today's overrides files for DICFO. Do not run the report." \
    --allowedTools "Bash(.venv/bin/python:*) WebSearch WebFetch Read Write" || true
fi
.venv/bin/python -m dicfo daily --profile "$PROFILE" --notify "${DICFO_NOTIFY:-telegram,email}"
