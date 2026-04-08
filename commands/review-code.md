---
description: Adversarial review of code changes — hunt for AI-generated failure modes
---

# Review Code

Run an adversarial code review against recent changes. Specifically targets AI-generated failure patterns: reckless completion, fabrication, unverified assumptions, scope violations.

## Usage

```
/review-code [commit-range, branch, or file paths]
```

$ARGUMENTS

## Workflow

1. If a commit range, branch, or file paths were provided, use them as the review scope
2. If no arguments were provided, infer scope:
   - If on a feature branch, diff against main/master
   - Otherwise, review the last 1-3 commits
3. Spawn the `adversarial-code-reviewer` agent with the review scope
4. Present the review to the user
