---
name: verify-web-ui
description: "Run a pull request's test plan in a real browser and prove it — drive each row with Playwright, record a video and screenshots per row, judge Pass / Fail / Couldn't verify from what the page actually showed, keep a re-runnable Playwright repro for every row, and draft a PR comment with the evidence that is posted with `gh pr comment --attach` once the user approves. Use whenever someone asks to verify, click through, smoke-test, or prove a PR's test plan or a web UI change in the browser, wants screenshots or video of a UI change on a PR, or asks whether the manual checks in a PR description actually pass — even if they don't say \"Playwright\"."
---

# verify-web-ui

First read [Codex runtime instructions](../../references/codex.md).

Read and follow the [verify-web-ui workflow](../../commands/verify-web-ui.md). Use the user's request and flags as its input. Resolve linked resources relative to the file containing the link.
