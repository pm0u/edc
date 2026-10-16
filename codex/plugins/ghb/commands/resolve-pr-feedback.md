# Resolve PR Feedback

Address unresolved review feedback on a pull request. Fetches all open review threads,
categorizes them by reviewer, **tiers the batch** so the mechanical fixes get handled for the
operator and the ones that would move their model of the code come back to them, then works
through each comment — making code changes where warranted, replying to explain decisions, and
resolving threads.

The tiering is deliberately light. It uses the classification rubric at
**`../docs/tiers-core.md`** with a review thread as the unit, and applies its
batching rule — classify the set once, pull out the exceptions — rather than sorting every
comment individually. No slices, no shells, no loop; that machinery belongs to
[`$coop`](../docs/coop.md), and a follow-up round on a review is exactly the case it's too
heavy for.

## Usage

```
$resolve-pr-feedback [PR_NUMBER]
```

If no PR number is provided, detects from the current branch.

Use the user's skill invocation and conversation context as the input, including any flags.

## Step 1: Identify the PR

```bash
# Use provided PR number, or detect from current branch
gh pr view --json number,url,headRefName -q '"\(.number) \(.url) \(.headRefName)"'
```

## Step 2: Fetch All Unresolved Review Threads

Query unresolved threads with full comment content:

```bash
# Replace OWNER, REPO, PR_NUMBER with actual inline values — do NOT use $variables
gh api graphql -f query='
query {
  repository(owner: "OWNER", name: "REPO") {
    pullRequest(number: PR_NUMBER) {
      reviewThreads(first: 100) {
        nodes {
          id
          isResolved
          path
          line
          comments(first: 10) {
            nodes {
              author { login }
              body
              createdAt
            }
          }
        }
      }
    }
  }
}'
```

## Step 3: Categorize and Triage

For each unresolved thread, determine:

1. **Who left it** — human reviewer, Copilot, CodeRabbit, other bot
2. **What it asks for** — code change, explanation, question, nitpick, style suggestion
3. **Priority:**
   - **Address** — Legitimate issue or reasonable request. Make the change.
   - **Discuss** — Disagreement or tradeoff. Reply with reasoning.
   - **Acknowledge** — Minor nitpick or style preference. Reply briefly, resolve.

## Step 3b: Route the Address set — who fixes it

Priority is about the *comment's* intent. This is about *the work* the fix is, and it decides
whether you fix it or hand it back. They're orthogonal: run this over the **Address** set only.

Read `../docs/tiers-core.md` (using the available file-reading tool) and apply the batching rule:
**assume the batch is Race, then pull out the exceptions.** Do not classify comment by comment.

A thread is an exception — it comes back to the operator, you do **not** fix it — when
addressing it means any of:

- **The fix bends the code** — it changes an invariant, restructures control flow, moves a
  contract or signature callers depend on, or turns on a judgment nobody pinned down. (The
  rubric's [Bends](../docs/tiers-core.md#routing-a-fix--by-the-work-not-by-the-unit) case;
  genuinely unsure is a Bend.)
- **The comment found a misunderstanding, not a defect** — the reviewer is pointing out that
  the code's intent, not its execution, is wrong. A defect is mechanical. A misunderstanding
  means someone's model of the system was wrong, and quietly patching it hands the operator
  working code and no model.
- **The blast radius is bigger than the comment looks** — a wrong fix here fails silently or
  corrupts data rather than throwing loudly, or many callers depend on the exact behavior.

Everything left is the Race batch: renames, extractions, an added guard for a case already
known to be possible, a missing test, a typo, a lint or type fix, a suggestion that lands at an
existing extension point without moving anything. Fix those in one pass (Step 4).

**Report the split before you start fixing.** One line per exception — thread, file:line, and
which trigger fired. The operator decides whether to take them, hand any back to you anyway, or
tell you to proceed on all of it. Don't wait on a reply to start the Race batch; the two are
independent.

If the batch is *mostly* exceptions, say so — a review round where most fixes bend is a signal
about the change itself, not a routing problem. That's the case worth a `$coop` run rather
than a feedback pass.

## Step 4: Address Each Thread

Work through **the Race batch** in file order (to minimize context switching). Threads routed
to the operator in Step 3b are not yours to fix — reply on those only to acknowledge that
they're with the operator, and leave them unresolved.

If a thread you started as part of the Race batch turns out to bend once you're in the code,
**stop and add it to the exception list** instead of finishing it. Same rule the loop's build
agents follow: don't reshape code the operator is supposed to understand in order to make a
fix fit.

### For code change requests:
1. Read the file and understand the context around the commented line
2. Make the change if it's an improvement
3. Reply to the thread confirming what was changed

### For questions or explanations:
1. Read the relevant code
2. Reply with a clear, concise answer
3. If the question reveals a real issue, fix it too

### For disagreements:
1. Read the code and the suggestion carefully
2. If the reviewer is right, make the change and say so
3. If you disagree, reply with specific reasoning (not "I prefer it this way" — explain the tradeoff)

### For bot feedback (Copilot, CodeRabbit):
1. Evaluate each suggestion on merit — bots can be right or wrong
2. Apply suggestions that improve the code
3. For false positives or irrelevant suggestions, reply briefly explaining why it doesn't apply

## Step 5: Resolve Threads

After addressing a thread (code change + reply, or reply only), resolve it. **Threads routed to
the operator stay unresolved** — resolving one would close a thread on work that hasn't happened.

```bash
# Replace THREAD_ID with actual value
gh api graphql -f query='
mutation {
  resolveReviewThread(input: { threadId: "THREAD_ID" }) {
    thread { isResolved }
  }
}'
```

## Step 6: Verify and Report

Re-query to confirm all threads are resolved:

```bash
gh api graphql -f query='
query {
  repository(owner: "OWNER", name: "REPO") {
    pullRequest(number: PR_NUMBER) {
      reviewThreads(first: 100) {
        nodes {
          isResolved
          comments(first: 1) {
            nodes {
              author { login }
            }
          }
        }
      }
    }
  }
}' | jq '{
  total: [.data.repository.pullRequest.reviewThreads.nodes[]] | length,
  resolved: [.data.repository.pullRequest.reviewThreads.nodes[] | select(.isResolved)] | length,
  remaining: [.data.repository.pullRequest.reviewThreads.nodes[] | select(.isResolved == false)] | length
}'
```

Output a summary:

```
## PR #123 Feedback Resolution

### Handled for you
- 3 code changes made (files: auth.ts, router.ts, config.ts)
- 2 questions answered
- 1 suggestion declined with reasoning

### Back to you (2)
- `auth.ts:88` — reviewer is right that the retry changes the idempotency guarantee. Bends.
- `router.ts:14` — the comment says the guard is in the wrong layer. That's a misunderstanding
  of where the check belongs, not a defect.

### Status
- 6/8 threads resolved, 2 open pending your fixes
- Ready for re-review once those land
```

List every thread that remains unresolved with the reason — routed to the operator, or couldn't
be addressed. Those are different reasons and shouldn't read the same.

## Guidelines

- **Don't blindly accept everything.** Reviewer feedback is input, not commands. Push back when you have good reason.
- **Route before you fix, and report the split.** The point of the tiering step is that the
  operator sees which fixes were theirs *before* the code moves, not after. Fixing everything
  and mentioning it in the summary defeats it.
- **Tier the batch, not the comment.** Classifying a dozen threads one at a time costs more
  than the decision is worth. Assume Race, hunt for the exceptions.
- **Don't dismiss bot feedback.** Copilot and CodeRabbit catch real issues. Evaluate each on merit.
- **Keep replies concise.** Reviewers don't want essays. One sentence for acknowledgments, a short paragraph for explanations.
- **Batch related changes.** If multiple threads touch the same file, make all changes before moving to the next file.
- **Commit changes as you go.** Don't accumulate a massive uncommitted diff. Group logically related fixes into commits.
