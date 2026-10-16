# Tier

Decide what you should build yourself and what you should hand off, for one task, without
running a loop. Classify it, then sequence the split: **you build the part you need to
understand, and when you're done an agent takes the remainder.**

The classification rubric is **`../docs/tiers-core.md`** with the whole task
as the unit. This command adds no machinery of its own — no slices, no shells, no reviewers, no
ledger, no iteration. If the task needs any of those, it says so and points at
[`$coop`](../docs/coop.md) instead of half-building it.

**Nothing here runs concurrently with the human.** Parallel human-and-agent building is what
forces shells and worktrees, and that's coop's job. Sequencing is what makes this command
light: one builder at a time means nothing can collide.

## Usage

```
$tier [task description]
```

Use the user's skill invocation and conversation context as the input, including any flags.

If no task was given, use the conversation. If there's no task in the conversation either, ask
for one.

## Step 1: Ground it

Classification is a fast call; its **inputs** are the expensive part. Don't guess at them.

Before classifying, get real answers to whichever of these the task actually turns on:

- **How many callers** depend on the behavior being changed, and do any depend on its exact
  current shape?
- **Is the failure loud?** Does a wrong result throw, fail a test, or fail to compile — or does
  it fail silently, return a plausible wrong value, or corrupt data?
- **Core or periphery?** Domain logic, invariants, shared state — or glue and plumbing?
- **Novel to the operator, or a pattern already in this codebase?** Find the existing instances
  if there are any.

Answer them by reading the code. Spawn `loop-researcher` when the task spans enough of the
codebase that you'd otherwise be inferring — it exists for exactly this and returns a brief,
not a plan. Skip it when the answers are already in context or one grep away; a researcher
round-trip on a task you can already see is the ceremony this command exists to avoid.

## Step 2: Check the floor

Read the floor rule in `docs/tiers-core.md`. If the task clears it — one mechanical edit, loud
failure mode, and the operator already holds the model — **say so in one line and stop.**

```
Below the floor: rename with a loud failure mode in code you already know. Just do it,
or hand the whole thing off. Nothing to split.
```

Most small tasks land here. Saying so and getting out of the way is a correct outcome, not a
failure to be useful.

## Step 3: Classify and split

Classify the task with the test in `docs/tiers-core.md`, then split it into **what you build**
and **what gets handed off**:

- **Own** → the operator builds it. Their understanding is a required output.
- **Co / Race** → handed off in Step 5.

Split at whatever line the work actually divides on. A task that reads as one thing is usually
mostly Race with a small Own centre — the retry *decision* is Own, the backoff helper and the
config plumbing are Race. Name the signal that drove each side; blast radius wins when signals
conflict.

Two things stay with the operator regardless of tier: a decision the task doesn't pin down (an
agent would be guessing for them), and anything where being wrong fails silently.

**Escape hatch.** Recommend `$coop` and stop when the split needs machinery this command
doesn't have:

- The Own and handoff parts touch the same files or the same function — they can't be sequenced
  cleanly, so they need shells.
- The handoff part isn't really Race — it's Co logic the operator will revisit, and it wants
  adversarial reviewers and a review pass, not a single build.
- The task decomposes into more than two or three pieces with real dependencies between them.

## Step 4: Present the posture

Show the split and stop. Short — this is meant to be read in fifteen seconds.

```
Task: add retry to the sync client

Floor: no — retry changes failure semantics, and a wrong result here
fails silently.

You build (Own)
  The retry decision in syncClient.flush(). Three callers depend on the
  current at-most-once behavior and nothing in the type system catches a
  double-send.

Handed off after (Race)
  The backoff helper, the config plumbing, the tests.

Your review on the return: confirm behavior, move on.
```

**Describe and stop.** State what the code is and why the tier landed where it did. Do not
write *verify this*, *confirm that*, or *consider whether* — a posture that tells the operator
what to check replaces their model with your checklist, which is the one thing the tier system
exists to prevent. The one exception is naming their review bar from the rubric, as above,
because that's an obligation rather than a checklist.

Then wait. The operator may re-split it, take more than you assigned them, or hand you the
whole thing — all fine. It's their understanding budget.

## Step 5: Sequence the handoff

After the operator signals their part is done:

1. Ask what they built and what they verified, in a sentence. You need it so the handoff isn't
   built against a stale reading of the file.
2. Spawn **one** `loop-dev` for the remainder, in the primary working directory — no worktree,
   because nothing else is building. Give it the task, the operator's part as existing context,
   the remainder as its scope, and the Race bar from the rubric: tests pass, behavior
   exercised. It does not touch the operator's part.
3. If `loop-dev` reports that a piece of its scope
   [bends](../docs/tiers-core.md#routing-a-fix--by-the-work-not-by-the-unit) the operator's
   code — it would move an invariant, a contract, or a decision nobody pinned — that piece
   comes back to the operator rather than getting built. Same rule the loop's builders follow.

If the operator would rather fire the handoff themselves, emit it as a ready-to-run prompt
instead of spawning.

## Step 6: Report

```
## Tier: add retry to the sync client

You built  — retry decision in syncClient.flush()
Agent built — backoff helper (util/backoff.ts), config plumbing, 4 tests
Verified   — `npm test src/sync` passes; retry exercised against a forced 503
Back to you — none

Your review: confirm the behavior, then move on. The Race bar is the whole bar here.
```

Name anything that came back to the operator and which trigger fired. If the agent's work
turned out to need review deeper than the Race bar, say that plainly — it means the split was
wrong, and the honest fix is a `$coop` run on that part, not a reviewer bolted on here.

## Guidelines

- **Classify, don't decide for them.** The output is a posture and its reasoning, never a
  verdict to rubber-stamp. If the operator can read the result without thinking, it's wrong.
- **One builder at a time.** The moment you'd run an agent alongside the operator, this is coop.
  Stop and say so.
- **The floor is a real answer.** Most tasks don't need splitting. Reaching for a split on all
  of them recreates the ceremony problem in a smaller package.
- **No loop, no reviewers, no ledger.** Race work's bar is that it works. Wanting more than
  that is a signal about the tiering, not a missing feature.
- **Ground before you classify.** A tier assigned off the task description alone is a guess with
  a confident format.
