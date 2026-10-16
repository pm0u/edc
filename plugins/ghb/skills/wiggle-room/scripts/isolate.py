#!/usr/bin/env python3
"""Copy a repo's working tree into a fresh, history-free directory, minus the paths being rebuilt.

Copies tracked + untracked-but-not-ignored files, so uncommitted test edits come along and
gitignored build output, caches, and node_modules don't. Runs `git init` but doesn't commit —
the coordinator writes the stub and runs setup first. Prints a JSON manifest to stdout.
"""
import argparse
import fnmatch
import json
import os
import shutil
import subprocess
import sys
from pathlib import Path


def under(rel, prefixes):
    return any(rel == p or rel.startswith(p + "/") for p in prefixes)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--repo", required=True)
    ap.add_argument("--out", required=True)
    ap.add_argument("--remove", nargs="+", required=True, help="repo-relative files or dirs to delete")
    ap.add_argument("--strip", nargs="*", default=["*.map"],
                    help="globs for committed artifacts to drop (matched against the repo-relative path)")
    args = ap.parse_args()

    repo = Path(subprocess.check_output(
        ["git", "-C", args.repo, "rev-parse", "--show-toplevel"], text=True).strip()).resolve()
    out = Path(args.out).resolve()
    if out == repo or repo in out.parents:
        sys.exit("--out must be outside the repo")
    if out.exists() and any(out.iterdir()):
        sys.exit(f"{out} exists and isn't empty")

    removed = [p.strip("/") for p in args.remove]
    for p in removed:
        if not (repo / p).exists():
            sys.exit(f"--remove path not found: {p}")

    files = subprocess.check_output(
        ["git", "-C", str(repo), "ls-files", "-z", "--cached", "--others", "--exclude-standard"],
        text=True).split("\0")

    copied, dropped, stripped, warnings = 0, [], [], []
    for rel in filter(None, files):
        src = repo / rel
        if under(rel, removed):
            dropped.append(rel)
            continue
        if any(fnmatch.fnmatch(rel, g) for g in args.strip):
            stripped.append(rel)
            continue
        if not os.path.lexists(src):
            continue  # deleted in the working tree but still in the index
        if src.is_dir() and not src.is_symlink():
            warnings.append(f"skipped directory entry (submodule?): {rel}")
            continue
        dst = out / rel
        dst.parent.mkdir(parents=True, exist_ok=True)
        if src.is_symlink():
            target = os.readlink(src)
            if os.path.isabs(target) or not (src.parent / target).resolve().is_relative_to(repo):
                warnings.append(f"symlink points outside the repo, skipped: {rel} -> {target}")
                continue
            os.symlink(target, dst)
        else:
            shutil.copy2(src, dst)
        copied += 1

    subprocess.check_call(["git", "init", "-q", str(out)])
    json.dump({
        "repo": str(repo),
        "room": str(out),
        "copied": copied,
        "removed": dropped,
        "stripped": stripped,
        "warnings": warnings,
    }, sys.stdout, indent=2)
    print()


if __name__ == "__main__":
    main()
