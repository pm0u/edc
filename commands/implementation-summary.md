---
description: Generate a meaningful summary of what was built and why — not just a diff recap
---

# Implementation Summary

Write a summary of recent implementation work that captures intent, decisions, and context — the kind of description you'd want on a PR or handoff doc. Not a diff listing.

## Usage

```
/implementation-summary [commit-range or branch]
```

$ARGUMENTS

## Step 1: Gather the Changes

If a commit range or branch was provided, use it. Otherwise, infer from context:

```bash
# If on a feature branch, diff against main/master
BASE=$(git merge-base HEAD main 2>/dev/null || git merge-base HEAD master 2>/dev/null)
git log --oneline "$BASE"..HEAD
git diff "$BASE"..HEAD --stat
```

Read the full diff and the changed files in context (not just the diff hunks — read surrounding code to understand what the changes plug into).

## Step 2: Understand Intent

Look for signals about what the work was trying to accomplish:

- Commit messages (especially the first one — often states the goal)
- Any referenced issue numbers or JIRA IDs in commits
- Planning artifacts in the repo (PLAN.md, SPEC.md, .planning/, .trak/, .vq/)
- The shape of the changes — are they adding a feature, fixing a bug, refactoring, migrating?

## Step 3: Identify Key Decisions

These are the things a reviewer or future maintainer needs to know:

- **Approach chosen** — Why this approach over alternatives? If the diff shows a non-obvious pattern, explain the reasoning.
- **Tradeoffs made** — What was sacrificed for what? Speed vs correctness, simplicity vs flexibility, etc.
- **Scope boundaries** — What was deliberately left out or deferred? What's the "not in this PR" list?
- **Surprises encountered** — Did the implementation reveal something unexpected about the codebase, API, or requirements?

## Step 4: Write the Summary

Structure:

```markdown
## What

{1-2 sentences: what was built/changed and the user-facing or system-facing effect}

## Why

{1-2 sentences: the motivation — what problem this solves or what goal it advances}

## How

{Brief description of the approach. Not a file-by-file walkthrough — describe the strategy.
Mention key architectural decisions and why they were made.}

## Notable Decisions

{Bulleted list of non-obvious choices with brief rationale for each}

## What's Not Here

{Anything deliberately scoped out, deferred, or left as follow-up work}
```

## Guidelines

- **Lead with impact, not mechanics.** "Adds offline sync for saved trails" not "Modified TrailStore.ts, added SyncManager class, updated ServiceWorker."
- **Explain the non-obvious.** If a reviewer would look at a change and think "why did they do it this way?", that's what belongs in the summary.
- **Be honest about tradeoffs.** If something is a hack, say so and say why it was the right call anyway.
- **Keep it short.** A good summary is 10-20 lines. If you need more, the PR is probably too big.
- **Skip the obvious.** Don't explain what a rename does or that a new file was created. Focus on intent and decisions.
