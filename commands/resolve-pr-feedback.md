---
description: Fetch unresolved PR review comments, address each one, and resolve the threads
---

# Resolve PR Feedback

Address unresolved review feedback on a pull request. Fetches all open review threads, categorizes them by reviewer, and works through each comment — making code changes where warranted, replying to explain decisions, and resolving threads.

## Usage

```
/resolve-pr-feedback [PR_NUMBER]
```

If no PR number is provided, detects from the current branch.

$ARGUMENTS

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

## Step 4: Address Each Thread

Work through threads in file order (to minimize context switching):

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

After addressing a thread (code change + reply, or reply only), resolve it:

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

### Threads Addressed
- 3 code changes made (files: auth.ts, router.ts, config.ts)
- 2 questions answered
- 1 suggestion declined with reasoning

### Status
- 6/6 threads resolved
- Ready for re-review
```

If any threads remain unresolved, list them with the reason they couldn't be addressed.

## Guidelines

- **Don't blindly accept everything.** Reviewer feedback is input, not commands. Push back when you have good reason.
- **Don't dismiss bot feedback.** Copilot and CodeRabbit catch real issues. Evaluate each on merit.
- **Keep replies concise.** Reviewers don't want essays. One sentence for acknowledgments, a short paragraph for explanations.
- **Batch related changes.** If multiple threads touch the same file, make all changes before moving to the next file.
- **Commit changes as you go.** Don't accumulate a massive uncommitted diff. Group logically related fixes into commits.
