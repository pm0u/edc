# Tiers in coop — slices, shells, and the ledger

The coop layer on top of [`tiers-core.md`](tiers-core.md). The core defines the
classification — the tiers, the signals, the test, the floor, and Absorbed vs. Bends. This
file defines what coop classifies (**slices**, separated by **shells**) and the loop
machinery that carries a tier through a build: bubble-up, and the ledger.

**Read both.** `tiers-core.md` is the classification; this file is coop's application of it.
Neither is complete alone, and both are injected into builder and plan-reviewer prompts —
subagents don't inherit them from the coordinator's context, so injecting only one leaves
agents either tiering blind or flagging blind.

> Tier is a property of the needed code, and specifically a divisible unit of the code, that
> is needed to accomplish the task. The goal is to create a shared understanding between
> agents and the human, and the framework serves as guidance for how to determine what is
> important to force onto the human.

## The unit: slices and shells

coop's unit is a **slice**. Slices are separated by **shells**. They're the same structure
seen from two sides — slices are the regions, shells are the boundaries between them.

A **slice** is the smallest unit of a change that (a) carries a single tier and (b) can be
built by one builder against the shells of its neighbors. Its defining property is
**tier-homogeneity**: if a candidate slice is half Own and half Race, it isn't one slice,
it's two — and the split happens at the boundary between them.

A **shell** is that boundary made explicit: a signature plus a one-line behavior contract
that both sides agree on before either builds.

```
function fn(ctx: Context, action: Action): FunctionReturnType { /* body filled by owner */ }
```

Whoever owns the higher-tier side writes the shell; the other side fills the body. A good
shell states its inputs, its output, and the one guarantee a caller can rely on — enough
that the other side can build against it without asking. A stable shell is what lets two
builders work adjacent slices in parallel without blocking on each other. An unstable one
(the contract keeps changing as you build) is the signal to stop parallelizing and sequence
instead.

Classify each slice with the test in [`tiers-core.md`](tiers-core.md#classifying-a-unit).
Tier is set in Phase 0 and can be challenged by the plan reviewer. coop's `--escalate` flag
is the who-builds knob the core describes; classification runs at every level.

**The core's floor does not apply to slices.** A slice small enough to clear the floor
shouldn't have been its own slice — fold it into a neighbor. The floor is for callers whose
units arrive pre-divided (a list of review comments, a single ad-hoc task); coop chooses its
own decomposition, so the equivalent move is a coarser one.

## Bubble-up — catching a mis-tiered slice mid-build

Phase 0 tiering is a guess and will sometimes be wrong. A build agent that starts a slice
tagged Co or Race and finds it's actually Own must flag it rather than race through — the
coordinator surfaces it to the human. This is the backstop that makes the core's
*unsure → Co* default safe.

A slice tagged Co or Race is actually Own the moment building it means any of:

- **You're touching a boundary, not an interior** — changing a shared invariant, shared
  state, or a contract other slices or callers depend on. The slice turned out to be a shell.
- **The blast radius is bigger than the tag** — a wrong result here fails silently or
  corrupts data rather than throwing loudly, or many callers depend on the exact behavior.
- **It hinges on a 2am-class decision** — correctness turns on a subtle, non-obvious call:
  concurrency, ordering, auth, money/units, a data migration.
- **You'd be guessing at intent** — the spec doesn't pin a decision that materially changes
  behavior, so building it means choosing for the human.

What to do when one fires:

- **If you can still build it correctly** — build it, but flag it in the Build Report's
  Own-tier section so the human re-derives it in review. A Co/Race tag downgrades their
  review, and an unflagged Own slice is one that silently skipped the model the human needed.
- **If building it requires an Own-class decision you'd only be guessing at** — stop and
  report blocked. Blocked beats fabricated; don't pick for the human on a slice that was
  supposed to be theirs.

## Bubble-down and the ledger

Fix routing is the core's rule: every finding against an Own slice is classified
[**Absorbed** or **Bends**](tiers-core.md#routing-a-fix--by-the-work-not-by-the-unit),
Absorbed goes to a fresh `loop-dev`, Bends comes back to the human, unsure is a Bend. Where
bubble-up catches a slice that mattered more than its tag, bubble-down catches a fix that
matters less.

coop's addition is the **ledger** — the record that keeps "you wrote it, so you know it"
true once agents are landing fixes inside a slice the human built. Every agent fix inside an
Own slice gets one line:

| Case | Delta | Model-touching |
| ---- | ----- | -------------- |
| the finding or input condition it answers | `file.ts:LINE` | yes / no |

Model-touching is the core's test: would someone who could explain this slice cold before
the fix now be wrong about it?

The human reads the whole ledger — it's a dozen lines, not a diff — and re-derives
([`re-derive.md`](re-derive.md)) only the model-touching entries. That's the trade: the
mechanical fixes leave their plate and their model still stays current.

A ledger is also a signal about the slice itself. Repeated model-touching entries, or
repeated Bends, on the same slice means its **shape** is wrong rather than its coverage. The
loop should say so — and stall — instead of grinding another round of guards onto it.
