#!/usr/bin/env python3
"""Find room files that mention identifiers which exist only in the deleted implementation.

A token is "private" if it appears in the deleted files but not in the public surface (stub,
tests). Room files containing private tokens are candidates for leaks: committed build output,
source maps, snapshots, docs, or other code reaching into the target's internals. Tokens that
show up in many room files are dropped as shared vocabulary. Output is ranked; the coordinator
judges each hit.
"""
import argparse
import fnmatch
import json
import re
import sys
from collections import defaultdict
from pathlib import Path

TOKEN = re.compile(r"[A-Za-z_$][A-Za-z0-9_$]{5,}")
SKIP_DIRS = {".git", "node_modules", ".venv", "venv", "vendor", "__pycache__"}
MAX_BYTES = 2_000_000


def text_files(root):
    for p in root.rglob("*"):
        if any(part in SKIP_DIRS for part in p.relative_to(root).parts):
            continue
        if p.is_file() and not p.is_symlink() and p.stat().st_size <= MAX_BYTES:
            data = p.read_bytes()
            if b"\0" not in data[:8192]:
                yield p, data.decode("utf-8", "replace")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--repo", required=True)
    ap.add_argument("--room", required=True)
    ap.add_argument("--removed", nargs="+", required=True, help="repo-relative paths that were deleted")
    ap.add_argument("--public", nargs="*", action="extend", default=[],
                    help="room-relative globs whose tokens are public by spec (stub, tests)")
    ap.add_argument("--max-files", type=int, default=15,
                    help="drop tokens found in more than this many room files")
    args = ap.parse_args()

    repo, room = Path(args.repo).resolve(), Path(args.room).resolve()

    deleted = set()
    for rel in args.removed:
        p = repo / rel
        for f in ([p] if p.is_file() else p.rglob("*")):
            if f.is_file():
                deleted |= set(TOKEN.findall(f.read_text("utf-8", "replace")))

    public, hits = set(), defaultdict(set)
    files = list(text_files(room))
    for p, text in files:
        rel = str(p.relative_to(room))
        if any(fnmatch.fnmatch(rel, g) for g in args.public):
            public |= set(TOKEN.findall(text))

    private = deleted - public
    for p, text in files:
        rel = str(p.relative_to(room))
        if any(fnmatch.fnmatch(rel, g) for g in args.public):
            continue
        found = private & set(TOKEN.findall(text))
        for t in found:
            hits[t].add(rel)

    common = {t for t, fs in hits.items() if len(fs) > args.max_files}
    by_file = defaultdict(list)
    for t, fs in hits.items():
        if t not in common:
            for f in fs:
                by_file[f].append(t)

    ranked = sorted(by_file.items(), key=lambda kv: -len(kv[1]))
    json.dump({
        "private_tokens": len(private),
        "dropped_as_common": sorted(common),
        "files": [{"file": f, "hits": len(ts), "tokens": sorted(ts)[:25]} for f, ts in ranked],
    }, sys.stdout, indent=2)
    print()


if __name__ == "__main__":
    main()
