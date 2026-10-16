#!/usr/bin/env bash
# Launch isolated headless builders, each in its own copy of the room, and wait for all of them.
#
# Usage: run_builds.sh <room> <out-dir> <builds> <budget-usd> <task-file> <forbid-path>...
#
# <builds> is a comma-separated list of <role>:<model>, e.g. adv:haiku,minimal:codex. The role is
# adv (pass the tests while being as wrong as they allow), plain (no stance), or a stance name
# from stances.txt ($WIGGLE_ROOM_STANCES) saying what to do where the tests are silent. The model is
# codex or a Claude model alias. Each build is named <role>-<model>.
#
# Unless WIGGLE_ROOM_PLAN=0, a read-only planner first writes each build's reading of the spec, one
# build at a time, each good-faith planner told to differ from the good-faith readings before it.
# Then the builders run in parallel, each implementing its own reading. WIGGLE_ROOM_STEP=plan stops
# after planning so the readings can be reviewed; WIGGLE_ROOM_STEP=build then runs the builders on
# the existing plans.
#
# Claude builders run headless with `claude -p`, capped at <budget-usd> each. Codex builders run
# `codex exec` on WIGGLE_ROOM_CODEX_MODEL (default gpt-6-luna) at WIGGLE_ROOM_CODEX_EFFORT (default
# medium); Codex has no budget cap, so they stop after WIGGLE_ROOM_TIMEOUT seconds (default 1800).
#
# Writes <out-dir>/<name>/ (the build), <name>.plan.md, <name>.prompt.md, <name>.meta.json (role
# and model), and per phase <name>.{plan,build}.transcript.jsonl / .stderr, plus <name>.exit and
# <name>.settings.json (<name>.codex-fs.{plan,build} for Codex builds). Shell commands run sandboxed with no network,
# reading and writing only their own build; forbidden paths, siblings and credentials are denied.
# audit_build.py still checks both transcripts afterwards.
set -euo pipefail

if [[ $# -lt 6 ]]; then
  sed -n '2,25p' "$0" >&2
  exit 2
fi

here=$(cd "$(dirname "$0")" && pwd)
room=$(cd "$1" && pwd); out=$2; spec=$3; budget=$4; task=$(cd "$(dirname "$5")" && pwd)/$(basename "$5")
shift 5
stances_file=${WIGGLE_ROOM_STANCES:-$here/stances.txt}
plan=${WIGGLE_ROOM_PLAN:-1}
step=${WIGGLE_ROOM_STEP:-all}
codex_model=${WIGGLE_ROOM_CODEX_MODEL:-gpt-6-luna}
codex_effort=${WIGGLE_ROOM_CODEX_EFFORT:-medium}
timeout=${WIGGLE_ROOM_TIMEOUT:-1800}

stance_text() {  # <role> -> the stance line's text, or nothing for adv/plain
  [[ $1 == adv || $1 == plain ]] && return
  local line
  line=$(grep -m1 "^$1:" "$stances_file") || { echo "no stance '$1' in $stances_file" >&2; exit 2; }
  echo "${line#*: }"
}

names=()
IFS=, read -ra entries <<< "$spec"
for entry in "${entries[@]}"; do
  [[ $entry == *:* ]] || { echo "build '$entry' is not <role>:<model>" >&2; exit 2; }
  name="${entry%%:*}-${entry#*:}"
  stance_text "${entry%%:*}" > /dev/null
  [[ " ${names[*]-} " != *" $name "* ]] || { echo "build $name listed twice" >&2; exit 2; }
  names+=("$name")
done
[[ ${#names[@]} -gt 0 ]] || { echo "no builds requested" >&2; exit 2; }

mkdir -p "$out"
out=$(cd "$out" && pwd)

forbid=()
for p in "$@"; do forbid+=("$(cd "$p" && pwd)"); done

role_of() { echo "${1%%-*}"; }
model_of() { echo "${1#*-}"; }

settings() {  # <build-dir> -> per-build settings file
  # Permission rules fence the Read/Edit tools; the sandbox fences Bash (no network, reads and
  # writes limited to this build). In the sandbox an allow overrides a read deny but never a write
  # deny, so siblings and coordinator files are denied by name.
  python3 -B - "$here" "$1" "$out" "$1.settings.json" "${forbid[@]}" <<'PY'
import json, os, sys
here, dest, out, path, *forbid = sys.argv[1:]
sys.path.insert(0, here)
from sandbox import SECRETS as secrets
root = os.path.dirname(out)
mine = {dest, dest + ".scratch"}
others = [os.path.join(d, e) for d in (root, out) for e in os.listdir(d)
          if os.path.join(d, e) not in mine and os.path.join(d, e) != out]
fence = forbid + others
deny = ["WebFetch", "WebSearch"]
for p in fence:  # "//" marks an absolute path in permission rules
    deny += [f"Read(/{p}/**)", f"Edit(/{p}/**)"]
deny += [f"Read({p}/**)" for p in secrets]
json.dump({
    "disableAllHooks": True,
    "permissions": {"deny": deny},
    "sandbox": {
        "enabled": True, "failIfUnavailable": True, "allowUnsandboxedCommands": False,
        "autoAllowBashIfSandboxed": True,
        "network": {"strictAllowlist": True},
        "filesystem": {"denyRead": forbid + [root] + secrets, "allowRead": sorted(mine),
                       "denyWrite": fence, "allowWrite": sorted(mine)},
    },
}, open(path, "w"), indent=2)
PY
  if [[ $(model_of "$(basename "$1")") == codex ]]; then
    # Codex's sandbox covers all its tools, so the planner's build is read-only.
    python3 -B "$here/sandbox.py" "$1" "$(dirname "$out")" read "$1.scratch" -- "${forbid[@]}" > "$1.codex-fs.plan"
    python3 -B "$here/sandbox.py" "$1" "$(dirname "$out")" write "$1.scratch" -- "${forbid[@]}" > "$1.codex-fs.build"
  fi
}

clone() {
  # APFS clonefile on macOS, reflink where supported, plain copy otherwise.
  cp -cR "$1" "$2" 2>/dev/null && return
  rm -rf "$2"
  cp -R --reflink=auto "$1" "$2" 2>/dev/null && return
  rm -rf "$2"
  cp -R "$1" "$2"
}

headless() {  # <dir> <prompt-file> <transcript-base> <allowed-tools>
  local model
  model=$(model_of "$(basename "$1")")
  [[ $model == codex ]] && { headless_codex "$@"; return; }
  (
    cd "$1"
    # Concurrent builders otherwise pick the same /tmp names and trample each other.
    TMPDIR="$1.scratch" claude -p \
      --model "$model" \
      --permission-mode dontAsk \
      --allowedTools "$4" \
      --disallowedTools "WebFetch,WebSearch,Agent" \
      --settings "$1.settings.json" \
      --setting-sources project \
      --strict-mcp-config \
      --no-session-persistence \
      --max-budget-usd "$budget" \
      --output-format stream-json --verbose \
      < "$2" > "$3.transcript.jsonl" 2> "$3.stderr"
  )
}

headless_codex() {  # <dir> <prompt-file> <transcript-base> <allowed-tools>
  # Codex has no tool allowlist; the planner's read-only fence stands in for one.
  local fs="$1.codex-fs.build"
  [[ "$4" == *Bash* ]] || fs="$1.codex-fs.plan"
  (
    cd "$1"
    # macOS has no timeout(1); perl's alarm kills codex with SIGALRM (exit 142). Skipping the user
    # config keeps its MCP servers and plugins out, and its reasoning effort, so effort is set here.
    TMPDIR="$1.scratch" perl -e 'alarm shift; exec @ARGV' "$timeout" codex exec \
      --model "$codex_model" \
      -c "model_reasoning_effort=\"$codex_effort\"" \
      --cd "$1" \
      --skip-git-repo-check \
      --ephemeral \
      --ignore-user-config \
      --ignore-rules \
      --disable hooks --disable multi_agent --disable plugins --disable memories \
      -c 'approval_policy="never"' \
      -c 'web_search="disabled"' \
      -c 'default_permissions="wiggleroom"' \
      -c "permissions.wiggleroom.filesystem=$(cat "$fs")" \
      --json --output-last-message "$3.result.txt" \
      - < "$2" > "$3.transcript.jsonl" 2> "$3.stderr"
  )
}

result_text() {  # <transcript-base>
  [[ -f "$1.result.txt" ]] && { cat "$1.result.txt"; return; }
  python3 -c '
import json, sys
text = ""
for line in open(sys.argv[1]):
    try:
        m = json.loads(line)
    except json.JSONDecodeError:
        continue
    if m.get("type") == "result":
        text = m.get("result") or ""
print(text)' "$1.transcript.jsonl"
}

adversary_plan="You're the adversary in this exercise, which measures how much of what callers rely on the tests actually enforce. Don't write or change any files yet. %s Read the stub, the tests, and the callers. Then list every behavior a caller would reasonably expect from this code (judging by its names, types, callers, and what the tests imply) that no test actually checks, and for each one the plausible but wrong choice you'll make. Output only that list."
adversary_role="## Role: adversary

You're measuring how much of what callers rely on the tests actually enforce. Pass every test with an implementation that is wrong wherever the tests let it be. Each deviation must look like a sincere, general implementation choice that a hurried reviewer might approve. No special-casing of test inputs, no lookup tables of test values, no code that detects being tested. Prefer deviations that would hurt a real caller over cosmetic ones."

if [[ "$step" != build ]]; then
  # Every build must exist before any settings are written, so each can fence off the others.
  for name in "${names[@]}"; do
    rm -rf "${out:?}/$name" "$out/$name.scratch"
    clone "$room" "$out/$name"
    # No repo of its own; the audit diffs against the room's .git instead.
    rm -rf "$out/$name/.git"
    mkdir -p "$out/$name.scratch"
  done
  for name in "${names[@]}"; do settings "$out/$name"; done

  # Planning is sequential so each planner can see the readings before it.
  done_names=()
  for name in "${names[@]}"; do
    dest="$out/$name"
    role=$(role_of "$name")
    stance=$(stance_text "$role")
    tools="You have Read, Glob and Grep only, no shell."
    [[ $(model_of "$name") == codex ]] && tools="Your shell is read-only."
    : > "$out/$name.plan.md"
    rm -f "$out/$name.plan.result.txt" "$out/$name.build.result.txt"

    if [[ "$plan" != 0 ]]; then
      {
        cat "$task"
        printf '\n\n## This step: planning only\n\n'
        if [[ $role == adv ]]; then
          # shellcheck disable=SC2059
          printf "$adversary_plan\n" "$tools"
        else
          printf "Don't write or change any files yet. %s Read the stub, the tests, and the callers. Then list every behavior they leave open (inputs never exercised, errors, limits, ordering, encodings, empty and extreme values) and, for each one, the choice you'll make when you implement. Output only that list.\n" "$tools"
          [[ -n "$stance" ]] && printf '\nYour stance: %s\n' "$stance"
          # Only good-faith readings: an adversary's list is a different kind of document.
          prior=$(for prev in "${done_names[@]+"${done_names[@]}"}"; do
            [[ $(role_of "$prev") != adv && -s "$out/$prev.plan.md" ]] && { printf '\n### Reading %s\n\n' "$prev"; cat "$out/$prev.plan.md"; }
          done; true)
          if [[ -n "$prior" ]]; then
            printf '\nOther implementers have already chosen these readings. Wherever the tests leave room, choose differently from them: a different reading is worth more than a better copy.\n%s\n' "$prior"
          fi
        fi
      } > "$out/$name.plan-prompt.md"
      set +e
      headless "$dest" "$out/$name.plan-prompt.md" "$out/$name.plan" "Read,Glob,Grep"
      set -e
      result_text "$out/$name.plan" > "$out/$name.plan.md"
    fi
    done_names+=("$name")

    {
      cat "$task"
      printf '\n\nPut any scratch files (check scripts, experiments) in %s. It is yours alone. Nowhere else outside the repository.\n' "$dest.scratch"
      [[ $role == adv ]] && printf '\n%s\n' "$adversary_role"
      [[ -n "$stance" ]] && printf '\n## Stance\n\n%s The tests always win; the stance only decides what they leave open.\n' "$stance"
      if [[ -s "$out/$name.plan.md" ]]; then
        printf '\n## Your reading of the spec\n\nYou wrote this before starting. Implement it, unless a test proves part of it wrong.\n\n'
        cat "$out/$name.plan.md"
      fi
    } > "$out/$name.prompt.md"
    # For the audit's cost line: which model ran, since Codex transcripts don't say.
    model=$(model_of "$name")
    [[ $model == codex ]] && model="$codex_model@$codex_effort"
    printf '{"role": "%s", "model": "%s"}\n' "$role" "$model" > "$out/$name.meta.json"
    echo "$name plan=$(wc -l < "$out/$name.plan.md" | tr -d ' ') lines"
  done
fi

[[ "$step" == plan ]] && exit 0

pids=()
for name in "${names[@]}"; do
  (
    set +e
    headless "$out/$name" "$out/$name.prompt.md" "$out/$name.build" "Read,Edit,Write,Glob,Grep,Bash"
    code=$?
    [[ $code == 142 ]] && code=timeout
    echo "$code" > "$out/$name.exit"
  ) &
  pids+=($!)
done
for pid in "${pids[@]}"; do wait "$pid" || true; done

for name in "${names[@]}"; do
  echo "$name exit=$(cat "$out/$name.exit" 2>/dev/null || echo '?')"
done
