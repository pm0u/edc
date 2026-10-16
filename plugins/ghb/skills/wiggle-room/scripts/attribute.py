#!/usr/bin/env python3
"""Attribute divergences to the original's code: missing test, or behavior nobody wrote on purpose?

For each divergence, a model that has read the original proposes the smallest edit that removes the
behavior in question (a constant, a branch, a special case). The proposal is only a hypothesis.
This script checks it in a throwaway copy of the reference:

  tests pass, output changes   unpinned: dedicated code no test notices losing. A missing test.
  tests fail, output changes   partly pinned: tests reach this code, just not this input.
  output unchanged             not attributed: the edit missed. The behavior falls out of general
                               logic, or the hypothesis was wrong.

It also blames the edited lines in the repo, because a bug-fix commit there settles the question.

--mutants is a JSON list of {"class", "input", "file", "find", "replace", "why"}: `file` is
reference-relative, and `find` must occur exactly once in it. `input` is in the probe's encoding.
"""
import argparse
import json
import os
import re
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

FIX = re.compile(r"\b(fix|bug|handle|edge|regression|issue|crash|guard)", re.I)


def sh(cmd, cwd, env=None, timeout=600):
    # The commands are the coordinator's own command strings, run as a shell would.
    return subprocess.run(cmd, shell=True, cwd=cwd, env=env, capture_output=True, text=True, timeout=timeout)


def probe(cmd, cwd, inp, timeout):
    with tempfile.TemporaryDirectory() as tmp:
        i, o = Path(tmp) / "in.json", Path(tmp) / "out.json"
        i.write_text(json.dumps([{"id": "x", "input": inp}]))
        sh(cmd, cwd, {**os.environ, "WIGGLE_ROOM_PROBE_IN": str(i), "WIGGLE_ROOM_PROBE_OUT": str(o)}, timeout)
        return json.loads(o.read_text())["x"]["output"] if o.exists() else {"$error": "<probe wrote nothing>"}


def blame(repo, rel, first, last):
    r = subprocess.run(["git", "-C", repo, "blame", "--porcelain", "-L", f"{first},{last}", "--", rel],
                       capture_output=True, text=True)
    shas = dict.fromkeys(l.split()[0] for l in r.stdout.splitlines() if re.match(r"^[0-9a-f]{40} ", l))
    out = []
    for sha in shas:
        if set(sha) == {"0"}:
            out.append({"commit": "uncommitted", "subject": ""})
            continue
        subject = subprocess.run(["git", "-C", repo, "log", "-1", "--format=%s", sha],
                                 capture_output=True, text=True).stdout.strip()
        out.append({"commit": sha[:10], "subject": subject, "fix_like": bool(FIX.search(subject))})
    return out


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--ref", required=True, help="reference directory (original implementation)")
    ap.add_argument("--repo", required=True, help="the real repo, for blame")
    ap.add_argument("--mutants", required=True)
    ap.add_argument("--test-cmd", required=True)
    ap.add_argument("--probe-cmd", required=True, help="runs only the probe file")
    ap.add_argument("--timeout", type=int, default=600)
    args = ap.parse_args()

    ref = Path(args.ref).resolve()
    results = []
    with tempfile.TemporaryDirectory() as tmp:
        # One copy for every mutant, each edit undone before the next: copying and deleting a
        # reference with node_modules took ~70s, most of the time per mutant. The reference itself
        # is never edited, so a crash here can't leave later rounds probing a mutant.
        work = Path(tmp) / "ref"
        # APFS clone on macOS; node_modules and friends make a plain copy slow.
        if subprocess.run(["cp", "-cR", str(ref), str(work)], capture_output=True).returncode:
            shutil.copytree(ref, work, symlinks=True)
        for m in json.loads(Path(args.mutants).read_text()):
            target = work / m["file"]
            src = target.read_text()
            hits = src.count(m["find"])
            row = {k: m.get(k) for k in ("class", "file", "why")}
            if hits != 1:
                results.append({**row, "verdict": "bad mutant", "detail": f"`find` occurs {hits} times"})
                continue
            before = probe(args.probe_cmd, work, m["input"], args.timeout)
            target.write_text(src.replace(m["find"], m["replace"]))
            try:
                tests_pass = sh(args.test_cmd, work, timeout=args.timeout).returncode == 0
                after = probe(args.probe_cmd, work, m["input"], args.timeout)
            finally:
                target.write_text(src)
            changed = json.dumps(before, sort_keys=True) != json.dumps(after, sort_keys=True)
            verdict = ("not attributed" if not changed else "unpinned" if tests_pass else "partly pinned")
            first = src[: src.index(m["find"])].count("\n") + 1
            last = first + m["find"].count("\n")
            results.append({**row, "verdict": verdict, "lines": f"{first}-{last}", "tests_pass": tests_pass,
                            "output_before": before, "output_after": after,
                            "blame": blame(args.repo, m["file"], first, last)})

    json.dump(results, sys.stdout, indent=2)
    print()
    for r in results:
        commits = "; ".join(f"{b['commit']} {b['subject']}" for b in r.get("blame", []))
        print(f"- {r['class']}: **{r['verdict']}** {r['file']}:{r.get('lines', '?')} {commits}", file=sys.stderr)


if __name__ == "__main__":
    main()
