# Tiers (core) — where your understanding budget goes

The classification rubric, independent of any workflow that uses it. It answers one
question about a unit of work:

> If the human's model of this code is wrong later, what does that cost — and is their
> understanding therefore a required output of doing the work, or not?

**This file defines the classification. It does not define the unit.** Each caller supplies
its own unit and its own routing:

| Caller | Unit | Routing |
| ------ | ---- | ------- |
| [`coop`](tiers.md) | a slice of a change, bounded by shells | who builds it, who fixes it, review depth per phase |
| `$resolve-pr-feedback` | a review thread, or a batch of same-shaped threads | who addresses it — one batched agent pass vs. by hand |
| [`$tier`](../commands/tier.md) | the whole task | whether you build it or hand it off, and how you review what comes back |

Everything below applies unchanged regardless of which unit is in play. Workflow machinery —
slices, shells, build order, Build Reports, the ledger — belongs to the caller, not here.

## The floor — when not to classify

Classification costs something. Below a floor it costs more than the decision is worth, and
running the rubric on a one-line edit is worse than just making it.

**Skip classification and treat the unit as Race when all three hold:**

- **It's one mechanical edit** — a rename, an added guard for a case you already knew was
  possible, a missing test case, a copy change, a lint or type fix.
- **The failure mode is loud** — being wrong throws, fails a test, or fails to compile. It
  does not fail silently or corrupt data.
- **You already hold the model** — it's in code you've classified before or wrote yourself,
  and the edit doesn't change what you'd say about how it works.

Any one of those failing puts the unit back through the test below. The floor is about
*ceremony*, not risk: it exempts work whose tier was never in question, and nothing else.

## Batching — classify the set, not each item

When a caller hands you N units of the same shape — review comments, a list of small fixes,
repetitive edits across files — **classify the batch once, then pull out the exceptions.**
Sorting a dozen items individually is the ceremony the floor exists to avoid.

The pattern: assume the batch is Race, scan it for the one or two units that trip a signal
below, split those out and classify them properly, and send the remainder through as one
pass. A batch that's mostly exceptions isn't a batch — classify each.

## The three tiers

Every unit is one of these. Read down a column for a tier's profile; read across a row to
compare the three on one thread.

| Thread                   | Own                                                                 | Co                                               | Race                                            |
| ------------------------ | ------------------------------------------------------------------- | ------------------------------------------------ | ----------------------------------------------- |
| **Qualifies when**       | high blast radius; core or hard to verify                           | real logic you'll revisit; moderate stakes       | throwaway or a known pattern                    |
| **Understanding target** | write or re-derive it; extend, debug, explain it cold               | the contract and the boundaries, not every line  | none — behavior only                            |
| **Default builder**      | you                                                                 | agent; you review actively (predict-before-peek) | agent                                           |
| **Verification bar**     | human comments that show understanding, or discussion with an agent that proves it | predict-before-peek review, then it merges       | tests pass; behavior exercised                  |
| **Your review**          | re-derive it — reconstruct the reasoning, don't just read it        | predict-before-peek, then accept                 | confirm it works, move on                       |

_Your review_ is what **you** do, and it only bites when an agent built the unit — for an Own
unit you built yourself, the re-deriving was the building. The method — the four-pass read
order, and how to predict before peeking — is [`re-derive.md`](re-derive.md).

Adversarial *agent* review is deliberately absent from this table. It runs at full depth on
every tier; a tier never talks a reviewer into going easier. Tier sets who builds and how
much the **human** reviews, nothing else.

## Classifying a unit

Weigh these, roughly in order. Fast — not a checklist to grind through. When they conflict,
blast radius wins.

- **Blast radius** — if your model of it is wrong, is the cost a lint fix or a 2am page? The
  dominant signal; it's the cost of being wrong.
- **Task fit** — how hard is it to get feedback and iterate? Code an agent can't verify
  itself leans Own.
- **Core vs. periphery** — domain logic, invariants, shared state? Or glue and plumbing?
  Usually tracks blast radius, but not always: a config file is periphery with high blast
  radius.
- **Return frequency** — will you touch this region again, or is it write-once?
- **Novelty** — new to you, or a pattern you've written many times? Scales how much *you
  specifically* gain from owning it.

**The test** (one line, so it's not endless reasoning):

> Blast radius is the spine. High blast radius + (hard to verify, core, novel, or you'll
> revisit) → **Own**. Low blast radius + periphery + known pattern → **Race**. Everything
> between → **Co**. Genuinely unsure → default **Co**.

Defaulting to Co rather than Own means you don't over-tier defensively. Callers that can
catch a mis-classified unit mid-work (coop's bubble-up) make that default safe; a caller
with no such backstop should read "unsure" as one step more conservative.

**Concrete anchors** (worked examples of each tier):

> Own: hard for an agent to verify, core logic or coordination, large blast radius
>
> Co: testing around _Own_ code, logic central to how the application functions but not
> complex, specific asks or edits from the operator
>
> Race: boilerplate, setup, copy/paste, refactor, reorganize, small bug fixes, text edits

## Who builds a tier vs. what tier it is

Classification is a property of the work. **Who builds each tier is a separate knob** — you
can take on more than your default (Own only), up to building everything in
codebase-familiarization mode. Classification still runs regardless: it drives review
intensity and ordering even when you aren't the builder. Callers expose this how they like
(coop uses an `--escalate` flag).

## Routing a fix — by the work, not by the unit

Tier decides who **does** a unit of work. It does not decide who **fixes** it afterward.
Most findings against a human-built core are mechanical — an unhandled input, a missing
guard, a case nobody anticipated, an optimization behind unchanged behavior. Routing those
back to the human because they landed in Own code is how a dozen one-line edge cases cost an
afternoon and teach nothing.

Classify every fix against an Own unit:

- **Absorbed** — the fix lands at an existing extension point: an added case, guard, or
  branch that leaves the code's shape, invariants, and contracts exactly as they were.
  Optimization that provably preserves behavior is Absorbed. → **an agent fixes it.**
- **Bends** — the fix changes an invariant, restructures control flow, moves a contract, or
  turns on a judgment nobody pinned down. → **you fix it.** This is the code the Own tag was
  protecting in the first place.

Genuinely unsure → **Bends**. The asymmetry is deliberate: an over-routed Absorbed fix costs
you a small edit you'd have made anyway, while an under-routed Bend quietly rewrites the
model you're supposed to be holding.

An agent that starts an Absorbed fix and finds that it bends **stops and reports it**. It
does not reshape a human's core to make a fix fit.

Once agents are landing fixes inside code you built, "you wrote it, so you know it" stops
being true on its own. Whatever record the caller keeps of those fixes, one test decides
whether a fix needs your attention:

> **Model-touching:** would someone who could explain this code cold before the fix now be
> wrong about it?

Adding a guard for an input you already knew was possible is no. Changing what the function
returns when that input arrives is yes. Re-derive the model-touching fixes; let the rest go.

Repeated Bends, or repeated model-touching fixes, in the same place are a signal about the
code rather than the coverage — its **shape** is wrong, and no number of absorbed cases
fixes a shape.
