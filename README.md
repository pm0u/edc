# edc

Defensive tools for working with AI, distributed as a [Claude Code](https://docs.claude.com/en/docs/claude-code) plugin marketplace named `loadout`. It carries two plugins, by weight:

- **`edc`** — *everyday carry.* One-shot prompt utilities, no agents.
- **`ghb`** — *get-home bag.* The heavier machinery: the engineering loops, adversarial review, and the agents they spawn.

## Install

```
/plugin marketplace add pm0u/edc
/plugin install edc@loadout      # everyday-carry utilities
/plugin install ghb@loadout      # engineering loops + reviews
```

CLI equivalents: `claude plugin marketplace add pm0u/edc`, `claude plugin install ghb@loadout`.

Commands are prefixed by their plugin: `/edc:un-ai`, `/ghb:sloop`.

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
