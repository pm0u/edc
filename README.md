# edc

Defensive tools for working with AI, available as [Claude Code](https://docs.claude.com/en/docs/claude-code) plugins and Codex plugins. The Claude marketplace is named `loadout`. It carries two plugins, by weight:

- **`edc`** — *everyday carry.* One-shot prompt utilities, no agents.
- **`ghb`** — *get-home bag.* The heavier machinery: the engineering loops, adversarial review, and the agents they spawn.

## Install in Claude Code

```
/plugin marketplace add pm0u/edc
/plugin install edc@loadout      # everyday-carry utilities
/plugin install ghb@loadout      # engineering loops + reviews
```

CLI equivalents: `claude plugin marketplace add pm0u/edc`, `claude plugin install ghb@loadout`.

Commands are prefixed by their plugin: `/edc:un-ai`, `/ghb:sloop`.

## Install in Codex

The Codex packages are `codex/plugins/edc` and `codex/plugins/ghb`. Ask Codex to install both local packages into your personal plugin marketplace. Each package has a `.codex-plugin/plugin.json` manifest and discoverable skills. Start a new thread after installation.

Invoke skills with `$write-task`, `$un-ai`, `$sloop`, `$coop`, etc. The command tables below use Claude's slash syntax; the same names are available as Codex skills. Workflow flags still apply, for example `$sloop --yolo fix the cache invalidation bug` or `$coop --escalate=co add the new parser`.

`ghb` uses the delegation tools available in your Codex session, loading its bundled agent prompts explicitly. Multi-agent workflows require delegation support. Concurrent builders get explicit Git worktrees. GitHub workflows require authenticated GitHub access; Slack delivery and diffr links are optional integrations, not installed by this package.

### Maintaining the Codex packages

The original files under `plugins/` remain the source of truth. After editing a command, skill, role, or rubric, regenerate and check the Codex packages:

```sh
python3 scripts/build_codex.py
python3 scripts/build_codex.py --check
```

The build uses only Python's standard library. It converts command invocations and runtime-specific instructions, includes the shared documents and role prompts, and derives a version suffix from package content so changed prompts receive a fresh install cache. Edit `scripts/codex-runtime.md` for the Codex delegation and worktree adapter. Do not edit generated files under `codex/` directly.

For a personal installation, refresh `~/plugins/edc` and `~/plugins/ghb` from the generated packages, then run `codex plugin add edc@personal` and `codex plugin add ghb@personal` (substitute your marketplace name if different). Start a new thread to pick up the changes. The source checkout and installed plugin cache are separate.

## edc — everyday carry

Lightweight one-shot tools; install if you just want the utilities.

| Command | What it does |
|---------|--------------|
| `/edc:write-task` | Turn a rough request into a task someone can execute AFK — grounded in real code, grilled before it's written. |
| `/edc:derive-spec` · `/edc:reverse-spec` | Derive a spec from a task, or reverse one out of existing code. |
| `/edc:trace-flow` · `/edc:mermaid` | Trace a data/execution flow; generate Mermaid diagrams. |
| `/edc:implementation-summary` · `/edc:ton-of-bricks` | Summarize the intent behind a change; reality-check validation. |
| `/edc:un-ai` | Strip AI slop from a doc. |

## ghb — get-home bag

The frameworks and their kit. Everything here spawns agents (bundled with the plugin).

| Command | What it does |
|---------|--------------|
| [`/ghb:sloop`](plugins/ghb/docs/sloop.md) | The engineering loop. A dev agent builds against a spec, two adversarial reviewers attack in parallel, and a coordinator iterates with fresh dev agents until the code passes review. |
| [`/ghb:coop`](plugins/ghb/docs/coop.md) | The cooperative loop. A fork of sloop where the work is split into tiered slices ([Own/Co/Race](plugins/ghb/docs/tiers-core.md)) and you build the ones you need to understand while agents build the rest. |
| `/ghb:review-code` · `/ghb:review-plan` | Adversarial review of recent changes, or of a plan/design doc. |
| `/ghb:build-n-break` · `/ghb:review-summary` | Execute a task then adversarially review it; morning PR review summary. |
| [`/ghb:tier`](plugins/ghb/commands/tier.md) | Classify one task, then sequence the split — you build the part you need to understand, an agent takes the rest when you're done. No loop. |
| [`/ghb:wiggle-room`](plugins/ghb/skills/wiggle-room/SKILL.md) | Measure how much a test suite pins. Delete a bounded module, have cheap isolated models rebuild it from the tests alone, diff their behavior against the original, and triage each divergence: pin it, free it, or it's a bug. |
| [`/ghb:perturb`](plugins/ghb/skills/perturb/SKILL.md) | Run the suite under a changed environment (timezone, locale, the date, a backwards clock, readdir order, no network) and report what the code and its tests rely on without saying so. Model-free. |
| [`/ghb:resolve-pr-feedback`](plugins/ghb/commands/resolve-pr-feedback.md) | Address unresolved PR comments, tiered — the mechanical fixes get handled, the ones that would move your model of the code come back to you. |
| [`/ghb:distill-reviews`](plugins/ghb/skills/distill-reviews/SKILL.md) | Distill a window of merged-PR review feedback into the repo's agent and Copilot review instructions, under a size budget, proposed as a PR — plus any live bugs the reviews surfaced. |

The agents (`loop-*` builders, `adversarial-*` reviewers) live in this one plugin, so nothing is shared or duplicated across plugins.

## Philosophy

AI tools are useful for bounded, verifiable tasks. They are bad at judgment, taste, and knowing when they're wrong. These tools are built around that reality:

- **Adversarial by default.** Assume AI output is wrong until proven otherwise.
- **Verification over generation.** The hard part isn't writing code -- it's knowing the code is correct.
- **Human judgment where it matters.** Route human attention to disputes and decisions, not scanning diffs.

Stay safe out there, meatbags.

## License

MIT
