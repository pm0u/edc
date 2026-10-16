# Perturb

Every suite passes in one environment: your timezone, your locale, this year, the order your
filesystem happens to list files in, a network that's up. Code and tests come to rely on all of
it without anyone deciding to. Those are unknown knowns, and nobody finds them by reading, because
the reader shares the same assumptions. This skill violates the assumptions on purpose, one axis at
a time, and reports what changed.

Each axis is marked against the contract:

- **within**: an environment the code is entitled to meet (any timezone, a wall clock that steps
  back, an unordered directory listing). A break here is a real dependency nobody stated.
- **beyond**: outside anything promised (`Math.random` returning only its extremes). A break here
  is a resilience finding: does it fail loudly and safely?

The fix differs, so the report keeps them apart.

## Usage

```
$perturb <path or test scope>
$perturb <wiggle-room $OUT>     # also replay the probe's fuzz cases against the original
```

`$SCRATCH` is a working directory outside the repo: the session scratchpad, or `$OUT` when the
target is a wiggle-room run.

## 1. Scope

Find the test command that covers the target, scoped to it if the full suite is slow. Every axis
runs it once, plus two baseline runs, so a 30-second suite costs about six minutes.

The script needs a green, stable baseline: it stops if either baseline run fails. A flaky suite has
to be fixed or scoped around first, and that's worth reporting on its own.

## 2. Contract

Read what the target states about its environment: README, module docs, types, config. Then write
`$SCRATCH/axes.json` for anything the defaults get wrong:

- An axis the target explicitly opts out of becomes beyond: `{"name": "tz-east", "contract": "beyond"}`
  for a module documented as UTC-only.
- Test order, when the runner can shuffle: `{"name": "test-order", "contract": "within",
  "test_cmd": "npx vitest run <scope> --sequence.shuffle --sequence.seed=7"}`, or jest's
  `--randomize --seed=7`.
- Jest sandboxes globals, so the clock and random axes don't reach test code through
  `NODE_OPTIONS`. Add `--setupFiles {preload}` to the jest test command. The script fills in the path.
- Python: the TZ and locale axes work as they are. The clock, random, readdir and network axes are
  Node-only, so pass `--only tz-east tz-west tz-half-dst locale-de locale-tr`.

## 3. Run

```bash
perturb.py --dir <project or $OUT/reference> --test-cmd "<scoped test command>" \
  [--probe-cmd "<runs only the probe file>" --inputs $OUT/probes/fuzz/cases.jsonl] \
  [--axes $SCRATCH/axes.json] --out $SCRATCH/perturb
```

It clones `--dir` and never runs in place. With a wiggle-room probe, it replays up to 500 of the
smallest fuzz inputs and drops any whose baseline output varies between two runs. Results go to
`perturb.json`, and a summary is printed.

| Axis | Contract | What changes |
|---|---|---|
| `tz-east` | within | TZ=Pacific/Kiritimati (UTC+14) |
| `tz-west` | within | TZ=Pacific/Pago_Pago (UTC-11) |
| `tz-half-dst` | within | TZ=Australia/Lord_Howe (UTC+10:30, 30-minute DST) |
| `locale-de` | within | LANG/LC_ALL=de_DE.UTF-8 (decimal comma, day-first dates) |
| `locale-tr` | within | LANG/LC_ALL=tr_TR.UTF-8 |
| `clock-ahead` | within | wall clock about 1000 days ahead |
| `clock-backwards` | within | wall clock runs backward for each process's first 30s |
| `readdir-reverse` | within | directory listings reversed |
| `network-down` | within | non-loopback connections refused (local servers still work) |
| `random-extremes` | beyond | `Math.random` alternates 0 and 1-2⁻⁵³ |

Your own timezone sits between the two TZ extremes, so one of them may change nothing. That's
expected.

## 4. Diagnose

For each axis with an effect, read the failing test or the changed probe example, then the code
it reaches. Decide where the reliance lives:

- **The test relies on the environment.** It hard-codes this year, expects `1,234.5` from
  `toLocaleString()`, or expects a listing order. The code may be fine. Fix the test by injecting
  the clock, timezone or locale.
- **The code relies on the environment.** Day boundaries in host time, elapsed time computed with
  `Date.now()`, a "latest" file taken as `readdir()[0]`. Either make it part of the contract (take
  a timezone or locale parameter, document "UTC only"), or fix it (`performance.now()` for elapsed
  time, sort the listing).
- **Outputs changed but the tests pass.** The behavior depends on the environment and nothing pins
  it. Ask whether that's intended. Host-locale formatting in a UI may be. In a stored key it isn't.
- **Beyond-contract breaks**: check whether the failure is loud and safe. A thrown error is
  usually fine. An empty id or a silent wrong value isn't.

Cite `file:line` for each. Suggest the fix; don't make it. The user decides.

## Report

```markdown
## Perturb — {target}

**Axes:** {n} run · {k} with an effect · probe: {inputs} inputs ({unstable} unstable dropped | no probe)

| Axis | Contract | Effect | Relies | Where | Suggested |
|---|---|---|---|---|---|
| tz-east | within | breaks tests | code | src/report.js:3 | take a timeZone parameter, or document UTC |

### Not covered
{axes skipped and why (Python, jest without setupFiles), plus what no axis reaches here: concurrency,
latency past the contract, input scale}
```

Latency and timeouts past the contract (a 30-second dependency call) aren't axes. They need a
running system and a blast radius, which makes them game-day work, not a test-suite pass.
