#!/usr/bin/env python3
"""Blind a room so builders get the tests' behavior and nothing else: no names, no titles, no comments.

  make     copy the room, replace every mapped word with an opaque token (in code, strings and
           paths), rename test titles to "case N", strip comments from the given files, and commit
           a fresh, history-free base. Then check the blinding didn't change what the tests say:
           the stub must still fail the blind test command, and the original implementation,
           blinded the same way, must pass it.
  restore  map a blind build back: reverse the tokens in every file it changed and lay those files
           over a copy of the normal room, so audit, probe and fuzz run on it unchanged.

Words are matched as whole identifiers, case-sensitively. A word inside test data changes the
data too (and its length). The original-passes check catches it when that breaks a test.
Comment stripping and title rewriting understand JS/TS only. Everything else relies on the
leftover report, which lists every remaining case-insensitive occurrence of a mapped word.
"""
import argparse
import fnmatch
import json
import os
import re
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

import sandbox

IDENT = "A-Za-z0-9_$"
KEYWORDS = {"return", "typeof", "case", "do", "else", "in", "of", "yield", "await", "delete", "void",
            "throw", "new", "instanceof"}
REGEX_PREV = set("(,=:[!&|?{};+-*%~^")
TITLE = re.compile(r"""((?<![\w$.])(?:\w+\.)?(?:describe|it|test|suite|context)"""
                   r"""(?:\.(?:only|skip|todo|concurrent|serial|sequential|fails))*\s*\(\s*)"""
                   r"""(['"`])((?:\\.|(?!\2)[^\\])*?)\2""")


def load_map(path):
    m = json.loads(Path(path).read_text())
    if isinstance(m, list):
        m = {w: f"zq{i + 1}" for i, w in enumerate(m)}
    return m


def substituter(mapping):
    words = sorted(mapping, key=len, reverse=True)
    rx = re.compile(rf"(?<![{IDENT}])({'|'.join(map(re.escape, words))})(?![{IDENT}])")
    return lambda s: rx.sub(lambda m: mapping[m.group(1)], s)


def strip_comments(s):
    """JS/TS comments out, everything else verbatim. Tracks strings, template literals (with ${}
    nesting) and regex literals well enough that a // inside one isn't taken for a comment."""
    out, n = [], len(s)

    def regex(i):
        j, in_class = i + 1, False
        while j < n and s[j] != "\n":
            ch = s[j]
            if ch == "\\":
                j += 2
                continue
            if ch == "[":
                in_class = True
            elif ch == "]":
                in_class = False
            elif ch == "/" and not in_class:
                j += 1
                break
            j += 1
        while j < n and s[j].isalpha():
            j += 1
        out.append(s[i:j])
        return j

    def template(i):
        out.append("`")
        j = i + 1
        while j < n:
            if s[j] == "\\":
                out.append(s[j:j + 2])
                j += 2
            elif s[j] == "`":
                out.append("`")
                return j + 1
            elif s.startswith("${", j):
                out.append("${")
                j = code(j + 2, nested=True)
            else:
                out.append(s[j])
                j += 1
        return j

    def code(i, nested=False):
        depth, prev, word, in_word = 0, "", "", False
        while i < n:
            c = s[i]
            if s.startswith("//", i):
                j = s.find("\n", i)
                while out and out[-1] in " \t":
                    out.pop()
                i = n if j < 0 else j
                continue
            if s.startswith("/*", i):
                j = s.find("*/", i + 2)
                j = n if j < 0 else j + 2
                out.append("\n" * s.count("\n", i, j))
                i = j
                continue
            if c in "'\"":
                j = i + 1
                while j < n and s[j] != c and s[j] != "\n":
                    j += 2 if s[j] == "\\" else 1
                out.append(s[i:j + 1])
                i, prev, word, in_word = j + 1, c, "", False
                continue
            if c == "`":
                i, prev, word, in_word = template(i), "`", "", False
                continue
            if c == "/" and (prev == "" or prev in REGEX_PREV or (prev.isalnum() and word in KEYWORDS)):
                i, prev, word, in_word = regex(i), "/", "", False
                continue
            if nested and c == "}" and depth == 0:
                out.append(c)
                return i + 1
            depth += (c == "{") - (c == "}")
            out.append(c)
            if c.isalnum() or c in "_$":
                word = word + c if in_word else c
                in_word, prev = True, c
            else:
                in_word = False
                if not c.isspace():
                    prev, word = c, ""
            i += 1
        return i

    code(0)
    text = "".join(out)
    return re.sub(r"\n[ \t]*(?:\n[ \t]*)+\n", "\n\n", text).lstrip("\n")


def sh(cmd, cwd, timeout):
    # The test command is the coordinator's own command string, run as a shell would.
    try:
        r = subprocess.run(cmd, shell=True, cwd=cwd, capture_output=True, text=True, timeout=timeout)
        return r.returncode == 0, (r.stdout + r.stderr)[-1500:]
    except subprocess.TimeoutExpired:
        return False, "timed out"


def clone(src, dst):
    # APFS clone on macOS; node_modules makes a plain copy slow.
    if subprocess.run(["cp", "-cR", str(src), str(dst)], capture_output=True).returncode:
        shutil.copytree(src, dst, symlinks=True)


def git(cwd, *a, git_dir=None):
    pre = [f"--git-dir={git_dir}", f"--work-tree={cwd}"] if git_dir else []
    return subprocess.run(["git", *pre, "-C", str(cwd), *a], capture_output=True, text=True, check=True).stdout


def text_of(path):
    try:
        return path.read_text()
    except (UnicodeDecodeError, OSError):
        return None


def matches(rel, globs):
    return any(fnmatch.fnmatch(rel, g) for g in globs)


def blind_tree(root, files, sub, tests, strip):
    """Rewrite `files` (room-relative) under `root` in place. Returns (path renames, titles rewritten)."""
    renames, titles = {}, 0
    for rel in files:
        p = root / rel
        src = text_of(p)
        if src is None:
            continue
        if matches(rel, strip):
            src = strip_comments(src)
        if matches(rel, tests):
            def title(m):
                nonlocal titles
                titles += 1
                return f"{m.group(1)}{m.group(2)}case {titles}{m.group(2)}"
            src = TITLE.sub(title, src)
        p.write_text(sub(src))
        new = sub(rel)
        if new != rel:
            (root / new).parent.mkdir(parents=True, exist_ok=True)
            p.rename(root / new)
            renames[rel] = new
    return renames, titles


def make(args):
    room, out = Path(args.room).resolve(), Path(args.out).resolve()
    mapping = load_map(args.map)
    sub = substituter(mapping)
    files = git(room, "ls-files").split()
    clone(room, out)
    shutil.rmtree(out / ".git")  # the room's history holds every name in the clear
    renames, titles = blind_tree(out, files, sub, args.tests, args.strip_comments)
    git(out, "init", "-q")
    git(out, "add", "-A")
    git(out, "-c", "user.name=wiggle-room", "-c", "user.email=wiggle-room@localhost",
        "commit", "-qm", "wiggle-room blind base")
    base = git(out, "rev-parse", "HEAD").strip()

    leftovers = []
    for rel in git(out, "ls-files").split():
        src = text_of(out / rel) or ""
        for word in mapping:
            if word.lower() in rel.lower():
                leftovers.append({"file": rel, "line": 0, "word": word, "text": "(path)"})
            for num, line in enumerate(src.splitlines(), 1):
                if word.lower() in line.lower():
                    leftovers.append({"file": rel, "line": num, "word": word, "text": line.strip()[:120]})

    blind_cmd = sub(args.test_cmd)
    stub_ok, stub_tail = sh(blind_cmd, out, args.timeout)
    checks = {"stub_fails": not stub_ok}
    if args.repo and args.target:
        # The original, blinded the same way, must pass the blind tests. If it doesn't, the map
        # changed what the tests say (a word in test data, a package name), not just how they read.
        work = Path(tempfile.mkdtemp(dir=out.parent, prefix=".blind-check-"))
        try:
            clone(out, work / "room")
            for t in args.target:
                src = Path(args.repo) / t
                for f in ([src] if src.is_file() else [p for p in src.rglob("*") if p.is_file()]):
                    rel = str(f.relative_to(args.repo))
                    dest = work / "room" / sub(rel)
                    dest.parent.mkdir(parents=True, exist_ok=True)
                    content = text_of(f)
                    dest.write_text(sub(content)) if content is not None else shutil.copy(f, dest)
            ok, tail = sh(blind_cmd, work / "room", args.timeout)
            checks["original_passes"] = ok
            if not ok:
                checks["original_tail"] = tail
        finally:
            shutil.rmtree(work)
    if stub_ok:
        checks["stub_tail"] = stub_tail

    json.dump({"blind_room": str(out), "base": base, "map": mapping, "renamed": renames,
               "blind_test_cmd": blind_cmd, "titles_rewritten": titles, "leftovers": leftovers,
               "checks": checks}, sys.stdout, indent=2)
    print()
    bad = [k for k, v in checks.items() if v is False]
    print(f"blind room at {out} · {titles} titles · {len(renames)} paths renamed · "
          f"{len(leftovers)} leftovers · checks: {'FAILED ' + ', '.join(bad) if bad else 'ok'}", file=sys.stderr)


def restore(args):
    room, blind, build, out = (Path(p).resolve() for p in (args.room, args.blind_room, args.build, args.out))
    mapping = load_map(args.map)
    reverse = substituter({v: k for k, v in mapping.items()})
    # A builder can pick a hidden word on its own (a local `separator`). Moved aside first, it
    # can't collide with the token that reverses into the same name.
    own = re.compile(rf"(?<![{IDENT}])({'|'.join(map(re.escape, mapping))})(?![{IDENT}])")
    gd = blind / ".git"
    base = git(blind, "rev-parse", "HEAD").strip()
    changed = set(git(build, "diff", "--name-only", base, git_dir=gd).split())
    changed |= set(git(build, "ls-files", "--others", "--exclude-standard", git_dir=gd).split())
    if links := sorted(rel for rel in changed if sandbox.escapes(build, rel)):
        sys.exit(f"refusing to restore {build}: symlinks or paths outside it: {links}")
    clone(room, out)
    shutil.rmtree(out / ".git", ignore_errors=True)
    restored, deleted, collisions = [], [], {}
    for rel in sorted(changed):
        src, dest = build / rel, out / reverse(rel)
        if not src.exists():
            dest.unlink(missing_ok=True)
            deleted.append(reverse(rel))
            continue
        dest.parent.mkdir(parents=True, exist_ok=True)
        content = text_of(src)
        if content is None:
            shutil.copy(src, dest)
        else:
            hits = sorted(set(own.findall(content)))
            if hits:
                collisions[reverse(rel)] = hits
                content = own.sub(lambda m: m.group(1) + "__own", content)
            dest.write_text(reverse(content))
        restored.append(reverse(rel))
    json.dump({"build": str(out), "restored": restored, "deleted": deleted,
               "renamed_own_words": collisions}, sys.stdout, indent=2)
    print()


def main():
    ap = argparse.ArgumentParser()
    sp = ap.add_subparsers(dest="cmd", required=True)
    m = sp.add_parser("make")
    m.add_argument("--room", required=True, help="the normal room, stub committed")
    m.add_argument("--out", required=True, help="where the blind room goes")
    m.add_argument("--map", required=True, help='JSON: ["word", ...] or {"word": "token"}')
    m.add_argument("--tests", nargs="*", default=[], help="globs whose test titles become 'case N'")
    m.add_argument("--strip-comments", nargs="*", default=[], help="globs to strip JS/TS comments from")
    m.add_argument("--test-cmd", required=True, help="the normal scoped test command; it gets blinded too")
    m.add_argument("--repo", help="the real repo, for the original-passes check")
    m.add_argument("--target", nargs="*", help="repo-relative target paths, for the original-passes check")
    m.add_argument("--timeout", type=int, default=900)
    r = sp.add_parser("restore")
    r.add_argument("--room", required=True, help="the normal room")
    r.add_argument("--blind-room", required=True)
    r.add_argument("--map", required=True)
    r.add_argument("--build", required=True, help="a blind build directory")
    r.add_argument("--out", required=True, help="where the restored build goes")
    args = ap.parse_args()
    make(args) if args.cmd == "make" else restore(args)


if __name__ == "__main__":
    main()
