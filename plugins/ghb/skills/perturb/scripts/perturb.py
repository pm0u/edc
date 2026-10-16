#!/usr/bin/env python3
"""Run a test suite (and optionally a probe) under a changed environment, to find what the code and
its tests rely on without saying so: the host's timezone, its locale, the date, readdir order,
a network, well-behaved randomness.

Every axis runs in a disposable clone of --dir, never in place. The baseline runs twice first.
Probe inputs whose baseline output varies between those two runs are dropped, and a suite that
fails or flakes in the baseline stops the run, since nothing after it could be read.

An axis is {"name", "contract", "what", "env", "test_cmd"?}. `contract` is "within" when the
perturbed environment is one the code is entitled to meet (any timezone, a wall clock that steps back)
and "beyond" when it's outside what anything promises. --axes adds axes or overrides built-in
fields by name, e.g. {"name": "tz-east", "contract": "beyond"} for a module documented as UTC-only,
or a test-order axis with the runner's shuffle flag as its test_cmd. "{preload}" in a command is
replaced with the path of the Node preload, for runners that isolate globals (jest --setupFiles).

Node-only axes (clock, random, readdir, network) act through preload.cjs, which every run loads
via NODE_OPTIONS and which stays inert until its variable is set. TZ and locale axes are plain
environment variables and reach any language.
"""
import argparse
import json
import os
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

HERE = Path(__file__).resolve().parent
DAY = 86_400_000

AXES = [
    {"name": "tz-east", "contract": "within", "env": {"TZ": "Pacific/Kiritimati"},
     "what": "UTC+14: local date is a day ahead of UTC for most of the day"},
    {"name": "tz-west", "contract": "within", "env": {"TZ": "Pacific/Pago_Pago"},
     "what": "UTC-11: local date is a day behind UTC for most of the day"},
    {"name": "tz-half-dst", "contract": "within", "env": {"TZ": "Australia/Lord_Howe"},
     "what": "UTC+10:30 with a 30-minute DST shift: offsets aren't whole hours"},
    {"name": "locale-de", "contract": "within", "env": {"LANG": "de_DE.UTF-8", "LC_ALL": "de_DE.UTF-8"},
     "what": "decimal comma, day-first dates in default-locale formatting"},
    {"name": "locale-tr", "contract": "within", "env": {"LANG": "tr_TR.UTF-8", "LC_ALL": "tr_TR.UTF-8"},
     "what": "Turkish casing rules (dotted and dotless i) in locale-aware operations"},
    {"name": "clock-ahead", "contract": "within", "env": {"WIGGLE_ROOM_PERTURB_CLOCK_OFFSET_MS": str(1000 * DAY)},
     "what": "wall clock ~2.7 years ahead: a different year, month, weekday, and DST state"},
    {"name": "clock-backwards", "contract": "within", "env": {"WIGGLE_ROOM_PERTURB_CLOCK_BACKWARDS_MS": "30000"},
     "what": "wall clock runs backward for each process's first 30s: Date.now isn't monotonic"},
    {"name": "readdir-reverse", "contract": "within", "env": {"WIGGLE_ROOM_PERTURB_READDIR": "reverse"},
     "what": "directory listings come back in reverse order (the order is unspecified)"},
    {"name": "network-down", "contract": "within", "env": {"WIGGLE_ROOM_PERTURB_NETWORK": "down"},
     "what": "every non-loopback connection is refused"},
    {"name": "random-extremes", "contract": "beyond", "env": {"WIGGLE_ROOM_PERTURB_RANDOM": "extremes"},
     "what": "Math.random alternates 0 and just under 1: legal values, but no real generator's stream"},
]


def sh(cmd, cwd, env, timeout):
    # The commands are the coordinator's own command strings, run as a shell would.
    try:
        r = subprocess.run(cmd, shell=True, cwd=cwd, env=env, capture_output=True, text=True, timeout=timeout)
        return r.returncode == 0, (r.stdout + r.stderr)[-2500:]
    except subprocess.TimeoutExpired:
        return False, "timed out"


def run_env(preload, extra):
    env = {k: v for k, v in os.environ.items() if not k.startswith("WIGGLE_ROOM_PERTURB_")}
    env["NODE_OPTIONS"] = f'{env.get("NODE_OPTIONS", "")} --require "{preload}"'.strip()
    return {**env, **extra}


def probe(cmd, cwd, env, inputs, timeout):
    with tempfile.TemporaryDirectory() as tmp:
        i, o = Path(tmp) / "in.json", Path(tmp) / "out.json"
        i.write_text(json.dumps([{"id": k, "input": v} for k, v in inputs.items()]))
        ok, tail = sh(cmd, cwd, {**env, "WIGGLE_ROOM_PROBE_IN": str(i), "WIGGLE_ROOM_PROBE_OUT": str(o)}, timeout)
        if not o.exists():
            return None, tail
        return {k: v["output"] for k, v in json.loads(o.read_text()).items()}, tail


def load_inputs(path, limit):
    p = Path(path)
    if p.suffix == ".jsonl":
        items = [json.loads(l)["input"] for l in p.read_text().splitlines() if l.strip()]
    else:
        items = json.loads(p.read_text())
    seen, out = set(), []
    for x in items:
        key = json.dumps(x, sort_keys=True)
        if key not in seen:
            seen.add(key)
            out.append(x)
    # Smallest first: a changed output on a small input is the one a person can read.
    out.sort(key=lambda x: len(json.dumps(x)))
    return {f"p{n}": x for n, x in enumerate(out[:limit])}


def canon(v):
    return json.dumps(v, sort_keys=True)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--dir", required=True, help="project directory; it is cloned, never run in place")
    ap.add_argument("--test-cmd", required=True, help="scoped test command, run from the clone")
    ap.add_argument("--probe-cmd", help="runs only the probe file (wiggle-room probe protocol)")
    ap.add_argument("--inputs", help="probe inputs: a JSON list, or a fuzz cases.jsonl")
    ap.add_argument("--max-inputs", type=int, default=500)
    ap.add_argument("--axes", help="JSON list of axes to add, or built-in fields to override by name")
    ap.add_argument("--only", nargs="*", help="run only these axes")
    ap.add_argument("--timeout", type=int, default=900)
    ap.add_argument("--out", required=True, help="writes perturb.json here")
    args = ap.parse_args()
    if bool(args.probe_cmd) != bool(args.inputs):
        sys.exit("--probe-cmd and --inputs go together")

    axes = {a["name"]: dict(a) for a in AXES}
    for a in json.loads(Path(args.axes).read_text()) if args.axes else []:
        axes.setdefault(a["name"], {"env": {}}).update(a)
    if args.only:
        axes = {n: a for n, a in axes.items() if n in args.only}

    out = Path(args.out)
    out.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory() as tmp:
        work, preload = Path(tmp) / "work", Path(tmp) / "preload.cjs"
        shutil.copy(HERE / "preload.cjs", preload)
        # APFS clone on macOS; node_modules makes a plain copy slow.
        if subprocess.run(["cp", "-cR", args.dir, str(work)], capture_output=True).returncode:
            shutil.copytree(args.dir, work, symlinks=True)
        cmd = lambda c: c.replace("{preload}", str(preload))

        base_env = run_env(preload, {})
        for n in (1, 2):
            ok, tail = sh(cmd(args.test_cmd), work, base_env, args.timeout)
            if not ok:
                sys.exit(f"baseline run {n} failed; perturbation needs a green, stable suite:\n{tail}")

        inputs, baseline, unstable = {}, {}, 0
        if args.probe_cmd:
            inputs = load_inputs(args.inputs, args.max_inputs)
            first, tail = probe(cmd(args.probe_cmd), work, base_env, inputs, args.timeout)
            second, _ = probe(cmd(args.probe_cmd), work, base_env, inputs, args.timeout)
            if first is None or second is None:
                sys.exit(f"baseline probe wrote nothing:\n{tail}")
            baseline = {k: v for k, v in first.items() if canon(v) == canon(second.get(k))}
            unstable = len(first) - len(baseline)
            inputs = {k: inputs[k] for k in baseline}

        results = []
        for a in axes.values():
            env = run_env(preload, a.get("env", {}))
            ok, tail = sh(cmd(a.get("test_cmd", args.test_cmd)), work, env, args.timeout)
            row = {"axis": a["name"], "contract": a.get("contract", "within"), "what": a.get("what", ""),
                   "tests_pass": ok, "test_tail": "" if ok else tail}
            if args.probe_cmd:
                got, ptail = probe(cmd(args.probe_cmd), work, env, inputs, args.timeout)
                if got is None:
                    row["probe_error"] = ptail
                else:
                    changed = [k for k in baseline if canon(baseline[k]) != canon(got.get(k))]
                    row["probe_changed"] = len(changed)
                    row["examples"] = [{"input": inputs[k], "baseline": baseline[k], "perturbed": got.get(k)}
                                       for k in changed[:3]]
            row["effect"] = ("breaks tests" if not ok else
                             "changes outputs" if row.get("probe_changed") else
                             "probe failed" if "probe_error" in row else "none")
            results.append(row)
            print(f"{a['name']}: {row['effect']}", file=sys.stderr)

    summary = {"dir": args.dir, "probe_inputs": len(inputs), "unstable_dropped": unstable, "axes": results}
    (out / "perturb.json").write_text(json.dumps(summary, indent=2))

    print(f"**{len(results)} axes** · probe: {len(inputs)} stable inputs ({unstable} unstable dropped)"
          if args.probe_cmd else f"**{len(results)} axes** · tests only, no probe")
    for r in results:
        line = f"- `{r['axis']}` ({r['contract']}): **{r['effect']}**"
        if "probe_changed" in r:
            line += f" · {r['probe_changed']}/{len(inputs)} outputs changed"
        print(line + f" — {r['what']}")
        for ex in r.get("examples", [])[:1]:
            print(f"  - `{canon(ex['input'])[:100]}` → `{canon(ex['baseline'])[:60]}` became `{canon(ex['perturbed'])[:60]}`")
    node_axes = [r for r in results if any(k.startswith("WIGGLE_ROOM_PERTURB_") for k in axes[r["axis"]].get("env", {}))]
    if node_axes and all(r["effect"] == "none" for r in node_axes):
        print("\nNo Node preload axis had any effect. That's expected if the code never reads the clock, "
              "randomness, directories, or the network. If it does, check the preload reaches the test "
              "process: runners that sandbox globals (jest) need `--setupFiles {preload}` in the test command.")


if __name__ == "__main__":
    main()
