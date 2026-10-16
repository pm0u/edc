#!/usr/bin/env python3
"""Build Codex packages from the maintained Claude commands, skills, and roles."""

import argparse
import hashlib
import json
from pathlib import Path
import re
import sys

ROOT = Path(__file__).resolve().parents[1]
PLUGINS = ("edc", "ghb")


def split_frontmatter(text):
    if not text.startswith("---\n"):
        return "", text
    header, body = text[4:].split("\n---\n", 1)
    return header, body.lstrip()


def adapt(text, names):
    text = text.replace("$ARGUMENTS", "Use the user's skill invocation and conversation context as the input, including any flags.")
    text = text.replace("(`${CLAUDE_PLUGIN_ROOT}` expands to the plugin's install directory)",
                        "(paths are relative to this workflow file)")
    text = text.replace("${CLAUDE_PLUGIN_ROOT}/docs/", "../docs/")
    text = text.replace("CLAUDE.md", "AGENTS.md")
    text = text.replace("Subagents cannot spawn subagents — all spawning happens here.",
                        "Keep all delegation in the coordinator; instruct child agents not to delegate further.")
    text = text.replace("one message, multiple Agent calls", "separate Codex spawn calls, then collect both results")
    text = text.replace("e.g. a SendMessage tool", "e.g. followup_task or resume_agent followed by send_input")
    text = text.replace("(SendMessage)", "(followup_task or resume_agent followed by send_input)")
    text = text.replace('using `isolation: "worktree"`',
                        "in a worktree you create with `git worktree add` before spawning (see the Codex runtime guide)")
    text = text.replace("with the Read tool", "with the available file-reading tool")
    text = text.replace("(Read tool)", "(using the available file-reading tool)")
    for name in sorted(names, key=len, reverse=True):
        text = re.sub(r"(?<![\w./])/(?:edc:|ghb:)?" + re.escape(name) + r"(?![\w./-])",
                      lambda _: "$" + name, text)
    return text


def build():
    files = {}
    names = {p.stem for p in (ROOT / "plugins").glob("*/commands/*.md")}
    names |= {p.parent.name for p in (ROOT / "plugins").glob("*/skills/*/SKILL.md")}
    for plugin in PLUGINS:
        source = ROOT / "plugins" / plugin
        prefix = Path("plugins") / plugin
        manifest = json.loads((source / ".claude-plugin/plugin.json").read_text())
        manifest.pop("$schema", None)
        manifest["skills"] = "./skills/"
        manifest["interface"] = {
            "displayName": "Everyday Carry" if plugin == "edc" else "Get-Home Bag",
            "shortDescription": "One-shot AI utilities" if plugin == "edc" else "Engineering loops and adversarial reviews",
            "longDescription": manifest["description"],
            "developerName": manifest["author"]["name"],
            "category": "Productivity",
            "capabilities": [],
            "defaultPrompt": ["Use $write-task to refine this request." if plugin == "edc" else "Use $sloop for this engineering task."],
        }
        workflows = {p.stem: p for p in source.glob("commands/*.md")}
        for p in source.glob("skills/*/SKILL.md"):
            if p.parent.name in workflows:
                raise ValueError(f"Duplicate workflow: {p.parent.name}")
            workflows[p.parent.name] = p
        for name, path in sorted(workflows.items()):
            header, body = split_frontmatter(path.read_text())
            match = re.search(r"^description: (.+)$", header, re.M)
            if not match:
                raise ValueError(f"Missing single-line description: {path}")
            # Existing source descriptions are plain YAML scalars; quote generated YAML.
            description = match.group(1)
            prelude = ""
            if plugin == "ghb":
                prelude = "First read [Codex runtime instructions](../../references/codex.md).\n\n"
            files[prefix / "skills" / name / "SKILL.md"] = (
                f"---\nname: {name}\ndescription: {json.dumps(description, ensure_ascii=False)}\n---\n\n"
                f"# {name}\n\n{prelude}"
                f"Read and follow the [{name} workflow](../../commands/{name}.md). "
                "Use the user's request and flags as its input. Resolve linked resources relative to the file containing the link.\n"
            )
            files[prefix / "commands" / (name + ".md")] = adapt(body, names)
        for folder in ("docs", "agents"):
            for path in sorted((source / folder).glob("*.md")):
                _, body = split_frontmatter(path.read_text())
                files[prefix / folder / path.name] = adapt(body, names)
        if plugin == "ghb":
            files[prefix / "references/codex.md"] = (ROOT / "scripts/codex-runtime.md").read_text()
        files[prefix / "LICENSE"] = (ROOT / "LICENSE").read_text()
        # Content-derived semver metadata makes changed prompts install as a new cache entry.
        digest = hashlib.sha256(json.dumps(manifest, sort_keys=True).encode())
        for path, content in sorted(files.items()):
            if path.is_relative_to(prefix):
                digest.update(str(path).encode())
                digest.update(content.encode())
        manifest["version"] = manifest["version"].split("+", 1)[0] + "+codex." + digest.hexdigest()[:12]
        files[prefix / ".codex-plugin/plugin.json"] = json.dumps(manifest, indent=2, ensure_ascii=False) + "\n"
    return files


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, default=ROOT / "codex", help="Generated package root")
    parser.add_argument("--check", action="store_true", help="Check generated files without writing")
    args = parser.parse_args()
    files = build()
    expected = set(files)
    existing = {p.relative_to(args.output) for p in args.output.rglob("*") if p.is_file()}
    stale = existing - expected
    if stale:
        raise SystemExit("Unexpected/stale files in output; inspect before removing: " + ", ".join(map(str, sorted(stale))))
    different = []
    for relative, content in files.items():
        destination = args.output / relative
        if destination.exists() and destination.read_text() == content:
            continue
        different.append(str(relative))
        if not args.check:
            destination.parent.mkdir(parents=True, exist_ok=True)
            destination.write_text(content)
    if args.check and different:
        print("Codex packages need regeneration:\n" + "\n".join(different), file=sys.stderr)
        return 1
    print(f"{'Checked' if args.check else 'Built'} {len(files)} files for edc and ghb.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
