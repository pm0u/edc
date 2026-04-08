---
description: Derive a focused spec with acceptance criteria from requirements, conversation, code, or an issue
---

# Derive Spec

Turn messy inputs — a conversation, a JIRA ticket, existing code, a verbal description — into a clean spec with concrete acceptance criteria. Captures the WHAT and the boundaries, not the HOW.

## Usage

```
/derive-spec [source]
```

Source can be a file path, issue URL, or omitted (derive from conversation context).

$ARGUMENTS

## Step 1: Gather Raw Input

Depending on what was provided:

- **File path** — Read it (could be a requirements doc, planning artifact, existing code)
- **Issue/ticket URL** — Fetch it via `gh issue view` or `gh api`
- **Nothing** — Use the current conversation context. Ask the user what they want to spec if it's not clear.
- **Existing code** — If pointed at code, derive a spec that describes what the code currently does (useful for retroactive documentation or before refactoring)

## Step 2: Extract the Core

From whatever raw input you have, identify:

1. **The goal** — What is this trying to accomplish? One sentence.
2. **The user/actor** — Who benefits from this? Who interacts with it?
3. **The trigger** — What kicks this off? User action, event, schedule, API call?
4. **The outcome** — What's different when this is done? What can the user do that they couldn't before?

## Step 3: Define Acceptance Criteria

Each criterion should be:

- **Testable** — You can write a test or manually verify it with a clear pass/fail
- **Specific** — No ambiguity about what "working" means
- **Independent** — Each criterion stands alone

Write them as "Given/When/Then" or simple declarative statements. Prefer whichever is clearer for the specific criterion.

Bad: "The search should be fast"
Good: "Search results return within 500ms for queries under 1000 results"

Bad: "Handle errors gracefully"
Good: "When the API returns 429, retry with exponential backoff up to 3 times, then surface the error to the user"

## Step 4: Identify Constraints and Boundaries

- **In scope** — What this spec covers
- **Out of scope** — What this spec explicitly does NOT cover (prevents scope creep)
- **Technical constraints** — Must use X, can't use Y, needs to work with Z
- **Non-functional requirements** — Performance, accessibility, browser support, etc. (only if relevant)

## Step 5: Write the Spec

```markdown
# {Feature/Change Name}

## Goal

{One sentence: what this accomplishes and for whom}

## Background

{2-3 sentences of context. Why does this matter? What's the current state?
Skip if obvious.}

## Acceptance Criteria

- [ ] {Criterion 1}
- [ ] {Criterion 2}
- [ ] {Criterion 3}
...

## Constraints

- {Constraint 1}
- {Constraint 2}

## Out of Scope

- {Thing that might seem in scope but isn't}
- {Another boundary}
```

## Guidelines

- **Capture intent, not implementation.** The spec says "users can filter trails by difficulty" not "add a dropdown component that queries the filter API endpoint." Let the implementer decide how.
- **Fewer criteria, more precision.** 5 sharp criteria beat 15 vague ones. Each criterion should make you think "I know exactly how to test that."
- **Ask when ambiguous.** If the source material is unclear about what "done" looks like, ask the user rather than guessing. A spec with a question mark is better than a spec with a wrong assumption.
- **Include the non-obvious.** If there's a constraint the implementer wouldn't guess (auth requirement, data format, backwards compatibility), that belongs in the spec even if it seems obvious to the person requesting it.
- **Skip ceremony for small things.** A one-line bug fix doesn't need a Background section. Scale the spec to the size of the work.
