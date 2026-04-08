---
description: Adversarial review of a plan — poke holes, challenge assumptions, surface risks
---

# Review Plan

Run an adversarial review against a plan, design doc, or implementation strategy.

## Usage

```
/review-plan [path-or-description]
```

$ARGUMENTS

## Workflow

1. If a file path was provided, read it
2. If no arguments were provided, check for common plan files in the current project:
   - `PLAN.md`, `**/PLAN.md`
   - `.planning/**/PLAN.md`
   - Any recently created design doc or proposal
3. If multiple candidates exist, ask which one to review
4. Spawn the `adversarial-plan-reviewer` agent with the plan content and any referenced codebase files
5. Present the review to the user
