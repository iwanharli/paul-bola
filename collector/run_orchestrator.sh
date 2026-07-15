#!/bin/bash
# Wrapper for cron: cron runs with a minimal environment, so we cd into the
# project dir explicitly and use the venv's python directly rather than
# relying on PATH/shell activation.
set -e
cd "$(dirname "$0")"
LOG_FILE="../cron.log"
{
  echo "=== Run started: $(date) ==="
  ../venv/bin/python orchestrate.py
  echo "=== Run finished: $(date) ==="
} >> "$LOG_FILE" 2>&1
