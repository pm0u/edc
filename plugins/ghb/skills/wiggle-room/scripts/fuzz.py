#!/usr/bin/env python3
"""Divergence-guided search: hunt for inputs where rebuilds disagree with the original.

Drives the probe (an in-language test file) over a request/response protocol:

  $WIGGLE_ROOM_PROBE_IN   JSON list of requests, each one of
                           {"id", "seed"}          generate(seed)
                           {"id", "seed", "from"}  mutate(from, seed)
                           {"id", "input"}         run this input as-is
  $WIGGLE_ROOM_PROBE_OUT  JSON object {id: {"input": <json>, "output": <json>}}

The reference materializes every input. Builds only ever get {"id", "input"}, so they all see
exactly the same inputs. Each round runs the reference twice and drops unstable cases, groups each
build's divergences by shape (what kind of difference), keeps the smallest example per group, and
mutates this round's divergent inputs for the next one. The model picks how inputs are generated
and mutated. Which ones get explored is decided by where the implementations disagree.

summary.json reports effective builds: on contested cases, the mean number of distinct behaviors
across builds. 1.0 means the builds moved as one; len(builds) means they were fully independent.
Adversary builds (--adversary) steer the search like any build but stay out of that number: their
divergences are deliberate, so each one is behavior the tests let a plausible implementation break.
"""
import argparse
import json
import random
import sys
import tempfile
from pathlib import Path

import sandbox


def run_probe(cmd, cwd, requests, timeout, fence):
    with tempfile.TemporaryDirectory() as tmp:
        inp, out = Path(tmp) / "in.json", Path(tmp) / "out.json"
        inp.write_text(json.dumps(requests))
        env = {"TMPDIR": tmp, "WIGGLE_ROOM_PROBE_IN": str(inp), "WIGGLE_ROOM_PROBE_OUT": str(out)}
        # The probe command is the coordinator's own; what it executes is the build's, so it runs
        # fenced. The reference runs the same way, so every implementation sees one environment.
        r = sandbox.run(cmd, cwd, *fence, writable=[tmp], env=env, timeout=timeout)
        if not out.exists():
            sys.exit(f"probe wrote nothing in {cwd} (exit {r.returncode}):\n{(r.stdout + r.stderr)[-2000:]}")
        return json.loads(out.read_text())


def canon(v):
    return json.dumps(v, sort_keys=True)


def kind(v):
    if isinstance(v, dict) and "$error" in v:
        return f"error:{v['$error']}"
    if v is None:
        return "null"
    return {bool: "bool", int: "number", float: "number", str: "string", list: "array", dict: "object"}.get(type(v), "other")


def relation(ref, got):
    """Coarse shape of a same-kind difference, so e.g. truncation doesn't merge with reordering."""
    if isinstance(ref, (str, list)) and isinstance(got, type(ref)):
        if len(got) != len(ref):
            return "longer" if len(got) > len(ref) else "shorter"
        return "reordered" if sorted(map(canon, ref)) == sorted(map(canon, got)) else "same-length"
    if isinstance(ref, (int, float)) and isinstance(got, (int, float)):
        return "greater" if got > ref else "less"
    if isinstance(ref, dict) and isinstance(got, dict) and set(ref) != set(got):
        return "keys"
    return "value"


def shape(ref_out, got):
    """How one build differs from the reference: `string->error:RangeError`, `array->array(shorter)`.
    Keyed per build, not per combination of builds, so independent builds add groups instead of
    multiplying them."""
    rk, gk = kind(ref_out), kind(got)
    return f"{rk}->{gk}" + (f"({relation(ref_out, got)})" if rk == gk else "")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--ref", required=True, help="reference directory (original implementation)")
    ap.add_argument("--build", nargs="+", required=True, help="green build directories")
    ap.add_argument("--adversary", nargs="*", default=[], help="green adversary build directories")
    ap.add_argument("--probe-cmd", required=True, help="runs only the probe file, from each directory")
    ap.add_argument("--fixed", help="JSON list of targeted inputs to include in round 0")
    ap.add_argument("--rounds", type=int, default=8)
    ap.add_argument("--batch", type=int, default=200, help="fresh generated inputs per round")
    ap.add_argument("--mutations", type=int, default=4, help="mutations per divergent input")
    ap.add_argument("--frontier", type=int, default=100, help="max divergent inputs to mutate per round")
    ap.add_argument("--quiet", type=int, default=3, help="stop after this many rounds without a new group")
    ap.add_argument("--seed", type=int, default=1)
    ap.add_argument("--timeout", type=int, default=600)
    ap.add_argument("--run-root", required=True, help="the wiggle-room run ($OUT), fenced off from the probe")
    ap.add_argument("--forbid", nargs="+", required=True, help="the repo and its worktrees, fenced off from the probe")
    ap.add_argument("--out", required=True, help="writes classes.json and cases.jsonl here")
    args = ap.parse_args()

    rng = random.Random(args.seed)
    fence = (args.run_root, args.forbid)
    out = Path(args.out)
    out.mkdir(parents=True, exist_ok=True)
    builds = label(args.build + args.adversary)
    adversaries = set(list(builds)[len(args.build):])
    classes, frontier, quiet = {}, [], 0
    names = sorted(n for n in builds if n not in adversaries)
    contested, distinct_sum = 0, 0
    agree = {(a, b): 0 for i, a in enumerate(names) for b in names[i + 1:]}
    total = unstable_total = 0
    log = (out / "cases.jsonl").open("w")
    next_id = 0

    def new_id():
        nonlocal next_id
        next_id += 1
        return f"c{next_id}"

    for rnd in range(args.rounds):
        requests = [{"id": new_id(), "seed": rng.randrange(2**31)} for _ in range(args.batch)]
        if rnd == 0 and args.fixed:
            requests += [{"id": new_id(), "input": i} for i in json.loads(Path(args.fixed).read_text())]
        for inp in frontier[: args.frontier]:
            requests += [{"id": new_id(), "seed": rng.randrange(2**31), "from": inp} for _ in range(args.mutations)]

        ref = run_probe(args.probe_cmd, args.ref, requests, args.timeout, fence)
        materialized = [{"id": k, "input": v["input"]} for k, v in ref.items()]
        ref2 = run_probe(args.probe_cmd, args.ref, materialized, args.timeout, fence)
        unstable = {k for k in ref if canon(ref[k]["output"]) != canon(ref2.get(k, {}).get("output"))}
        results = {name: run_probe(args.probe_cmd, d, materialized, args.timeout, fence) for name, d in builds.items()}

        new_sigs, frontier = 0, []
        for k, v in ref.items():
            if k in unstable:
                continue
            expected = canon(v["output"])
            outputs = {n: r.get(k, {}).get("output", {"$error": "<missing>"}) for n, r in results.items()}
            canon_out = {n: canon(o) for n, o in outputs.items()}
            faithful = {canon_out[n] for n in names}
            if len(faithful | {expected}) > 1:
                contested += 1
                distinct_sum += len(faithful)
                for a, b in agree:
                    agree[a, b] += canon_out[a] == canon_out[b]
            diverged = {n: o for n, o in outputs.items() if canon_out[n] != expected}
            log.write(json.dumps({"round": rnd, "id": k, "input": v["input"], "reference": v["output"],
                                  "diverged": diverged}) + "\n")
            if not diverged:
                continue
            frontier.append(v["input"])
            size = len(canon(v["input"]))
            for n, o in diverged.items():
                sig = (shape(v["output"], o), n)
                c = classes.get(sig)
                if c is None:
                    new_sigs += 1
                    classes[sig] = {"shape": sig[0], "build": n, "adversary": n in adversaries,
                                    "count": 1, "first_round": rnd,
                                    "example": {"input": v["input"], "reference": v["output"], "output": o}}
                else:
                    c["count"] += 1
                    if size < len(canon(c["example"]["input"])):
                        c["example"] = {"input": v["input"], "reference": v["output"], "output": o}
        rng.shuffle(frontier)
        total += len(ref) - len(unstable)
        unstable_total += len(unstable)
        quiet = 0 if new_sigs else quiet + 1
        print(f"round {rnd}: {len(ref)} cases, {len(unstable)} unstable, {len(frontier)} divergent, "
              f"{new_sigs} new groups ({len(classes)} total)", file=sys.stderr)
        if quiet >= args.quiet:
            break
    log.close()

    by_shape = {}
    for c in classes.values():
        by_shape.setdefault(c["shape"], []).append(c)
    ranked = sorted(by_shape.items(), key=lambda kv: (-len(kv[1]), -sum(c["count"] for c in kv[1])))
    ranked = [{"shape": k, "builds": sorted(cs, key=lambda c: c["build"])} for k, cs in ranked]
    (out / "classes.json").write_text(json.dumps(ranked, indent=2))

    # Effective builds: on cases where anything disagrees, how many distinct behaviors the builds
    # show on average. 1.0 means they moved as one build; len(builds) means fully independent.
    effective = distinct_sum / contested if contested else float(len(names))
    pairwise = {f"{a}~{b}": round(n / contested, 3) if contested else None for (a, b), n in agree.items()}
    unique = {n: sum(1 for g in ranked if [c["build"] for c in g["builds"]] == [n]) for n in builds}
    adversary_only = [g["shape"] for g in ranked if all(c["adversary"] for c in g["builds"])]
    (out / "summary.json").write_text(json.dumps({
        "stable_cases": total, "unstable": unstable_total, "rounds": rnd + 1, "shapes": len(ranked), "groups": len(classes),
        "contested_cases": contested, "effective_builds": round(effective, 2), "builds": len(names),
        "pairwise_agreement": pairwise, "found_alone": unique, "adversaries": sorted(adversaries),
        "adversary_only_shapes": adversary_only}, indent=2))

    print(f"**{total} stable cases** over {rnd + 1} rounds · {unstable_total} unstable (dropped) · "
          f"{len(ranked)} divergence shapes ({len(classes)} build×shape groups)")
    print(f"**Effective builds:** {effective:.2f} of {len(names)} over {contested} contested cases · "
          f"found alone: " + ", ".join(f"{n} {u}" for n, u in unique.items()))
    print("**Pairwise agreement on contested cases:** " +
          ", ".join(f"{k} {v:.0%}" for k, v in pairwise.items() if v is not None))
    if adversaries:
        print(f"**Adversary-only shapes:** {len(adversary_only)} (no good-faith build diverged there)")
    print()
    for g in ranked:
        print(f"- `{g['shape']}` — " + ", ".join(f"{c['build']} ({c['count']})" for c in g["builds"]))
        for c in g["builds"]:
            ex = c["example"]
            print(f"  - {c['build']}: `{canon(ex['input'])[:120]}` → ref `{canon(ex['reference'])[:80]}`, "
                  f"got `{canon(ex['output'])[:80]}`")


def label(dirs):
    """Name builds by directory, adding the parent where two rounds share a name (build-1)."""
    base = [Path(d).name for d in dirs]
    return {(f"{Path(d).parent.name}/{b}" if base.count(b) > 1 else b): d for d, b in zip(dirs, base)}


if __name__ == "__main__":
    main()
