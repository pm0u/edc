---
name: distill-reviews
description: Distill a sprint of merged-PR review feedback (Copilot and human) into a repo's agent and Copilot review instructions, synthesized under a size budget and proposed as a PR — plus any live bugs the reviews surfaced
---

# Distill Reviews

Review threads are where a team learns the gotchas — a race in an internal API, a flag
that reads `false` until the client loads, a retry that duplicates writes. The fix lands
in the PR and the lesson is gone. This skill mines a window of merged PRs, distills what's
worth keeping, folds it into the files agents and Copilot actually load, and proposes the
change as a PR the team reviews line by line.

You are the coordinator. Gatherers extract, a validator checks bugs, an integrator
synthesizes; you run the pipeline, reconcile, check routing, and assemble the result.

## Usage

```
/distill-reviews [<repo path or owner/name>] [--since=YYYY-MM-DD] [--open-pr]
```

$ARGUMENTS

Default is a **dry run**: everything is written to a scratch directory and nothing leaves
the machine. `--open-pr` adds the PR step at the end, which still asks for confirmation.

Scripts live in `${CLAUDE_PLUGIN_ROOT}/skills/distill-reviews/scripts/`.

## Step 1: Preflight

1. Resolve the repo: a local path, or find the checkout for `owner/name`. Get
   `owner/name` from `gh repo view --json nameWithOwner`, and the default branch from
   `git symbolic-ref refs/remotes/origin/HEAD`.
2. `git fetch origin` and use `origin/<default>` as **the ref**. Every agent reads code only
   through the ref. Local checkouts are often months stale, and a stale read once made
   removed code look present.
3. Pick a scratch directory (your session scratchpad if you have one) as `$OUT`.

## Step 2: Window

- If `--since` was given, use it.
- Otherwise find the last merged PR labeled `distill-reviews` and use its merge date.
- Otherwise default to 14 days ago.

If a previous `distill-reviews` PR exists, fetch its review comments too
(`gh api repos/<o>/<r>/pulls/<n>/comments`) and save them as `$OUT/prior-feedback.json`.
Entries the team rejected or rewrote there must not be re-proposed in the same form.

## Step 3: Fetch and annotate

```bash
fetch_threads.sh <owner/name> <since> $OUT/prs
annotate_threads.sh $OUT/prs $OUT/thread-evidence.json
```

The fetch excludes earlier `distill-reviews` PRs and anonymizes reviewers to
`copilot | bot | pr-author | human-reviewer`. Evidence like "did the code change after
this comment" is computed here, by script — gatherers asked to infer it invented data.

If there are no threads and no substantive review bodies, report that and stop.

## Step 4: Map the knowledge files

Before spawning anything, build `$OUT/knowledge-map.md` from the ref: every `CLAUDE.md`,
`AGENTS.md`, `.claude/rules/**`, `.github/copilot-instructions.md`,
`.github/instructions/**`, and any docs those point to. For each, note size and **when it
loads** — session start, effectively always (broad globs), on demand, not auto-loaded
(nested `AGENTS.md` without a sibling `CLAUDE.md`), or Copilot review. Check `git ls-tree`
mode `120000` for symlinks. The integrator routes by this map, and loading gaps you find
here become suggestions in the PR.

## Step 5: Gather (parallel)

Split PRs into batches of roughly 10–15 PRs or 25 threads. Spawn one
`ghb:review-gatherer` per batch, all in one message, each given its batch file, the repo
path, the ref, and `$OUT/candidates/batch-N.json`.

Collect the replies. Note any "possible secret" reports — never repeat the value; tell the
user so it can be rotated. Collect every `live-bug` candidate and every bug-like aside a
gatherer mentioned outside its candidates (asides have turned out to be real).

## Step 6: Validate and integrate (parallel)

Spawn both in one message:

- **`ghb:bug-validator`** with the bug claims, candidate paths, repo, ref, and
  `$OUT/bug-validation.md`. Skip if there are no claims.
- **`ghb:knowledge-integrator`** with the candidates, `thread-evidence.json`, `prs/`,
  `knowledge-map.md`, `prior-feedback.json` if present, repo, ref, and `$OUT` as its
  output directory.

## Step 7: Reconcile bugs

Compare the validator's verdicts with the integrator's LIVE-BUG readings in its ledger.
Where they disagree on the verdict or the attribution ("PR X introduced this" vs "already
broken before"), check the specific disputed point yourself in the code at the ref, or
spawn a second `ghb:bug-validator` scoped to just that question. Neither agent alone has
been reliable on every claim; the disagreements are where the errors were.

Final bug list: CONFIRMED and LIKELY go in the PR body. UNCLEAR goes in only with what
would settle it. NOT A BUG and INTENTIONAL are dropped, unless they expose a misleading
comment or doc worth a one-line mention.

## Step 8: Check routing and budget

Read `proposal/changes.diff` against the knowledge map:

- Every line added to a session-start or effectively-always file must have a justification
  in the ledger for why it applies to most sessions. If it doesn't hold up, send it back to
  the integrator (SendMessage) to route narrower. This is the integrator's most common miss.
- Confirm the budget: ≤ 25 net lines across existing files, ≤ 3 new files of ≤ 20 lines,
  Copilot files ≤ 4000 characters.
- Spot-check three surviving entries against their source threads.

## Step 9: Assemble the PR body

Write `$OUT/pr-body.md`. Reviewers need context for every change, but the per-change
reasoning lives in inline review comments (`rationale.json`), so the body stays a summary:

1. One paragraph: what this PR is, the window, how many PRs and threads were read.
2. Per file, one line on what changed.
3. **Possible bugs found** — per bug: file:line, the scenario, impact, confidence, the PR
   it came from, suggested fix. Say that each needs a ticket or a "won't fix".
4. **Suggestions (not applied)** — from `suggestions.md` and the knowledge map.
5. How to review: reply on an inline comment to reject or reword an entry; the next run
   reads those replies.

No reviewer usernames. If the user has a writing or voice guide, follow it.

## Step 10: Report

Tell the user: candidates → survivors by action, files changed with net line deltas, the
top learnings, the final bug verdicts (with any reconcile corrections), suggestions, any
secrets to rotate, and where everything is in `$OUT`. For a dry run, stop here.

## Step 11: Open the PR (`--open-pr` only)

This publishes to the team. Confirm with the user first, every time, and ask for anything
their conventions need (ticket ID, branch and commit format from their CLAUDE.md).

1. Create a worktree from the ref, copy the `proposal/` files in, commit, push.
2. `gh pr create --label distill-reviews` with `pr-body.md`. If the label doesn't exist,
   ask before creating it.
3. Post `rationale.json` as one review with inline comments:
   `gh api repos/<o>/<r>/pulls/<n>/reviews` with `event: COMMENT` and a `comments` array of
   `{path, line, side: "RIGHT", body}`.
4. Return the PR link.

## Not yet built

- Reaction and acceptance signals on Copilot comments (thumbs, committed suggestions) as
  evidence of reviewer accuracy.
- A `#learn` marker reviewers can put in a comment so the integrator must handle it — it can
  merge or reword, but dropping one requires a stated reason in the PR body.
- Scheduling (per sprint, per repo).
