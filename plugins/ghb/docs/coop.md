# /coop — the cooperative engineering loop

A fork of [`/sloop`](sloop.md) where you are a first-class builder, not just the final
reviewer. The change is split into slices, each slice is tiered, you build the slices you
need to understand and agents build the rest, adversarial reviewers attack everything, and
a coordinator iterates until the code passes review.

sloop's bet still holds — AI is decent at building bounded things and bad at knowing when
it's wrong, so nothing is trusted on a single pass. coop adds a second bet: for some slices
the *human's understanding* is a required output, not just correctness, and that
understanding only comes from building or re-deriving the code. So coop routes those slices
to you on purpose, instead of handing you a finished diff to rubber-stamp.

This page is the overview. The workflow itself lives only in
[`skills/coop/SKILL.md`](../skills/coop/SKILL.md), and the tier rubric only in
[`tiers-core.md`](tiers-core.md) and [`tiers.md`](tiers.md).

## When to use it

Reach for coop over sloop when you'll own or maintain the code and a wrong mental model is
expensive — or when the point is to *learn* the code, not just ship it. It's the answer to
"the agent could build this, but then I wouldn't understand it." If you genuinely don't need
the model — throwaway, boilerplate, a well-understood change — plain sloop is less overhead.

## Tiers

Each slice is **Own** (you build or re-derive it), **Co** (an agent builds, you review it
predict-before-peek), or **Race** (an agent builds, you check it works). The rubric for
deciding is in [`tiers-core.md`](tiers-core.md).

## Usage

```
/coop [task description]
/coop --escalate=co [task description]
/coop --escalate=co,race [task description]
/coop --yolo [task description]
```

`--escalate` sets who builds which tier. By default you build Own and agents build the rest;
`=co` adds Co to yours; `=co,race` (or `=all`) has you build everything while agents only
plan, review, and verify. `--yolo` hands every slice to agents and skips the approval gate.

## At a glance

0. **Spec, slice & tier.** Your task becomes a spec, split into tiered slices with a contract
   (a "shell") at each seam. You approve the spec, the tiering, and the shells.
1. **Build.** You build your slices in your normal checkout while agents build theirs in
   parallel worktrees; their branches merge back when done.
2. **Review.** Adversarial reviewers attack every slice at full depth, including yours.
3. **Adjudicate.** The coordinator triages findings. Mechanical fixes inside your slices go
   to agents and get logged in a ledger; fixes that change your slice's shape come back to
   you. Before the loop can pass, you do a per-tier review — [`re-derive.md`](re-derive.md)
   is the method — while a saboteur checks the tests in the background.
4. **Report.** The sloop report plus who built what, the ledger, and an understanding check
   on each slice you built.

## What you get back

The work lands on a feature branch. You come away with the code *and* a real model of the
parts that mattered — because you built them — while the parts that didn't were handled for
you and still survived adversarial review. The understanding check at the end is the proof:
a passed loop where you can't explain your own slices cold is a failed loop.

## Limits worth knowing

- The coordination is only as parallel as the seams allow. Tightly coupled slices, or shells
  that won't stabilize, fall back to sequential.
- Passing the loop still means the code survived adversarial review, not that it's correct.
  You're the final reviewer.
- A slice that keeps needing shape-changing fixes has the wrong shape, not thin coverage. The
  loop stalls there and escalates to you rather than piling on more patches.
