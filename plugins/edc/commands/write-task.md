---
description: Turn a rough request into a task an agent or a human can execute AFK — grounded in real code, grilled before it is written
---

# Write Task

Turn a vague request — a bug report, a Slack thread, a hallway conversation, a "we should probably" — into a work item someone can pick up cold and finish without asking you anything.

Works for a Jira ticket, a GitHub issue, a task file handed to `/ghb:sloop`, or plain markdown you paste wherever.

## Usage

```
/write-task [source]
```

Source can be a description, a file path, an issue URL, a Slack/Discord link, a pasted transcript, or omitted (use the conversation).

$ARGUMENTS

## What Separates a Good Task From a Bad One

A bad task describes an area. A good task describes a delta and its boundary.

The difference is almost entirely in five things:

1. **The delta is explicit** — current behavior and desired behavior are both stated, so the reader doesn't have to infer the change.
2. **The real code is named** — actual functions, types, and files, including which existing helper to reuse instead of writing a second one.
3. **Out of scope is specific** — it names the adjacent thing a reasonable person would touch and shouldn't.
4. **The criteria are verifiable** — including what must *keep* working, and what the implementer must *not* do.
5. **Tests and docs are criteria, not follow-up** — if they aren't in the list, they don't happen.

Everything below exists to produce those five.

## Step 1: Gather and Preserve the Source

Pull in whatever exists:

- **File path** — read it
- **Issue/PR URL** — `gh issue view <n> --repo <owner/repo>`, or `gh api` for comments
- **Jira key** — fetch it via the `acli` skill if available
- **Pasted transcript** — use it as-is
- **Nothing** — use the conversation; if the target is unclear, ask before anything else

**Keep the raw source verbatim.** Do not summarize away the reporter's own words — the phrasing often carries the reproduction steps. It goes in the finished task under Source, collapsed if the tracker supports it.

Note the date. A task that records when its decisions were made is a task you can trust six weeks later.

## Step 2: Ground It in the Real Thing

This is the step that makes the task worth writing. Do it before asking any questions, because half your questions will answer themselves.

**In a codebase:**

Find the actual code the work touches. Grep for the symptom, the feature name, the error string, the UI label. Read the functions you find — do not stop at the grep hit.

Then answer, from what you read:

- Which functions, types, and files does this change touch? Name them exactly.
- What do they do *today*? State the mechanism, not the intent.
- **Does something already solve part of this?** A normalizer, a validator, a hook, a fixture, a similar handler two directories over. This is the single highest-value find — it turns "write a thing" into "call the thing that exists," and it prevents a second parallel implementation.
- What test files sit beside this code, and what do they already cover? A criterion that says "add tests" is worthless; "table-driven tests beside the evaluator covering X, Y, and unchanged-ASCII" is not.
- What breaks if this changes? Callers, migrations, API contracts, cached data.
- Where is this documented?

**Outside a codebase** (a process change, an ops task, a docs task), the same questions apply to different surfaces: which systems, documents, dashboards, or teams the work touches; what exists that already does part of it; how anyone would tell it worked. Keep the section, rename it Key Surfaces.

**Never name a function you have not read.** A plausible-sounding symbol that doesn't exist is worse than no reference at all — it sends the implementer looking for something that was never there and quietly teaches them not to trust the rest of the task.

## Step 3: Grill

Now interrogate — the requester, and yourself. Ask everything at once; don't drip questions across five turns.

**Do not ask what Step 2 already answered.** Do not ask what has an obvious default — pick it, and list it as an assumption for them to overrule.

Work through these. Skip what doesn't apply:

**The delta**
- What exactly happens today? If you can't state it at the mechanism level, you don't understand it yet — go back to Step 2.
- What should happen instead? What's the observable difference?
- How do you reproduce it? Which inputs, which state?

**The boundary**
- What's the adjacent thing that stays untouched? Name it.
- What currently works that must keep working? List the specific behaviors, not "don't break anything."
- Is any of this a breaking change to an API, a schema, or stored data?

**The unknowns**
- What should happen when the data isn't there — empty, malformed, missing, an older server version that doesn't support this?
- **Is a plausible guess acceptable, or must it fail visibly?** Get this answered explicitly. Unresolved, it is the single most common source of code that reports success while doing nothing.
- Concurrency, retries, a restart mid-flight — does any of that matter here?

**The proof**
- How does the implementer show this works? What external surface can be driven — an HTTP response, a table row, rendered output?
- Can it be verified automatically, or does it need a human looking at a real thing? Say which.
- What existing fixtures or harnesses should be reused?

**The delivery**
- One PR, or several working slices? If several, what's in each, and what order?
- Blocked by anything? Does it ship after something else?
- What user-facing docs change?

**The judgment**
- Which parts need taste or product judgment rather than execution?
- Which decisions are already made, and by whom?

Present unresolved items as a short numbered list. Then stop and wait.

**Decisions come from the requester, not from you.** The finished task states implementation decisions as settled, which only works if they were actually settled. Anything you decided yourself is labeled an assumption until they confirm it. Never launder your own guess into the task as though it were established.

## Step 4: Size It

Pick the smallest tier that holds the work. Padding a one-line fix into the full template is how tickets become unreadable.

| Tier | When | Sections |
|------|------|----------|
| **Brief** | A bug or contained change. One reviewer, one sitting. The mechanism is understood. | Summary, Current/Desired behavior, Key interfaces, Criteria, Out of scope |
| **Standard** | A feature touching a few surfaces. Still one PR. Decisions fit inside the criteria. | What to build, Criteria (compound), Key interfaces, Out of scope, Blocked by (not in Jira) |
| **Full** | New capability across backend, frontend, storage, and docs. Multiple slices. Decisions need their own space. | Delivery, Problem, Solution, User stories, Implementation decisions, Testing decisions, Out of scope |

**Signals you need the next tier up:** the criteria list passes ten items; two criteria contradict unless you explain a decision; the work can't land in one reviewable PR; you're writing "and also" a lot.

**Signals you're over-tiering:** the user stories all restate one sentence; Implementation Decisions is one bullet; the Delivery section describes a single commit.

## Step 5: Write It

**Title.** State the symptom and its consequence, not the area. `Path autocomplete swallows Enter, so a path field can never be confirmed from the keyboard` beats `Fix path autocomplete`. If the tracker has a convention — conventional-commit prefixes, a Jira key format — look at the neighbors and match it.

### Tier 1 — Brief

```markdown
# {Symptom, and what it costs the user}

**Category:** bug | enhancement | refactor | perf | chore
**Summary:** {One sentence: the mechanism, then the resulting failure.}

## Current behavior

{What the code does today. Name the real functions. Explain why that
produces the symptom — the causal chain, not a restatement of the title.}

## Desired behavior

{The end state, observable. Include the edge cases that must hold and the
behavior that must survive unchanged.}

## Key interfaces

- `thing()` in `path/to/file.ext` — {what it does now, what it must do}
- `existingHelper()` in `path/to/other.ext` — {already used by X and Y;
  reuse it rather than adding a second implementation}

## Acceptance criteria

- [ ] {Behavioral: the new thing works, stated as something you can run}
- [ ] {Edge case}
- [ ] {Preservation: these specific existing behaviors are unchanged}
- [ ] {Negative: what must not be done}
- [ ] {Tests: where they live and what cases they cover}
- [ ] {Docs: which document says what}

## Out of scope

- {The adjacent thing that stays as it is}
- {The tempting refactor that isn't this task}

## Source

{link or reference} — {date}

<details>
<summary>Original report</summary>

{verbatim}

</details>
```

### Tier 2 — Standard

```markdown
# {What this adds, in the user's terms}

## What to build

{One paragraph. What the user gets, and any hard requirement — a version
floor, a dependency, a platform.}

## Acceptance criteria

- [ ] {Compound is fine here: the behavior, plus its constraint, plus what
      it must not do. Each criterion carries a whole decision.}
- [ ] {Reuse: which existing hooks, fixtures, or components this goes through}
- [ ] {Unsupported/degraded case: what the user sees, and that nothing is
      fabricated when the real value is unavailable}
- [ ] {Verification, including whether a human must look at a real instance}
- [ ] {Docs and contracts updated in the same PR}

## Key interfaces

- `{symbol}` in `{path}` — {role in this change}

## Out of scope

- {Boundary}

## Blocked by

{Link, and delivery order relative to other work. Omit if nothing blocks it,
and omit it in Jira — there the order lives in issue links (see Step 6).}

## Source

{link} — {date}
```

### Tier 3 — Full

```markdown
# {feat|fix}({area}): {what it adds}

## Delivery

{Branch, target, whether it stacks. Then the slices — each one a working,
committed increment, with what's in it and what it must not touch. If the
implementer should announce which slice they're in, say so.}

## Problem Statement

{The real-world pain, in the user's world. No code. What they do today
instead, and why it's bad.}

## Solution

{One paragraph of what the system does once this ships. Link any glossary
or decision record.}

## User Stories

1. As a {role}, I want {capability}, so that {outcome}.

{Be exhaustive. This is where the edge cases live — the empty state, the
unsupported instance, the restart, the second user, the other platform.
Each story is one testable capability. If two stories are the same
sentence twice, cut one.}

## Implementation Decisions

### {Area}

- {A decision, stated as settled. Include the reasoning only where the
  next person would otherwise reverse it.}
- {What not to do, and why: "do not add a second definition of X",
  "do not wrap this in an interface yet".}

## Testing Decisions

- {What a good test looks like here — which surface it drives, what it
  asserts. State what is not asserted on.}
- {The specific cases, per layer.}
- {What can only be proven by a human on real data, and that the feature
  isn't done until that happens.}

## Out of Scope

- {Each boundary, specifically. This section is long in a good full task.}

## Further Notes

- {Date the decisions were made and where they're recorded.}
- {Prerequisite versions or releases and their status.}
```

## Step 6: Deliver It

If decisions are still open, list them and don't file.

**Always print the markdown first.** Then route it based on where you are — check, don't assume:

- **Jira in play** (a project key in the source, `acli` available) — offer to create the work item using the `acli` skill. Confirm project, type, and any required fields before creating. Express ordering and dependencies as issue links (Blocks, or the project's equivalent), not as a "Blocked by" section or "blocks X" prose in the body — links show on the board and stay correct when tickets move, body text doesn't. Naming a sibling ticket in the body is still fine where it carries meaning ("the tests from WHERE-123 pass unmodified"). When filing several related tickets, create them first, then write the bodies with the real keys and add the links.
- **GitHub repo with `gh` available** — offer `gh issue create`. Suggest labels that already exist in the repo (`gh label list`). Don't invent labels.
- **Feeding an engineering loop** — write it to a file and hand the path to `/ghb:sloop`, `/ghb:coop`, or an implementation session.
- **None of the above** — the markdown is the deliverable.

Creating a ticket is outward-facing and hard to take back. Get explicit approval for the specific destination before you file, every time — approval to write the task is not approval to publish it.

## Failure Modes to Avoid

**Criteria that can't fail.** "Handle errors gracefully." "The feature works as expected." "Improve performance." If you can't say what you'd run to check it, it isn't a criterion.

**Criteria that restate the title.** If item one is the title as a checkbox, delete it.

**An empty Out of Scope.** Every task has one. If you can't name the adjacent thing, you haven't looked at the code around it.

**Fabricated interfaces.** Named a function you didn't read? Remove it.

**Laundered guesses.** A decision you made, written as though the requester made it.

**Implementation prose as requirements.** Under Brief and Standard, say what must be true, not how to write it. Full-tier Implementation Decisions is the one place the how belongs, and only for decisions that are actually made.

**Skipping the grill because the request seemed clear.** The requests that seem clearest are the ones carrying an unstated assumption.
