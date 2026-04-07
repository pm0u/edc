---
description: Validate that what you built actually works — test it like a real user, not with mocks
---

# Ton of Bricks

Reality check. Stop trusting tests and mocks. Find a way to validate this work the way a real user would experience it.

## Usage

```
/ton-of-bricks [what-to-validate]
```

$ARGUMENTS

## The Problem This Solves

Agents write code, tests pass, TypeScript compiles, CI is green — and the feature is completely broken. Mocks accept any shape and return whatever the test expects. Type packages don't match runtime APIs. Silent catch blocks swallow real errors and degrade to empty state. 192 tests can pass while literally nothing works.

This command forces real-world validation. No mocks. No assumptions. Actual requests, actual responses, actual rendered output.

## Step 1: Understand What Needs Validating

If arguments were provided, use them. Otherwise, look at recent changes:

```bash
git diff --name-only HEAD~3..HEAD
```

Read the changed files. Determine what the work is supposed to do from the user's perspective — not what the code does internally, but what a user would see, click, or receive.

## Step 2: Figure Out How to Test It For Real

This is the core of the skill. There is no universal recipe — you must figure out the right validation strategy for what was built. Think like a QA engineer, not a unit test writer.

**Ask yourself:**
- How would a human verify this works?
- What would they look at, click, or request?
- What would "working" look like to them?

**Common strategies (not exhaustive — use judgment):**

- **Web page/UI?** Start the dev server, hit the actual URL, check that real content renders. Use Playwright MCP or Chrome DevTools MCP to inspect the DOM, not screenshots.
- **API endpoint?** Curl it. Send real requests. Check real responses. Validate the shape and content of what comes back.
- **GraphQL?** Run the actual query against the real schema endpoint. Don't trust TypeScript types as ground truth — the runtime API may differ.
- **Data pipeline?** Feed it real input. Check the output file/database/queue has the expected content.
- **CLI tool?** Run it with real arguments. Check stdout, exit codes, side effects.
- **Integration?** Hit the upstream service. If there's a staging/dev environment, use it. If there's a local proxy, verify the proxy actually works before testing through it.

**If you genuinely cannot test it live** (no dev server available, external service requires credentials you don't have, etc.), say so explicitly and describe exactly what manual step the user should take to validate. Do not pretend mock-based validation is sufficient.

## Step 3: Run the Validation

Execute your validation strategy. For each thing you check:

1. **State what you're checking** and what you expect
2. **Run the actual check** — real request, real command, real browser action
3. **Report what actually happened** — actual response, actual output, actual DOM content

Do not summarize. Show the evidence.

## Step 4: Report

```markdown
## Reality Check

### What was validated
{Brief description of what the changes are supposed to do}

### Results

| Check | Expected | Actual | Status |
|-------|----------|--------|--------|
| ... | ... | ... | PASS/FAIL |

### Issues Found
{If anything failed: what went wrong, what the real error is, what needs fixing}

### Confidence Level
{How thoroughly was this validated? What couldn't be checked and why?}
```

## Guidelines

- **Never trust passing tests as evidence.** Tests are a safety net, not proof of correctness. This skill exists because tests lie.
- **Never trust types as API truth.** TypeScript interfaces, generated types, and schema packages can diverge from what the API actually accepts and returns at runtime.
- **Watch for silent failures.** Empty states, catch blocks that swallow errors, loading spinners that never resolve — these are features hiding broken backends.
- **Check the full chain.** If the UI calls an API that calls a service, verify each hop. The bug is usually at a boundary.
- **If you can't validate something, say so.** "I couldn't test X because Y" is infinitely better than "looks good to me" based on vibes.
