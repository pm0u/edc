# /sloop — the engineering loop

A coordinator-driven loop for building a change under adversarial review. A dev agent builds against a spec, reviewers attack the result, and a coordinator iterates with fresh dev agents until the code passes review or the loop stalls. Then a saboteur checks whether the tests would catch the code going wrong. You stay out of it until the end, except for one approval gate before any code is written.

The bet is simple: AI is decent at building bounded things and bad at knowing when it's wrong. So sloop never trusts a single pass. Whatever the builder produces gets stress-tested by agents whose only job is to find what's broken, and a coordinator — which never writes code itself — decides what's a real finding and what's noise.

This page is the overview. The workflow itself — roles, phases, thresholds, report format — lives only in [`commands/sloop.md`](../commands/sloop.md).

## When to use it

Reach for sloop when the task is big enough that a single build-and-hope pass isn't trustworthy, and concrete enough to pin down acceptance criteria. It earns its overhead on changes where the risk is in the details — the kind of thing you'd want a careful reviewer on anyway.

Skip it for trivial changes, where the coordination cost outweighs the work, and for open-ended exploration where you don't yet know what "done" means. sloop needs a contract to build and review against — if you can't state 2-6 acceptance criteria, you're not ready for the loop yet, and `/derive-spec` is the better first stop.

## Usage

```
/sloop [task description]
/sloop --yolo [task description]
```

`--yolo` skips the approval gate; the coordinator resolves plan-review questions itself and records the calls in the report.

## At a glance

0. **Spec.** Your task becomes a short spec with acceptance criteria, stress-tested by a plan reviewer. You approve it, and it freezes.
1. **Build.** A dev agent implements it and reports what it verified and what it couldn't.
2. **Review.** Line-level and architecture reviewers attack the diff; a verifier reproduces the dev agent's claims when they go beyond the test suite.
3. **Adjudicate.** The coordinator triages findings and decides to pass, iterate with a fresh dev agent, or stall and escalate to you.
4. **Sabotage.** The saboteur tries to break the passed code without failing the tests; each survivor gets a killing test.
5. **Report.** You get the result, routed to what needs your eyes.

## What you get back

The work lands on a feature branch, with the loop's commits kept off main. The report gives you a diff link, every acceptance criterion tabulated with evidence, a test-strength line from sabotage, and a short list of specific things to check by hand. It routes your attention to disputes and unverified claims instead of the whole diff, and it shows what the coordinator dismissed as noise so you can catch a finding it dropped too eagerly.

## Limits worth knowing

- Passing means the code survived adversarial review, not that it's correct. You're still the final reviewer.
- Sabotage measures the tests against the spec, not against everything that could go wrong. Behavior the spec never named is untested by construction.
- The loop stalls on purpose — on a direction disagreement, a finding that keeps coming back, or the iteration cap — and escalates to you rather than burning more rounds.
- The spec freezes after the approval gate. Changing scope mid-loop means starting a new loop.
- Some findings come to you mid-loop even though the loop is otherwise autonomous: ones that question the spec's premise are never the coordinator's to dismiss.
