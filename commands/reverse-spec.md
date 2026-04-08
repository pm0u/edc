---
description: Derive a spec from existing code — document what it actually does, not what someone intended
---

# Reverse Spec

Read existing code and produce a spec that describes its actual behavior. Useful before refactoring, when onboarding to unfamiliar code, or when a feature exists but was never formally specified.

## Usage

```
/reverse-spec [path]
```

Path can be a file, directory, or module. If omitted, asks what to document.

$ARGUMENTS

## Step 1: Read the Code

If given a directory, start by understanding the structure:

```bash
find <path> -type f -not -path '*/node_modules/*' -not -path '*/.git/*' | head -40
```

Read entry points first — exports, route handlers, main files, index files. Then follow the dependency chain inward to understand what the module actually does.

Don't stop at the top-level abstraction. Read into the functions, the branching logic, the error handling. The spec should reflect real behavior, not what the function names suggest.

## Step 2: Identify the Boundaries

Determine:

- **What triggers this code?** — Route, event, import, schedule, user action
- **What does it depend on?** — External services, databases, other modules, config, environment
- **What does it produce?** — Responses, side effects, state changes, files, events
- **What does it assume?** — Auth state, data shape, preconditions that aren't validated

## Step 3: Extract Behaviors

For each meaningful behavior the code implements, describe it as an acceptance criterion. Derive these from what the code actually does, including:

- Happy path behavior
- Error handling and edge cases that are explicitly coded
- Validation rules
- Default values and fallback behavior
- Side effects (logging, analytics, cache updates, notifications)

**Be honest about what's missing.** If the code has no error handling for a failure mode, note that as a gap — don't invent criteria the code doesn't satisfy.

## Step 4: Note the Gaps

Things the code probably should handle but doesn't:

- Unvalidated inputs
- Unhandled error cases
- Missing edge cases
- Silent failures (empty catches, swallowed errors)
- Assumptions that aren't enforced

These aren't criticism — they're useful context for whoever works on this next.

## Step 5: Write the Spec

```markdown
# {Module/Feature Name}

## Purpose

{What this code does, in one sentence. Describe the behavior, not the implementation.}

## Entry Points

- `path/to/file.ts:functionName` — {what triggers it, what it does}

## Current Behavior

### {Behavior Group 1}

- [ ] {What it does — stated as a testable criterion}
- [ ] {Another behavior}

### {Behavior Group 2}

- [ ] ...

## Dependencies

- {Service, module, or external system it relies on}

## Implicit Assumptions

- {Things the code assumes but doesn't validate}

## Gaps

- {Behaviors that are missing or incomplete}
- {Error cases not handled}
- {Edge cases not covered}
```

## Guidelines

- **Describe behavior, not implementation.** "Returns a 404 when the trail ID doesn't exist" not "Calls `findById` and checks for null." The spec should survive a rewrite.
- **Include the weird stuff.** If the code has a strange special case, a hardcoded value, or a workaround — document it. Those are the things that get lost in refactors.
- **Distinguish intentional from accidental.** If a behavior looks like a bug vs. a deliberate choice, flag it as uncertain rather than asserting either way.
- **Group by user-facing behavior, not by file.** Organize the spec around what the feature does, not how the code is structured. Files can be reorganized; behaviors are what matter.
- **Don't over-document internals.** Private helper functions, utility methods, and implementation details don't belong in the spec unless they encode important business logic.
