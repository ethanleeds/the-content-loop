#!/usr/bin/env bash
# Runs the weekly loop. Schedule with cron, e.g. Mondays 7am:
# 0 7 * * 1 /path/to/repo/scripts/weekly.sh
cd "$(dirname "$0")/.." || exit 1
claude -p "Use the content-agent subagent to run the weekly loop" >> scripts/weekly.log 2>&1
