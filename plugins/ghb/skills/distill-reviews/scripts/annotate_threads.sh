#!/bin/bash
# usage: annotate_threads.sh <prs_dir> <out.json>
# Per-thread evidence computed deterministically, because gatherer agents misread or
# invent it. isOutdated (the commented lines changed afterward) is the useful fix signal;
# commits_after is weak since nearly every thread is followed by some commit.
set -euo pipefail
jq -s '[.[] | . as $p | .threads[] | .comments[0].at as $t | {pr:$p.number, path, isResolved, isOutdated,
  opened_by:.comments[0].by, opened_at:$t, replies:(.comments|length-1),
  commits_after:[$p.commits[] | select(.at > $t) | "\(.sha) \(.msg)"]}]' "$1"/*.json > "$2"
jq '{threads:length, outdated:(map(select(.isOutdated))|length),
  by_opener:(group_by(.opened_by)|map({(.[0].opened_by):length})|add)}' "$2"
