---
id: review-summary
description: "Morning PR review summary — find PRs awaiting review, adversarial review each, send a Slack DM"
invocation:
  byModel: false
---

# Review Summary

Fetch all open PRs where you're a requested reviewer, run an adversarial code review on each, clean up AI-generated descriptions, and present a summary.

## Usage

```
/review-summary [--slack] [--org=<org>]
```

$ARGUMENTS

If `--slack` is passed, send the summary as a Slack DM instead of outputting it here.

If `--org=<org>` is passed, scope the search to that GitHub org (adds `--owner=<org>` to the `gh search prs` call). Otherwise, search across all orgs where you're a requested reviewer.

## Step 1: Find PRs Awaiting Review

```bash
gh search prs --review-requested=@me --state=open --json number,title,url,repository,author
```

Add `--owner=<org>` if `--org` was passed.

If no PRs are found, say "No PRs waiting for your review." and stop.

### Filter to directly-assigned PRs

`--review-requested=@me` includes team-assigned PRs. Filter them out: for each PR, run `gh pr view {number} -R {owner/repo} --json reviewRequests` and only keep PRs where your user login appears directly (not just via a team). Drop any PRs that are only team-assigned.

### Fetch PR details

For each remaining PR, fetch the body and stats:

```bash
gh pr view {number} -R {owner/repo} --json body,additions,deletions
```

Batch these calls in parallel where possible.

## Step 2: Triage

Split the PRs into two groups:

1. **Review** — PRs authored by humans that need adversarial review
2. **Automated** — Dependabot, Renovate, or other bot PRs. These get listed at the end without a full review.

Skip any PRs authored by you entirely — don't include them in the output at all.

## Step 3: For Each PR in the Review Group

### Fetch the diff

```bash
gh pr diff {number} -R {owner/repo}
```

### Adversarial code review

Spawn the `adversarial-code-reviewer` agent for each PR with the diff as input. Collect the verdict (Clean / Needs Review / Contaminated) and key findings.

### Un-AI the description

Run `/un-ai` on the PR body. If the description is clearly human-written, note that and move on. If it's AI-generated, include the cleaned-up version in the summary.

## Step 4: Compile Summary

Order reviewed PRs by verdict: Contaminated first, then Needs Review, then Clean.

For each reviewed PR:

```
{PR title}
Repo: {org/repo} | Author: {author} | +{additions} / -{deletions}
Link: {url}

What it does: {un-ai'd description, 1-3 sentences}

Review findings:
{Key findings from adversarial review — Red Flags and Suspicions only. Brief but specific.}

Verdict: {Clean | Needs Review | Contaminated}
```

For Clean PRs with no findings, use a one-line summary instead.

At the end, list automated PRs under a separate heading with title, repo, author, and link — no review needed, just awareness.

## Step 5: Output

If `--slack` was passed, send the summary as a Slack DM to the current user. Use Slack mrkdwn formatting (`*bold*`, `_italic_`, `` `code` ``). Do NOT use `**bold**` or `---` — Slack rejects them.

Otherwise, output the summary directly.

## Guidelines

- **Skip your own PRs entirely.** Don't include them in the output.
- **Don't pad reviews.** If a PR is small and clean, say so in one line.
- **Be concrete.** "The import on line 12 doesn't resolve" is useful. "This might have issues" is not.
- **Bot PRs go at the end.** Dependabot, Renovate, etc. get listed for awareness but don't need adversarial review.
