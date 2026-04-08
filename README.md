# kit

Small, purpose-built agents and commands for AI-assisted development workflows. Designed for [OpenPackage](https://openpackage.dev).

## Install

```bash
opkg install gh@pm0u/kit
```

## Agents

| Agent | Description |
|-------|-------------|
| `adversarial-plan-reviewer` | Stress-tests implementation plans. Pokes holes in assumptions, identifies risks, and challenges feasibility before work begins. |
| `adversarial-code-reviewer` | Hunts for AI-generated failure modes in code changes. Targets reckless completion patterns, fabricated assumptions, scope violations, and engineering judgment issues. |
| `distill-learnings` | Extracts reusable lessons from completed work. |

## Commands

| Command | Description |
|---------|-------------|
| `/build-n-break` | Execute a task then adversarially review the result. You review disputes, not the full diff. |
| `/review-plan` | Run an adversarial review against a plan or design doc. |
| `/review-code` | Run an adversarial code review against recent changes. |
| `/implementation-summary` | Generate a summary of what was built and why -- intent and decisions, not a diff listing. |
| `/ton-of-bricks` | Reality-check validation. Forces real-world verification instead of trusting tests and types. |
| `/resolve-pr-feedback` | Fetch and address unresolved PR review comments. |
| `/derive-spec` | Derive a specification from a task description. |
| `/reverse-spec` | Reverse-engineer a specification from existing code. |
| `/trace-flow` | Trace a data or execution flow through the codebase. |
| `/mermaid` | Generate Mermaid diagrams from code or descriptions. |
| `/un-ai` | Strip AI slop from a document. Extract what it actually says in plain language. |

## Philosophy

AI tools are useful for bounded, verifiable tasks. They are bad at judgment, taste, and knowing when they're wrong. These tools are built around that reality:

- **Adversarial by default.** Assume AI output is wrong until proven otherwise.
- **Verification over generation.** The hard part isn't writing code -- it's knowing the code is correct.
- **Human judgment where it matters.** Route human attention to disputes and decisions, not scanning diffs.

## License

MIT
