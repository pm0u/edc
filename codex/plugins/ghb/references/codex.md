# Running ghb in Codex

The workflow and role files in this package are prompts, not registered agent types.
Resolve paths from this file's directory; the package root is `..`.

## Role dispatch

Before each delegation, read `../agents/<role>.md` and include its body in the child's task.
Available roles: `loop-dev`, `loop-researcher`, `loop-verifier`,
`adversarial-code-reviewer`, `adversarial-architecture-reviewer`,
`adversarial-plan-reviewer`, and `distill-learnings`.
Provide the actual repository/worktree path, assigned scope, spec, commit ranges,
and reports required by the workflow. Do not assume children inherit this skill.
Keep the coordinator as the only agent that spawns children.

Use the delegation tools exposed by the current Codex environment. With the
collaboration tools, use `spawn_agent`, retain the returned ID, and collect results
with `wait_agent`; use `followup_task` to restart an idle reviewer and `send_message`
for an active one. With the native agent tools, use `spawn_agent`, `wait`, and
`send_input`, resuming closed agents with `resume_agent` when supported. Supply the
role prompt as the task, not as an invented `agent_type` or `subagent_type`.
Use the session's model defaults; Claude model names and tool allowlists do not apply.
Respect the available agent slots: queue overflow reviewers/verifiers, and release
finished agents when the harness supports it. Keep simultaneous reviews on the same
frozen commit; do not start a builder while reviewers are examining its tree.

If delegation is unavailable or prohibited by session instructions, explain that
the requested multi-agent workflow cannot run here. Do not impersonate independent
reviewers or report the loop passed. A direct single-agent review is a separate
alternative that must be clearly identified.

## Files and worktrees

Read files with the available shell/file tools and use `rg` for searching. Research
and review roles do not edit production code. Verifiers can run checks with the
same permissions as the session; this package grants no additional permissions.

Codex spawns do not automatically isolate files. Before concurrent builders, create
one separate branch and worktree per agent using `git worktree add -b <unique-branch>
<absolute-worktree-path> <baseline-commit>`. Pass that path to the child and require
every command and edit to run there. Keep the human in the primary checkout. Record
each returned branch and commit, then integrate in dependency order as the workflow
requires. Do not delete worktrees with uncommitted work or overwrite user changes.

## Inputs and optional integrations

`$sloop`, `$coop`, and the other `$name` examples invoke Codex skills. Flags such as
`--yolo` and `--escalate=co` are interpreted from the user's message, not by a shell.
They alter the workflow only; they never bypass Codex sandbox or approval rules.
Honor explicit authorization and preferences already given in the session.

References to `docs/...` in a workflow mean the package's `../docs/...` directory,
not a directory in the user's project. Coop additionally relies on sloop's shared
mechanics: read `../commands/sloop.md` when running coop, along with the two tier
rubrics required by coop. Read `re-derive.md` when performing the human review.

The diffr MCP integration is optional. Use its diff-link tool only if actually
available. Otherwise report the base/head commits and relevant local file links,
and say that no diffr link was generated. GitHub workflows need an authenticated
`gh` CLI or equivalent available GitHub tools; do not invent remote results.
The review-summary workflow uses `$un-ai` from edc when installed; otherwise edit
the summary's wording directly. Its `--slack` option needs an available Slack
connection and a resolved recipient. Without that connection, return the summary
in the conversation and disclose that it was not sent.
