"""The fence around model-written code, as a Codex permissions profile.

Codex builders run inside it, and so does everything that executes a build afterwards (the audit's
test run, the probe), since that's the same untrusted code. Inside: the whole disk readable except
the original, the rest of the wiggle-room run and credentials; only the working directory (and any
extra writable paths) writable; no network.
"""
import json
import os
import re
import shutil
import subprocess
import sys

# Session transcripts hold everything the coordinator read, including the original.
SECRETS = ["~/.claude/projects", "~/.ssh", "~/.aws", "~/.config/gh", "~/.config/gcloud", "~/.netrc"]
# All of ~/.codex can't be denied: the codex binary lives there.
CODEX_SECRETS = ["~/.codex/auth.json", "~/.codex/sessions", "~/.codex/history.jsonl"]
SECRET_ENV = re.compile(r"TOKEN|SECRET|PASSW|CREDENTIAL|API_?KEY|ACCESS_KEY|PRIVATE_KEY|AUTH", re.I)
URL_CREDENTIAL = re.compile(r"://[^/\s:@]+:[^/\s@]+@")  # e.g. a GOPROXY with a token in it


def escapes(build, rel):
    """True if build/rel is a symlink or resolves outside build. The fence stops a builder reading
    outside its build, not creating a link that points out, which the coordinator would follow."""
    build = os.path.realpath(build)
    path = os.path.join(build, rel)
    resolved = os.path.realpath(path)
    return os.path.islink(path) or not (resolved == build or resolved.startswith(build + os.sep))


def rules(cwd, run_root, forbid, writable=(), access="write"):
    """Filesystem rules as a TOML inline table for `-c permissions.<name>.filesystem=`.

    "none" also blocks lstat, and Node lstats every ancestor of its entry script, so the run is
    denied entry by entry along the path to cwd, never an ancestor of cwd itself."""
    cwd, run_root = os.path.realpath(cwd), os.path.realpath(run_root)
    keep = {cwd} | {os.path.realpath(w) for w in writable}
    rel = os.path.relpath(cwd, run_root)
    if rel.startswith(".."):
        sys.exit(f"{cwd} is not inside the run {run_root}")
    deny, cur = [], run_root
    for part in rel.split(os.sep) if rel != "." else []:
        deny += [p for e in os.listdir(cur) if (p := os.path.join(cur, e)) not in keep and e != part]
        cur = os.path.join(cur, part)
    deny += [os.path.realpath(p) for p in forbid]
    deny += [os.path.expanduser(p) for p in SECRETS + CODEX_SECRETS]
    table = {":root": "read", **{p: "none" for p in deny}, cwd: access,
             **{os.path.realpath(w): "write" for w in writable}}
    return "{" + ", ".join(f"{json.dumps(k)}={json.dumps(v)}" for k, v in table.items()) + "}"


def run(cmd, cwd, run_root, forbid, writable=(), env=None, timeout=None):
    """Run a shell command in cwd inside the fence. Secret-looking environment variables are
    dropped; with no network they could only be written into the build, but nothing needs them."""
    codex = shutil.which("codex")
    if not codex:
        sys.exit("wiggle-room runs builds inside Codex's sandbox: install the codex CLI")
    env = {k: v for k, v in os.environ.items()
           if not SECRET_ENV.search(k) and not URL_CREDENTIAL.search(v)} | (env or {})
    argv = [codex, "sandbox", "-C", cwd, "-P", "wiggleroom",
            "-c", f"permissions.wiggleroom.filesystem={rules(cwd, run_root, forbid, writable)}",
            "--", "sh", "-c", cmd]
    return subprocess.run(argv, cwd=cwd, env=env, capture_output=True, text=True, timeout=timeout)


if __name__ == "__main__":  # run_builds.sh: print the rules for a Codex builder
    cwd, run_root, access, *rest = sys.argv[1:]
    sep = rest.index("--")
    print(rules(cwd, run_root, forbid=rest[sep + 1:], writable=rest[:sep], access=access))
