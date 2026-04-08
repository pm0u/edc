---
description: Trace how data or execution flows through a system — from entry point to outcome
---

# Trace Flow

Follow a piece of data or an execution path through the codebase from entry to exit. Produce a clear narrative and optionally a structured diagram of how things connect.

## Usage

```
/trace-flow [starting-point-or-question]
```

Examples:
- `/trace-flow src/api/trails.ts` — trace from this entry point
- `/trace-flow "how does a search query get results?"` — trace a conceptual flow
- `/trace-flow "what happens when a user logs in?"` — trace an end-to-end flow

$ARGUMENTS

## Step 1: Identify the Flow

If given a file, start there and follow the data/execution forward and backward. If given a question, find the entry point by searching the codebase.

```bash
# Find entry points
grep -r "router\.\|app\.\|export\s" --include="*.ts" --include="*.js" -l src/ | head -20
```

Determine what kind of flow this is:

- **Request flow** — HTTP/GraphQL request → middleware → handler → service → data → response
- **Data flow** — User input → validation → transformation → storage → retrieval → display
- **Event flow** — Trigger → event → handler(s) → side effects
- **Build/deploy flow** — Source → transform → bundle → deploy
- **State flow** — Action → reducer/store → derived state → UI update

## Step 2: Walk the Chain

Follow the flow through each layer. At each hop, note:

1. **What enters** — the input shape, type, relevant fields
2. **What happens** — transformation, validation, branching, side effects
3. **What exits** — the output shape, what changed
4. **Where it goes next** — the next function/service/component in the chain

Read the actual code. Don't guess based on file names.

## Step 3: Identify Boundaries

Mark where the flow crosses significant boundaries:

- Client ↔ Server
- Service ↔ Service
- Application code ↔ Framework/library
- Sync ↔ Async
- Your code ↔ Third-party API

These boundaries are where bugs live and where understanding breaks down.

## Step 4: Write the Trace

```markdown
# Flow: {description}

## Summary

{2-3 sentences: what this flow does end-to-end, who/what triggers it, what the final outcome is}

## Path

### 1. {Layer/Step Name}

**File:** `path/to/file.ts` (lines X-Y)
**Input:** {what arrives here}
**Action:** {what happens — be specific about transformations, validations, branching}
**Output:** {what leaves}
**Next:** → {where it goes}

### 2. {Next Layer/Step}
...

## Key Observations

{Anything notable about this flow:}
- {Surprising indirection or complexity}
- {Error handling gaps}
- {Performance implications}
- {Places where the flow could break}

## Boundaries Crossed

| From | To | Mechanism | Notes |
|------|----|-----------|-------|
| ... | ... | ... | ... |
```

## Guidelines

- **Follow the code, not the abstractions.** Framework magic hides real behavior. If a decorator or middleware does something important, trace into it.
- **Stop at a reasonable depth.** Don't trace into standard library internals or well-known framework code. Stop where the behavior becomes predictable.
- **Note the surprises.** If the flow does something you wouldn't expect from reading the entry point, call it out. Those are the things that trip people up.
- **Include error paths if they matter.** If the question is "how does X work?" the happy path is enough. If the question is "why does X break?" trace the error paths too.
