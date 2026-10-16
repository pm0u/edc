#!/usr/bin/env python3
"""Audit one wiggle-room build: what it changed, what its transcript touched, and whether tests pass.

Isolation while building is enforced by run_builds.sh (sandbox and deny rules). This lists the
paths outside the build that the transcripts referenced, so a copy of the original the fence didn't
know about (another clone, a vendored copy) can be spotted. The tests run the build's own code, so
they run inside the same fence (sandbox.py).

Verdict, first match wins:
  out-of-bounds  changed files outside the target paths, or symlinks (tests not run)
  red            the test command fails (re-run here, never taken from the builder)
  green          eligible for the probe diff
"""
import argparse
import json
import os
import re
import subprocess
import sys
import tempfile
from pathlib import Path

import sandbox

ABS_PATH = re.compile(r"(?<![\w.])(/(?:Users|home|private|tmp|var|opt|Volumes)/[^\s\"'`;|&)]+)")
STRING_LIT = re.compile(r"""(["'`])((?:(?!\1)[^\\\n]|\\.){4,80})\1""")

# Codex reports no cost. $/M tokens (input, cached input, cache writes, output) at short context,
# from OpenAI's price list as of 2026-10. Requests over 272K input tokens cost more, but Codex's
# JSON only gives per-turn totals, so the estimate assumes no request crossed that line.
CODEX_PRICES = {
    "gpt-6-luna": (0.10, 0.01, 0.125, 0.50),
    "gpt-6.1-sol": (2.00, 0.10, 2.50, 10.00),
    "gpt-6-astra": (10.00, 1.00, 12.50, 50.00),
}


def codex_cost(transcripts, model):
    prices = CODEX_PRICES.get(model.split("@")[0])
    if not prices:
        return None
    total = 0.0
    for t in transcripts:
        for line in open(t):
            try:
                m = json.loads(line)
            except json.JSONDecodeError:
                continue
            if m.get("type") != "turn.completed":
                continue
            u = m.get("usage") or {}
            # Assumes input_tokens includes cached and cache-write tokens; writes were 0 in every
            # run so far, so that part is unverified.
            cached, writes = u.get("cached_input_tokens") or 0, u.get("cache_write_input_tokens") or 0
            fresh = max((u.get("input_tokens") or 0) - cached - writes, 0)
            total += fresh * prices[0] + cached * prices[1] + writes * prices[2] + (u.get("output_tokens") or 0) * prices[3]
    return total / 1e6


def git(git_dir, build, *a):
    return subprocess.run(["git", f"--git-dir={git_dir}", f"--work-tree={build}", "-C", build, *a],
                          capture_output=True, text=True).stdout


def tool_uses(transcript):
    with open(transcript) as f:
        for line in f:
            try:
                msg = json.loads(line)
            except json.JSONDecodeError:
                continue
            if msg.get("type") == "result":
                yield "result", msg
            # codex exec --json: one turn per run, no cost, and tool calls arrive as items.
            if msg.get("type") in ("turn.completed", "turn.failed"):
                yield "result", {"subtype": "success" if msg["type"] == "turn.completed" else "error",
                                 "num_turns": 1}
            item = msg.get("item")
            if msg.get("type") == "item.completed" and isinstance(item, dict):
                if item.get("type") in ("command_execution", "file_change"):
                    yield "tool", {"input": {k: item.get(k) for k in ("command", "changes")}}
            # Some lines (e.g. permission_denied) carry message as a plain string.
            body = msg.get("message")
            content = body.get("content") if isinstance(body, dict) else None
            for block in content if isinstance(content, list) else []:
                if isinstance(block, dict) and block.get("type") == "tool_use":
                    yield "tool", block


def tokens(transcripts):
    """Token totals per transcript. Codex reports no cost, so tokens are what compares a Codex
    build with a Claude one."""
    total = {"input": 0, "cache_read": 0, "output": 0}

    def add(inp, cache_read, out):
        total["input"] += inp
        total["cache_read"] += cache_read
        total["output"] += out

    for t in transcripts:
        result, messages = None, {}
        for line in open(t):
            try:
                m = json.loads(line)
            except json.JSONDecodeError:
                continue
            if m.get("type") == "turn.completed":  # codex: input_tokens includes the cached ones
                u = m.get("usage") or {}
                cached = u.get("cached_input_tokens") or 0
                add((u.get("input_tokens") or 0) - cached, cached, u.get("output_tokens") or 0)
            elif m.get("type") == "result" and m.get("usage"):
                result = m["usage"]
            body = m.get("message")
            if isinstance(body, dict) and body.get("role") == "assistant" and body.get("usage"):
                messages[body.get("id")] = body["usage"]
        # claude -p streams each response's usage before the response finishes, so its per-message
        # output counts are partial; the result line has the totals. Session transcripts have no
        # result line, and every line of a response carries its final usage.
        for u in [result] if result else messages.values():
            add((u.get("input_tokens") or 0) + (u.get("cache_creation_input_tokens") or 0),
                u.get("cache_read_input_tokens") or 0, u.get("output_tokens") or 0)
    return total


def under(rel, prefixes):
    return any(rel == p or rel.startswith(p + "/") for p in prefixes)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--build", required=True)
    ap.add_argument("--base", required=True, help="room base commit")
    ap.add_argument("--git-dir", required=True, help="the room's .git (builds carry no repo of their own)")
    ap.add_argument("--transcript", nargs="+", required=True, help="every transcript for this build (plan and build)")
    ap.add_argument("--target", nargs="+", required=True, help="repo-relative paths the builder may change")
    ap.add_argument("--test-cmd", required=True)
    ap.add_argument("--test-file", nargs="*", default=[], help="build-relative test files, for the literal check")
    ap.add_argument("--run-root", required=True, help="the wiggle-room run ($OUT), fenced off from the tests")
    ap.add_argument("--forbid", nargs="+", required=True, help="the repo and its worktrees, fenced off from the tests")
    ap.add_argument("--timeout", type=int, default=900)
    args = ap.parse_args()

    build = str(Path(args.build).resolve())
    targets = [t.strip("/") for t in args.target]

    changed = set(git(args.git_dir, build, "diff", "--name-only", args.base).split())
    changed |= set(git(args.git_dir, build, "ls-files", "--others", "--exclude-standard").split())
    out_of_bounds = sorted(f for f in changed if not under(f, targets) or sandbox.escapes(build, f))

    outside, cost, turns, result = set(), 0.0, 0, {}
    events = ((k, i) for t in args.transcript for k, i in tool_uses(t))
    for kind, item in events:
        if kind == "result":
            result = item  # the last transcript given is the build; its result is the builder's
            cost += item.get("total_cost_usd") or 0
            turns += item.get("num_turns") or 0
            continue
        for p in ABS_PATH.findall(json.dumps(item.get("input", {}))):
            p = os.path.realpath(p.rstrip("/.,"))  # /tmp vs /private/tmp
            if not (p == build or p.startswith(build + "/") or p.startswith(build + ".scratch")):
                outside.add(p)

    literals = set()
    for tf in args.test_file:
        path = Path(build) / tf
        if path.is_file() and not sandbox.escapes(build, tf):
            literals |= {m.group(2) for m in STRING_LIT.finditer(path.read_text("utf-8", "replace"))}
    impl_text = ""
    for f in changed:
        p = Path(build) / f
        if f not in out_of_bounds and p.is_file():
            impl_text += p.read_text("utf-8", "replace")
    in_impl = sorted(l for l in literals if l in impl_text)

    # The test command is the coordinator's own; what it executes is the builder's.
    tests_pass, tail = None, "not run: out of bounds"
    if not out_of_bounds:
        with tempfile.TemporaryDirectory() as tmp:
            try:
                run = sandbox.run(args.test_cmd, build, args.run_root, args.forbid, writable=[tmp],
                                  env={"TMPDIR": tmp}, timeout=args.timeout)
                tests_pass, tail = run.returncode == 0, (run.stdout + run.stderr)[-1500:]
            except subprocess.TimeoutExpired:
                tests_pass, tail = False, "timed out"

    # claude -p reports its own cost; Codex's is estimated from tokens.
    meta_path = Path(build + ".meta.json")
    meta = json.loads(meta_path.read_text()) if meta_path.exists() else {}
    basis = "reported" if cost else None
    if not cost:
        cost = codex_cost(args.transcript, meta.get("model") or "")
        basis = "estimate" if cost is not None else None

    verdict = "out-of-bounds" if out_of_bounds else "green" if tests_pass else "red"
    json.dump({
        "build": build,
        "verdict": verdict,
        "changed": sorted(changed),
        "out_of_bounds": out_of_bounds,
        "outside_paths": sorted(outside)[:50],
        "test_literals_in_impl": in_impl,
        "tests_pass": tests_pass,
        "test_tail": tail if not tests_pass else "",
        "role": meta.get("role"),
        "model": meta.get("model"),
        "cost_usd": round(cost, 4) if cost is not None else None,
        "cost_basis": basis,
        "tokens": tokens(args.transcript),
        "turns": turns,
        "builder_result": result.get("subtype"),
    }, sys.stdout, indent=2)
    print()


if __name__ == "__main__":
    main()
