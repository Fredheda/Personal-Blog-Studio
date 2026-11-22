#!/usr/bin/env bash
set -uo pipefail
cd "$(dirname "$0")/../.."

status=0
for rule in pr_size spec_location shared_block comment_count comment_content plan_diagram; do
  python3 "scripts/rules/$rule.py" || status=1
done
exit "$status"
