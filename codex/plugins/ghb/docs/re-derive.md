# Re-deriving — how to actually review a slice you didn't build

[`tiers-core.md`](tiers-core.md) says what your review has to achieve per tier: predict-before-peek on a
Co slice, re-derive anything bubble-up flagged, confirm behavior on a Race slice. This is the
method for the first two — the read order that gets you a real model of code an agent wrote,
instead of the feeling of having read it.

It applies when an agent built the slice and you now need the model: agent-built Co slices,
and any slice bubble-up re-tiered to Own. An Own slice you built yourself needs none of this —
the re-deriving was the building. A Race slice needs none of it either; check the behavior and
move on.

## Why not just read the diff

Reading a diff top to bottom follows the order files happen to sort in, which has nothing to
do with how the code works. You end up checking each hunk in isolation and never build the
through-line, and because every individual hunk looks reasonable, you come away confident. That
confidence is the thing this exists to prevent — it's the rubber-stamp coop was built to avoid,
just slower.

## The four passes

Read the slice four times, in this order, all the way through each time. The order is the point:
each pass gives you the vocabulary for the next one.

**1. Types and interfaces.** The data shapes the slice consumes and produces. Signatures, new
types, schema and migration changes, the shells at its boundaries. Nothing about behavior yet —
just what flows.

**2. Data flow.** Where data enters, what transforms it, where it exits. Entry point → transform
→ exit, plus anything that fans out (a query that dispatches, a write that triggers a hook).

**3. Business logic.** What the code decides. Branches, guards, short-circuits, ordering,
the conditions under which each path runs.

**4. Edge surfaces.** Where the code *could* go wrong — nullable values, unguarded branches,
external input, concurrent paths, context assumptions (an auth call in a queue worker),
anything the shell promised that the body has to hold up.

Pass 4 names locations, not fixes. "This branch is unguarded and the input is external" is
the observation; what to do about it is a finding you raise afterward, if you decide it's wrong.

## Predict before you peek

At each pass, say what you expect before you look — out loud, in the loop, or written down. Not
"I expect this to work": name the specific shape, the specific path, the specific branch. Then
read.

A prediction that misses is the whole return on the exercise. It means your model and the code
disagree, and one of them is wrong — which is exactly the information a diff read gives you
zero of. Chase every miss until you know which side was wrong. A miss where the *code* turns
out to be right is still a miss: your model was off, and you keep going until it isn't.

Predicting after you've read is not predicting. If you catch yourself doing it, you've turned
the review back into a diff read.

## Cite while you read

Every observation gets a `file.ts:LINE`. This isn't bookkeeping — a claim you can't cite is a
claim you're making about code you didn't locate, and it's how a vague sense that "the
validation happens somewhere in there" survives review. If you can't point at it, you haven't
found it yet.

## What the map is not

If the coordinator hands you a map of the slice to read against, it describes and stops: here
are the types, here's where data enters and exits, here's what the logic decides, here are the
branches. It never says *verify this*, *confirm that*, *make sure*, *consider*, or *is this
intended?* — and neither do your notes during the read.

The moment the map tells you what to check, you're working someone else's checklist and the
re-derivation is gone. You'd get a list of confirmations instead of a model, which is the
failure this whole procedure exists to prevent. Deciding what's wrong is your job, and it comes
after the four passes, not during them.

## When you're done

You can explain the slice cold: what it takes, what it does, what breaks if a key assumption
changes. That's the same bar as the understanding check in Phase 4 — if you can't clear it here,
the check will catch it there, and the loop won't close either way.
