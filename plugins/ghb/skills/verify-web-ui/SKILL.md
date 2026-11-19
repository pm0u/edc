---
name: verify-web-ui
description: Run a pull request's test plan in a real browser and prove it — drive each row with Playwright, record a video and screenshots per row, judge Pass / Fail / Couldn't verify from what the page actually showed, keep a re-runnable Playwright repro for every row, and draft a PR comment with the evidence that is posted with `gh pr comment --attach` once the user approves. Use whenever someone asks to verify, click through, smoke-test, or prove a PR's test plan or a web UI change in the browser, wants screenshots or video of a UI change on a PR, or asks whether the manual checks in a PR description actually pass — even if they don't say "Playwright".
context: fork
model: sonnet
---

# Verify Web UI

Input: $ARGUMENTS

A test plan in a PR description is a list of claims nobody has checked: open this URL, do this,
expect that. Reviewers skim it, authors run it once from memory, and the PR merges on trust. This
skill runs each row in a browser, keeps what the browser showed, and drafts a PR comment where a
reviewer can see it — screenshots and video as evidence, and a Playwright spec so anyone can run
the checks again instead of trusting the recording.

The verdict is the product, so it has to be honest. **Couldn't verify** is a first-class result:
use it whenever the evidence doesn't settle the row. A wrong Pass is worse than no verification,
because it ends the conversation the row was supposed to start.

You run as a subagent and can't ask the user anything. Where the steps below need the user — an
unresolvable placeholder, a login, an app that isn't running — record it and carry on, or stop and
hand back with exactly what they need to do. You never post: you hand back a draft, and the
session that invoked you posts it once the user approves (section 9).

## Usage

```
/ghb:verify-web-ui <PR number or URL> [--base-url <url>] [--rows 2,4] [--values deliveryID=1,previewID=8]
/ghb:verify-web-ui <path to a test plan file> [--base-url <url>]
```

`$OUT` is this run's directory, outside the repo: `<session scratchpad or $TMPDIR>/verify-<pr or
slug>-<YYYYMMDD-HHMM>/`. Everything the run writes goes there, so nothing lands in the working tree.

## 1. Check you're testing the right thing

Verifying the wrong build is the easiest way to produce a confident, worthless Pass. Check all
three before reading the plan, because resolving the plan's placeholders needs the running app:

- **The checkout:** fetch the PR (`gh pr view <n> --json number,url,body,headRefName,headRefOid`)
  and compare `headRefOid` with `git rev-parse HEAD`. If they differ, stop and hand back — don't
  check out branches in a working tree that might hold the user's changes.
- **The server runs this checkout.** A port can be served from another clone, an old container,
  or a stale build. Find what listens on the base URL's port (`lsof -nP -iTCP:<port> -sTCP:LISTEN`)
  and trace it to this repo: a dev server whose working directory is the repo, a container whose
  compose project directory or source mount is the repo (`docker ps`, `docker inspect`). If it's a
  build rather than a live mount, check it was built after the PR's head commit. If you can't tie
  the server to this checkout, say so in the report — it qualifies every verdict.
- **It answers.** `curl -s -o /dev/null -w '%{http_code}' <base-url>` — use a GET; some dev
  servers answer HEAD with an error while serving GET fine. If nothing answers, hand back with
  the repo's dev-server command; don't start long-lived servers.
- **Login.** If the app redirects to a login page, hand back and ask the user to save a session
  themselves — `npx playwright codegen --save-storage=$OUT/auth.json <base-url>`, log in, close
  the window — then rerun. Never ask for credentials, and never attach or commit `auth.json`: it
  holds live session cookies.

If `--base-url` is absent, infer it from the plan's URLs or the repo's dev-server config.

## 2. Read the plan

Find the section of the PR body that describes manual checks — usually headed "Test plan",
"Testing", "How to test", or "Verification" — and normalize every row into `$OUT/plan.md`:

```
## Row 1: <short name>
Start: <URL>
Do: <the actions, as steps>
Expected: <what should be true afterwards>
```

Plans come as tables, checklists, numbered steps, or prose; keep the author's wording for
"Expected" so the verdict answers what they actually claimed. Mark a row **out of scope** when a
browser can't check it (CI status, a backend log, a mobile app), and keep it in the report.

Placeholders like `:id`, `<recordID>`, or "a long list" need real values. Use `--values` first,
then resolve the rest from the running app (its API, a list page, the frontend's API client for the
routes) and record which value you used. A placeholder you can't resolve makes its row Couldn't
verify; write that row's test with `test.skip(<reason>)` so it reruns once someone has the data.

When the plan's own URL doesn't render the thing under test (a results page that needs a query
first), use the smallest substitution that reaches it, state it in the row's Observed, and treat
the substitution itself as worth the author's attention — their plan doesn't work as written.

## 3. Set up Playwright

Prefer the repo's own `@playwright/test` if it has one. Otherwise set it up in `$OUT` with
`npm init -y` and `npm i -D --save-exact @playwright/test@<version>`, never a floating tag. Pick the
version to match a browser already in the Playwright cache (`~/Library/Caches/ms-playwright` on
macOS, `~/.cache/ms-playwright` on Linux): each release's `browsers.json` names its Chromium build
number, so a cached `chromium-1208` means the release whose `browsers.json` lists 1208. Only if no
cached build matches, install one with `npx playwright install chromium`, and say so in the report.
Record the browser version (`npx playwright install --dry-run chromium` prints it) for the comment.

Write `$OUT/playwright.config.ts`, setting `baseURL` and, if a session was saved, `storageState`:

```ts
import { defineConfig, devices } from '@playwright/test'

export default defineConfig({
  testDir: '.',
  testMatch: 'verify.spec.ts',
  outputDir: './results',
  fullyParallel: false,
  workers: 1,
  retries: 0,
  reporter: [['list'], ['json', { outputFile: './report.json' }]],
  use: {
    baseURL: 'http://localhost:3000',
    // storageState: './auth.json',
    viewport: { width: 1280, height: 800 },
    video: { mode: 'on', size: { width: 1280, height: 800 } },
    screenshot: 'on',
    trace: 'on',
    // Headless Chromium has no WebGL without SwiftShader, so map and canvas apps render blank.
    launchOptions: { args: ['--enable-unsafe-swiftshader'] },
  },
  projects: [{ name: 'chromium', use: { ...devices['Desktop Chrome'], viewport: { width: 1280, height: 800 } } }],
})
```

## 4. Write one test per row

Write `$OUT/verify.spec.ts` with one `test('row N: <short name>', ...)` per row, in plan order:

- **Drive it like a user.** Prefer role and text locators (`getByRole`, `getByText`) over CSS, so
  the test breaks when the UI a user sees changes, not when a class name does.
- **Encode "Expected" as assertions wherever it's mechanical:** the URL, visible text, an element's
  count or state, a request that fired. These make the verdict reproducible.
- **Prefer app state over pixels.** When the claim lives inside a canvas or a map (layer order,
  what's drawn, the camera), find a read-only hook into the app's state — a debug global, the
  framework's dev-mode component tree, the map library's instance — and assert on that. A pixel
  judgment is the fallback, not the default.
- **Screenshot the moment of judgment,** after any transition or animation has finished (wait for
  the element's final opacity or position, not a timer). Name it for what it shows
  (`row-3-panel-open.png`), and add a `before` shot when the row is about a change.
- **Waiting for something not to happen** (a selection that should survive a double-click) is the
  one place a fixed wait is right: no event marks the absence. Keep it short, and put the reason in
  the test name or a one-line annotation.
- Collect console errors per test (`page.on('console')`) and report them even when the row passes.

Shared helpers are fine; the spec is reproduced whole in the comment.

## 5. Run and judge

`npx playwright test -c $OUT/playwright.config.ts`. Per row:

- **Script problem** (a locator matched nothing, navigation timed out before the page rendered):
  that's your test, not the product. Fix it and rerun, at most twice per row. If it still can't
  drive the page, the verdict is Couldn't verify, with the reason.
- **Assertion failed on product behavior:** Fail. Never loosen an assertion, stretch a timeout past
  reason, or change the expected value to get a row green — that converts a finding into a lie.
- **Visual claims:** read the screenshots. Pass only when the image plainly shows the expected
  state; if it's ambiguous or too small to tell, it's Couldn't verify — say what would settle it.

Running a subset (`-g "row N"`) empties `outputDir`, deleting every other row's video and the
report. Once the spec is settled, do one final full run, and take all evidence from that run.

Write `$OUT/results.md`: one line per row with the verdict, the observed state in a sentence, and
any console errors.

## 6. Prepare the evidence

Copy what you'll attach out of `results/` into `$OUT` beside the comment: named screenshots, and
each row's `video.webm` as `row-N.webm`. Never attach anything straight from `results/` —
Playwright's automatic screenshots, videos, and `trace.zip` are unredacted.

Look at every file you'll attach for personal data, secrets, or tokens on screen (emails, names,
addresses, keys in a dev panel). Redact before anything leaves the machine: Playwright's `mask`
option on `page.screenshot` for screenshots, and `ffmpeg -vf drawbox=...` over the same region
for video — then spot-check a few frames. Drop a file you can't redact. Note in the report what
you masked and why. Attachments on a private repo are visible to everyone with access to it.

GitHub accepts `.png`, `.gif`, `.jpg`, `.mp4`, `.mov`, and `.webm`, up to 10 MB per image and 10 MB
per video (100 MB on paid plans), and one `gh` command takes up to 50 files. Trim or downscale an
oversized video with `ffmpeg`, or attach screenshots only and say so.

## 7. Draft the comment

Write `$OUT/comment.md`. `gh` rewrites a relative reference like `![alt](./row-3-panel-open.png)`
into the uploaded asset; a video referenced the same way renders as a player and takes no alt text.
This is an evidence report with a fixed shape — follow this template rather than any personal
writing-style guidance for PR comments:

~~~markdown
### UI verification — <n> rows: <p> pass, <f> fail, <c> couldn't verify

Ran against `<short sha>` at `<base-url>`, Chromium <version>, <viewport>. <Where the server's
code came from, one clause. Placeholder values used, one sentence.>

| Row | Verdict | Observed |
|---|---|---|
| 1. <short name> | Pass | <one sentence> |

<details><summary>Row 1: <short name> — Pass</summary>

**Expected:** <author's wording>
**Observed:** <what the page showed; any substitution; console errors if any>

![Row 1 after: <what it shows>](./row-1-after.png)
![](./row-1.webm)
</details>

<details><summary>Reproduce</summary>

Save as `verify.spec.ts` beside this config, then `npx playwright test -g "row N"`.

```ts
<playwright.config.ts with baseURL set to a placeholder>
```

```ts
<the whole verify.spec.ts>
```
</details>
~~~

Order the per-row sections Fail, then Couldn't verify, then Pass — the first two are what the
reviewer needs. Keep prose to observed facts.

## 8. What this doesn't prove

Put these in the comment's closing line when they apply, rather than letting a green table imply
them: one browser, one viewport, one run; rows judged from screenshots rest on reading an image;
the app's data was whatever the local environment had.

## 9. Hand back

Return to the invoking session, in this order:

1. The verdict table.
2. The path to `$OUT/comment.md` and every attachment with its size.
3. What you redacted, and any qualifier on the run (server not tied to the checkout, a browser
   download, a substituted URL).
4. The posting command, for the invoking session to run **only after the user approves the
   draft**:
   `cd $OUT && gh pr comment <n> --body-file comment.md --attach ./<file> ...` (one `--attach` per
   referenced file). When re-verifying after fixes, post a new comment rather than editing the
   old one, so the history of what failed stays readable.
5. The follow-up that makes videos play inline. `gh` rewrites a video reference into a link,
   `[row-1.webm](https://github.com/user-attachments/assets/<id>)`, and GitHub only renders a
   player for the bare asset URL on its own line. With the comment URL from step 4:

   ```bash
   id=<comment id>; repo=<owner/name>
   gh api repos/$repo/issues/comments/$id --jq .body |
     perl -pe 's{\[[^\]]+\.(?:webm|mp4|mov)\]\((https://github\.com/user-attachments/assets/[^)]+)\)}{\n$1\n}g' > body.md
   gh api -X PATCH repos/$repo/issues/comments/$id -F body=@body.md --jq .html_url
   ```
