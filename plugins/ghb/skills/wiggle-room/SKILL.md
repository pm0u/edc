---
name: wiggle-room
description: Measure how much a test suite actually pins — delete a bounded module's implementation, have cheap isolated models rebuild it from the tests alone, and diff the rebuilds' behavior against the original. Every divergence is a gap in the spec, a free choice, or a bug in the original.
---

# Wiggle Room

A test suite defines a class of programs, not a program. Anything that passes is a valid
implementation, and the question nobody can answer by reading the tests is how wide that
class is. This skill measures it directly: delete the implementation of one bounded unit,
let several cheap, isolated builders rebuild it with nothing but the tests and the interface,
and run every green rebuild side by side with the original on the same inputs.

Where they agree, the tests (or the problem) pinned the behavior. Where they disagree, one of
three things is true, and the human decides which:

- **Pin** — the behavior matters and nothing enforces it. Write the test.
- **Free** — the behavior genuinely doesn't matter. Record it so it's never raised again.
- **Original wrong** — the rebuild is right and the code you had is the bug.

Cheap models on purpose. A careful model converges on the most obvious implementation, which
is usually the one you already have — it hides gaps. Sloppy builders take more of the paths
the tests allow, so more gaps show up per round. Accuracy comes from the tests, the re-run,
and the diff, never from trusting a builder.

You are the coordinator. Builders are separate headless processes (`claude -p` for Claude models,
`codex exec` for Codex) in history-free copies of the repo. They aren't subagents, because a
subagent shares your session's sandbox and permissions and could read the original. You never write the
implementation; you write the interface stub and the targeted probe inputs, and a subagent that never sees the original writes the generators.

## Usage

```
/wiggle-room <path(s) to rebuild> [--named=<role:model,...>] [--blind=<role:model,...> | --no-blind] [--budget=USD]
```

$ARGUMENTS

Default matrix: four roles, each built by both Haiku and Codex (`gpt-6-luna` at medium effort),
$2 cap per Claude build. A run typically costs about $1, almost all of it Haiku; the caps bound it
at $8 plus a few cents of Codex:

| Role | Room | Builds |
|---|---|---|
| adversary | named | `adv:haiku`, `adv:codex` |
| minimal stance | named | `minimal:haiku`, `minimal:codex` |
| thorough stance | named | `thorough:haiku`, `thorough:codex` |
| no stance | blind | `plain:haiku`, `plain:codex` |

`--named` and `--blind` replace a row set (`<role>:<model>`, role `adv`, `plain` or a stance from
`scripts/stances.txt`, model `codex` or a Claude alias); `--no-blind` drops the blind room. Scripts live in
`${CLAUDE_PLUGIN_ROOT}/skills/wiggle-room/scripts/`. Everything happens in a scratch directory
(`$OUT`, a fresh directory of its own: `~/.wiggle-room/<target>-<timestamp>`; the sandbox fences
everything in it outside a builder's own copy off from that builder). Nothing touches the user's repo until
triage, and then only test files, only after approval, and never committed.

## Scope: bounded units only

The target has to be something with a clear seam — a module, an API route handler, a DB
adapter, a parser, a reducer. You can delete it, leave a stub with the same exports, and the
rest of the codebase still compiles against the stub. If deleting the target means also
deleting UI, store wiring, and API calls interleaved with it, the boundary is wrong. Say so and
suggest a smaller seam instead of running.

## Phase 1: Boundary — the one gate

The deletion boundary is a spec decision, so the user signs off on it before anything runs.

1. Resolve the repo root and the target paths (files or directories, repo-relative).
2. Find the **public interface**: what the rest of the codebase imports from the target, and
   what the tests call. Grep for imports of the target from outside it.
3. Find the **tests that pin it**, and a **scoped test command** that runs only those
   (`npx vitest run src/routes/waypoints`, `go test ./internal/geo/...`, `pytest tests/geo`).
   Also find the **setup command** (`pnpm install --frozen-lockfile`, `go mod download`, ...).
4. Run the scoped test command in the real repo. It must be green — a rebuild can't be
   measured against a red baseline.
   Then sort the tests. **Behavioral** tests go through the public interface and assert what a
   caller can observe. **Structural** tests reach past it: they import non-public modules, mock
   or spy on the target's own internals, assert call counts on its private collaborators, or
   snapshot its internal state. Mocking a real boundary (network, DB, clock, filesystem) is a
   seam, not a structural test. Structural tests pin the original's shape rather than its
   behavior, so they turn rebuilds red for reasons that say nothing about the spec, and they're
   often the only thing guarding a behavior.
5. Draft the **interface stub**: the target's exported names and signatures (with their types)
   and bodies that throw `not implemented`. Nothing else — no private helpers, no comments
   describing behavior, no constants beyond what the tests import. The stub is part of the
   spec, so everything in it is pinned by definition.
6. Present the boundary: paths being deleted, the stub, the tests (structural ones listed with
   the line that makes them structural), the test and setup commands. If there are structural
   tests, offer a **behavior-only round** alongside the normal one (Phase 2).
   Point out anything outside the target that reaches into its internals — that's a seam
   problem, and it will show up as a broken build. Wait for the user's go-ahead.

Later rounds reuse the approved boundary; only the tests change.

## Phase 2: Isolate

```bash
isolate.py --repo <repo> --out $OUT/room --remove <target paths...> > $OUT/manifest.json
```

This copies the working tree (tracked plus untracked, minus gitignored, so uncommitted test
edits come along) into a fresh directory with no git history, minus the targets. Then:

1. Write the stub files into `$OUT/room` at the target paths.
2. Run the setup command in `$OUT/room`.
3. `git -C $OUT/room add -A && git -C $OUT/room commit -qm "wiggle-room base"` — and record
   `BASE=$(git -C $OUT/room rev-parse HEAD)`. Check that `node_modules` (or the equivalent)
   is ignored rather than committed.
4. Run the scoped test command in the room. **It must fail.** If the tests pass against a stub
   that throws, they don't exercise the target at all — stop and report that as the finding.
5. Leak scan:
   ```bash
   leak_scan.py --repo <repo> --room $OUT/room --removed <target paths...> \
     --public <stub paths...> --public <test globs...> > $OUT/leaks.json
   ```
   It lists room files containing identifiers that exist only in the deleted code. Committed
   build output, source maps, snapshots of internals, and docs that paste the implementation
   are leaks — delete them from the room and amend the base commit. Another source file that
   imports a private helper is a seam problem — go back to Phase 1. Domain vocabulary that just
   happens to match is noise.

**Behavior-only round.** When the suite has structural tests, build a second room the same way
with them gone: pass whole structural test files to `--remove` as well, and delete structural
cases from mixed files in that room before the base commit. Its test command runs only what's
left. Build both rooms (`$OUT/builds` and `$OUT/builds-behavior`) and probe them together. A
divergence only the behavior-only builds show is guarded by structural tests alone. Each one is
a structural test to rewrite as a behavioral one before it's safe to refactor the target.

**Blind round.** Names carry a spec of their own. A builder that sees `slugify` reaches for the
slug library it knows best, and the tests mostly confirm that prior. A blind room hides every
word that carries meaning. Builders get the tests' inputs and outputs and nothing else. A
behavior only the named builds share is pinned by the name's conventions, not by any test: an
unknown known, made measurable.

Test data carries meaning too. On the slug toy, every blind builder worked out the domain from
`'Hello World'` → `'hello-world'` and wrote the same conventions (accent folding, length cap) as
the named builds. The blind round found nothing the named round hadn't. It's in the default
matrix because the names that matter most (internal domain modules, opaque ids, house formats)
are the ones the data doesn't explain. When the target's names are generic and the data says
everything they do, suggest `--no-blind` at the boundary gate.

1. Write `$OUT/blind-map.json`: a list of the words to hide. Include the target's exported names,
   its option and field names, the words in its file names, and domain words in error messages
   the tests assert on. Leave out words that appear in test data, and package names.
2. Make the room. The globs pick which files get titles rewritten and comments stripped (JS/TS only):
   ```bash
   blind.py make --room $OUT/room --out $OUT/room-blind --map $OUT/blind-map.json \
     --tests <test globs> --strip-comments <test globs> <stub globs> \
     --test-cmd "<scoped test command>" --repo <repo> --target <target paths> > $OUT/blind.json
   ```
   It replaces each word with an opaque token everywhere (code, strings and paths), renames test
   titles to `case N`, strips comments, and commits a history-free base. Two checks must hold:
   `stub_fails`, and `original_passes`, meaning the original implementation, blinded the same way,
   passes the blind tests. If it fails, the map changed what the tests say, not just how they read.
   Read `leftovers` and extend the map until nothing that matters is left.
3. Write `$OUT/task-blind.md` with the blind paths and the blind test command (both are in
   `blind.json`), then build the blind row (Phase 3) from `$OUT/room-blind` into
   `$OUT/builds-blind`. Audit against the blind room: `--git-dir $OUT/room-blind/.git`, its base,
   the blind targets.
4. Restore each green build: `blind.py restore --room $OUT/room --blind-room $OUT/room-blind
   --map $OUT/blind-map.json --build $OUT/builds-blind/<name> --out $OUT/blind/<name>`. Run the
   normal test command in each. A failure there means the round trip broke, not the build.
   Builders often reuse a hidden word on their own (a local `separator`). `restore` renames
   those to `<word>__own` first, so they can't collide, and lists them in `renamed_own_words`.
   That list also shows the domain leaking back through the data.
   Restored builds go into the probe and fuzz like any others (`--build $OUT/blind/plain-*`, and
   `--adversary $OUT/blind/adv-*` if the blind row has adversaries).

## Phase 3: Build

Write the task to `$OUT/task.md`:

```markdown
You're implementing {target paths} in this repository. The implementation is missing; what's
there is a stub with the exported interface, which you must keep.

Make this command pass: `{scoped test command}`

- Only create or change files under: {target paths}. Changes anywhere else, including tests and
  config, disqualify the build.
- Read anything else in the repository you like — callers, tests, and types are your spec.
- The original implementation doesn't exist anywhere you can reach. Don't look for it.
- When the command passes, stop.
```

Nothing about the original's behavior, its history, or why you're doing this.

**The matrix.** Builds from one model fail in the same places, so four plain Haiku builds act
like about one: on the toy, they scored 1.44 effective builds out of 4. Each axis of the matrix
pulls them apart a different way:

- **Roles.** A stance (`scripts/stances.txt`, or `WIGGLE_ROOM_STANCES=<file>` with one
  `name: text` per line) tells a build what to do where the tests are silent, which aims its
  variation at the unpinned space being measured. The default uses the two ends: minimal, the
  build that does the least the tests allow, shows what they leave to convention; thorough, the
  build that handles every edge it can think of, shows what they leave unguarded. On the toy,
  rotating five stances took four Haiku builds from 1.44 to 3.91 effective builds; `--named` can
  add the others (strict, lenient, conventional).
- **Adversaries.** An `adv` build is told to pass every test while being as wrong as the tests
  allow, in ways that would still pass review: no special-casing test inputs. Good-faith builds
  only disagree where reasonable people would, which keeps findings small. The adversary goes
  after what callers rely on, so the bigger gaps show up there. Its divergences are deliberate.
  They stay out of effective builds, and each one counts as behavior the tests let a plausible
  implementation break.
- **Models.** A different model family misses in different places. On `color.ts`, Haiku and Codex
  (`gpt-6-luna`) each found gaps the other didn't, and mixing them beat four Haiku builds.
  Codex runs at medium effort (`WIGGLE_ROOM_CODEX_EFFORT`): high effort made luna converge on
  Haiku's conventions and lose behaviors of its own. `WIGGLE_ROOM_CODEX_MODEL` swaps the model.
- **Rooms.** The blind row builds without names (Phase 2), so a behavior only the named builds
  share is one the names pinned, not the tests.
- **Planning.** Before any building, a read-only planner per build lists what the tests leave
  open and makes its role's choice on each one. Planners run in sequence, and each good-faith
  planner sees the earlier good-faith readings and is told to choose differently. Each builder
  then implements its own reading. This adds a cheap sequential step; `WIGGLE_ROOM_PLAN=0` skips
  it.

Expect more divergences that you'll mark free. A deliberately lenient build disagrees with a
strict original in ways nobody cares about. That's the right kind of noise for a run whose output
is "what the tests don't pin".

Plan first, and show the plans before building:

```bash
WIGGLE_ROOM_STEP=plan run_builds.sh $OUT/room $OUT/builds adv:haiku,adv:codex,minimal:haiku,minimal:codex,thorough:haiku,thorough:codex <budget> $OUT/task.md <repo> [<other worktrees of repo>...]
WIGGLE_ROOM_STEP=plan run_builds.sh $OUT/room-blind $OUT/builds-blind plain:haiku,plain:codex <budget> $OUT/task-blind.md <repo> [<other worktrees of repo>...]
```

Read every `*.plan.md` in both build directories and present the **open behaviors**: the union of what the
planners say the tests leave open, grouped by dimension (inputs, errors, limits, ordering,
encodings, state, concurrency…). For each, note how many planners flagged it and whether the
adversary plans to exploit it. This is the cheapest output of the whole run and the broadest:
it's a gap list before any code exists, and it's the frame the probe results get rolled up
into. Then build, in the background, with the same arguments:

```bash
WIGGLE_ROOM_STEP=build run_builds.sh <same arguments, once per room>
```

Every path after the task file is forbidden to the builders. Pass the repo and every worktree
from `git -C <repo> worktree list`. Each builder gets an APFS-cloned copy of the room, `dontAsk`
permissions, its own scratch directory, no web, no subagents, no MCP, no hooks, and no user
settings. Bash runs in Claude Code's sandbox, which fails closed: no network, and reads and writes
limited to its own build and scratch directory. The forbidden paths, sibling builds, everything
else in `$OUT`, session transcripts and credential directories are denied to every tool. The
fence only knows the paths it's given. Any other copy of the original on disk is still readable,
so pass every one.

Claude builders run headless with `claude -p`, each capped at the budget, and the audit reports
their cost. Codex builders get the same fence through a Codex permissions profile: the whole disk
readable except the forbidden paths, `$OUT`, credentials and Codex's own auth and session history,
and only their own build and scratch directory writable, no network. Planners get their build
read-only. Codex has no budget cap, so `WIGGLE_ROOM_TIMEOUT` (default 1800 seconds) stops any that
run long, and the audit reports only tokens for them. You're notified when the script exits.

## Phase 4: Audit

For each build directory in `$OUT/builds` and `$OUT/builds-blind` (named `<role>-<model>`):

```bash
audit_build.py --build <dir> --base $BASE --git-dir $OUT/room/.git \
  --transcript $OUT/builds/<name>.plan.transcript.jsonl $OUT/builds/<name>.build.transcript.jsonl \
  --target <target paths...> \
  --test-cmd "<scoped test command>" --test-file <test paths...> \
  --run-root $OUT --forbid <repo> [<other worktrees of repo>...]
```

The audit re-runs the tests itself. A builder's claim that they pass counts for nothing. The tests
execute the builder's code, so they run inside the builders' fence (`sandbox.py`, Codex's sandbox:
no network, the repo, the rest of `$OUT` and credentials unreadable). That needs the `codex` CLI
even when every build is a Claude one. Then it classifies the build:

- **out-of-bounds** — changed files outside the targets. Discard; its tests don't run.
- **red** — tests fail. Discard, but keep count.
- **green** — eligible for the diff.

Two more signals worth reading on green builds, not just counting:

- `test_literals_in_impl` — string literals from the tests that appear in the implementation.
  A builder that special-cases test inputs passed because the tests are example-shaped where
  they should be property-shaped. That's a finding in its own right: the test can be satisfied
  without the behavior it names.
- `outside_paths` — absolute paths outside the build the transcript referenced. Usually
  toolchain noise. Anything that looks like another copy of the original (a second clone, a
  vendored or published copy) wasn't fenced. Discard the build and add the path to the forbid list.

An adversary with test literals in its implementation cheated rather than found a gap. Drop it.
A red adversary is a good sign: the tests resisted it.

If fewer than two good-faith builds are green, the round can't diff. A high red rate means the target is
too big for the builder model or the tests are coupled to implementation details. Report which,
and offer a larger model or a smaller boundary.

## Phase 5: Probe

Now, and not before, the probe gets written. It runs the same inputs through the original and every
green build and records what comes out. The probe never needs to know the right answer, because the
original supplies it. The only judgment left is which inputs get tried, and this phase keeps as
little of that with you as it can. You've read the original, so inputs you choose are biased toward
what you know it does. Behavior nobody thought of stays invisible, and that's exactly the
behavior this skill exists to find.

Inputs come from three sources, each with less model judgment than the one before:

- **Targeted** (you): boundary values and cases aimed at what you know the original does, plus real
  fixtures or recorded inputs if the repo has them. Written to `$OUT/probes/fixed.json`.
- **Type-derived** (a subagent that never sees the original): generators that cover the interface's
  declared input types exhaustively.
- **Divergence-guided** (`fuzz.py`): mutations of whatever made the implementations disagree. The
  builds' own differences decide where to search.

1. Build the reference: `cp -cR $OUT/room $OUT/reference` (plain `cp -R` off macOS), then copy
   the original target files from the repo over the stub.
2. Spawn a `general-purpose` agent to write the probe. Give it the room path, the stub paths, the
   test command, and the protocol below, and tell it to read only inside the room: the stub, its
   types, its callers, and the tests. Not the reference or the repo. It writes
   `$OUT/probes/wiggle-room.probe.<ext>`, a test file in the project's own runner that drives the
   target the way the existing tests do: the same request helper for a route, the same test DB
   setup for an adapter. No new harness. The probe contains:
   - `generate(seed)`: a deterministic input built from the declared types and nothing else. Every
     union member, optional fields both absent and present, null wherever the type allows it,
     empty and large collections, numeric extremes, unicode in strings, and inputs the tests show
     get rejected. Follow the type, not a guess about the behavior.
   - `mutate(input, seed)`: a small deterministic edit. Half the mutations shrink the input (drop
     characters or elements, move numbers toward zero), which keeps the driver's examples small.
   - inputs as JSON, so the driver can hand them back. Anything that isn't JSON (dates, buffers,
     functions) gets an encoding the probe owns.
   - outputs recorded canonically: return values as JSON, thrown errors as
     `{"$error": <name>, "message": <message>}`, and side effects the interface exposes (rows
     written, calls made) as part of the output.
   - the protocol: read the request list from `$WIGGLE_ROOM_PROBE_IN`; each request is
     `{id, seed}` → `generate(seed)`, `{id, seed, from}` → `mutate(from, seed)`, or `{id, input}`
     → run as-is; write `{id: {input, output}}` to `$WIGGLE_ROOM_PROBE_OUT`.

   **Stateful targets** (adapters, stores, routes with side effects, anything with a lifecycle):
   one call in and one value out never reaches the state where those go wrong. There, an input is
   a sequence of operations, `[{"op": "insert", "args": [...]}, {"op": "get", ...}]`, run
   against a fresh instance (fresh test DB, fresh store), and the output is the list of
   per-step results, with errors recorded in place, plus the observable end state. `generate`
   builds sequences (1–20 ops, repeated keys, operations on things that don't exist, the same
   op twice). `mutate` inserts, deletes, duplicates, or swaps steps, and half the time removes
   one.

   Check the generators against the stub's types. Don't check them against the original.
3. Write `fixed.json`: your targeted inputs, in the probe's input encoding.
4. Copy the probe into the reference and every green build at the same path, then run the search:
   ```bash
   fuzz.py --ref $OUT/reference --build $OUT/builds/{minimal,thorough}-{green...} $OUT/blind/plain-{green...} [$OUT/builds-behavior/...] \
     --adversary $OUT/builds/adv-{green...} --probe-cmd "<runs only the probe file>" --fixed $OUT/probes/fixed.json --out $OUT/probes/fuzz \
     --run-root $OUT --forbid <repo> [<other worktrees of repo>...]
   ```
   Each round materializes inputs in the reference, runs the reference twice and drops cases it
   disagrees with itself on (time, randomness, ordering), runs every build on the identical
   inputs, and mutates this round's divergent inputs for the next round. Every probe run, the
   reference's included, runs inside the same fence as the audit. It stops after 3 rounds
   with no new divergence group. If many cases come back unstable, normalize them in the probe
   and rerun. An unstable reference hides real divergences.

`classes.json` groups divergences by **shape**, meaning how a build differs from the reference
(`string->string(longer)`, `error:TypeError->string`). Each shape lists which builds showed it, with
the smallest input that produced it for each one. `cases.jsonl` has every case. `summary.json` has
**effective builds**: on contested cases, the average number of distinct behaviors across builds,
plus pairwise agreement and the shapes each build found alone. If effective builds sits near 1, the
round was really one build run several times. Check that the plans actually differ and that the
matrix mixes models. `adversary_only_shapes` lists shapes no good-faith build hit.

The builds show what the tests leave open. They can't show what the original relies on in its
environment, because every build ran in the same one. For that, offer `/ghb:perturb` on
`$OUT/reference` with the probe command and `$OUT/probes/fuzz/cases.jsonl`. It's model-free, and
its findings go in the report's Notes.

## Phase 6: Triage

Shapes are a mechanical first cut, not behaviors. One shape can hide several behaviors (CJK kept
and apostrophes kept are both `string->string(longer)`), and one behavior can show up under two
shapes. Read each build's example in a shape, and pull more from `cases.jsonl` when they differ. Merge and split them into behavior classes: "empty input: reference returns
[], builds 2 and 4 throw", "multi-character separators: reference fails to trim them". For each class:

- the smallest example input, the reference output, and each divergent build's output
- which builds diverged, and with what stance. Three of four disagreeing with the original
  is a different signal from only the lenient build disagreeing.
- its attribution (unpinned / partly pinned / incidental, the blamed commit, callers).
- your suggested call — **pin**, **free**, or **original wrong** — with a one-line reason.
  Suggest, don't decide. If the original throws where every build returns something sensible,
  the original is often the one that's wrong.

**Attribute before suggesting.** A divergence is either a missing test (someone wrote code for
this and nothing checks it) or incidental (it falls out of general logic and nobody chose it).
The original can tell you which. Spawn a `general-purpose` agent with the reference, the
classes, and the callers from Phase 1. For each class it:

- finds the smallest edit to the original that would remove the reference's behavior on the
  example (raise a constant, delete a branch, drop a special case), and writes it to
  `$OUT/probes/mutants.json` as `{class, input, file, find, replace, why}`. If no dedicated code
  produces the behavior, it says so instead.
- checks the callers. Does any call site pass inputs in this region, or depend on this output?
  It cites `file:line`.

Then verify the edits mechanically:

```bash
attribute.py --ref $OUT/reference --repo <repo> --mutants $OUT/probes/mutants.json \
  --test-cmd "<scoped test command>" --probe-cmd "<runs only the probe file>"
```

- **unpinned** — the edit changes the example's output and every test still passes. Dedicated
  code that nothing checks: **pin**. The blamed commit says why it exists, and a bug-fix commit
  makes that certain.
- **partly pinned** — the tests catch the edit, just not on this input. A missing case next to
  an existing test.
- **not attributed** / no dedicated code — incidental. **free**, unless a caller depends on it.
- A caller depending on it is **pin** whatever the code says (Hyrum's law).

Check `$OUT/ledger.md` first. Classes already marked free in an earlier round don't get raised
again.

Present the classes, plus the red/out-of-bounds counts and any test-literal findings,
and let the user make each call.

## Phase 7: Pin and repeat

1. **Pin**: after approval, write one test per pinned class in the user's repo, next to the
   existing tests. Keep the tests behavioral: call the interface, assert the output. Run them
   against the real implementation. They must pass there. **Original wrong**: report it as a bug
   and leave the fix to the user. Don't pin the wrong behavior.
2. Append the round to `$OUT/ledger.md`: each class, the call, and the test that pins it (or
   "free: reason").
3. Ask whether to run another round. Each round starts again at Phase 2 with the same boundary
   and the new tests. The working-tree copy picks them up uncommitted.

**Convergence** is two consecutive rounds that surface no new divergence class. That's the
closest thing to a number for "the tests pin this module." Report the round count it took, and
leave the ledger's free list where the user can promote it into the repo as documentation of
what's deliberately unspecified.

## Report

```markdown
## Wiggle Room — {target} — round {N}

**Builds:** {green}/{total} green · {red} red · {oob} out-of-bounds · ~${total cost}
**Matrix:** {each build: name, verdict} · **Effective builds:** {effective} of {green good-faith}
**Probe:** {cases} stable cases over {rounds} search rounds · {unstable} unstable · {shapes} shapes → {classes} behavior classes
**Convergence:** {new classes this round} new classes ({rounds since last new class} quiet rounds)

### Open behaviors by dimension
| Dimension | Planners flagged | Divergences | Adversary broke it | Attribution |
|---|---|---|---|---|
| {errors} | {3/4} | {2 classes} | {yes} | {unpinned ×1, incidental ×1} |

### Divergences
1. **{behavior}** — {builds with stances}. `{input}` → reference `{out}`, build-{n} `{out}`.
   Attribution: {unpinned at file:line (commit subject) | partly pinned | incidental} · callers: {file:line or none}
   Suggested: {pin | free | original wrong} — {reason}

### Guarded only by structural tests
{classes only the behavior-only round found, each with the structural test to rewrite, or "no behavior-only round"}

### Tests that can be satisfied without their behavior
{test-literal findings, or "none"}

### Cost
| Build | Model | Verdict | Cost | Output tokens |
|---|---|---|---|---|
| {adv-haiku} | {haiku} | {green} | {$0.24 reported} | {92k} |
| {adv-codex} | {gpt-6-luna@medium} | {green} | {~$0.012 estimate} | {5k} |
| **{model}** | | | **{total per model}** | |

From each audit's `cost_usd` and `cost_basis`. Claude's is what `claude -p` reported; Codex's is
estimated from its tokens at short-context prices (`CODEX_PRICES` in `audit_build.py`). Your own
work and the subagents you spawn (probe, attribution) run in this session and aren't counted.

### Notes
{unfenced copies found, seam problems, why builds went red, anything you couldn't probe}
```
