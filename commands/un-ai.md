---
description: Strip AI slop from a document — extract what it actually says in plain language
---

# Un-AI

Take an AI-generated document and rewrite it as what a human would have actually written. Kill the filler, the hedging, the bullet-point-ification, and the corporate enthusiasm. Extract the actual content.

## Usage

```
/un-ai [file path, URL, or paste the text]
```

$ARGUMENTS

## Step 1: Get the Input

If a file path was provided, read it. If a URL, fetch it. If no arguments, ask the user to paste the text.

## Step 2: Identify the Slop

Before rewriting, identify what's noise:

- **Preamble that says nothing.** "In today's rapidly evolving landscape..." "As we continue to innovate..." "This document outlines our strategic approach to..."
- **Restating the obvious.** Sentences that just rephrase the heading they're under.
- **Hollow transitions.** "With that in mind," "Building on this," "It's worth noting that" — delete, the next sentence stands on its own.
- **Weasel hedging.** "It's important to consider that we might want to think about potentially exploring..." — just say the thing or don't.
- **Synonym stacking.** "Streamline and optimize our processes and workflows" — pick one word.
- **Fake precision.** "Leverage our robust, scalable, enterprise-grade solution" — what does it actually do?
- **Bullet inflation.** A single idea broken into 5 bullets that each say the same thing with different words.
- **Conclusion that restates the intro.** "In summary, as outlined above..." — cut it entirely.

## Step 3: Extract the Actual Content

For each section, ask: **what is this actually saying?** Write that instead.

Rules:
- One idea per sentence. One sentence if possible.
- Use concrete nouns and verbs. "We'll add search to the map" not "We'll implement an enhanced discovery experience."
- If a paragraph can be one sentence, make it one sentence.
- If a section can be a paragraph, don't make it a section.
- If three bullets say the same thing, pick the best one.
- If something is genuinely vague in the original — meaning the author didn't actually decide anything — say so. "This section doesn't commit to anything specific" is more honest than rephrasing the vagueness.
- Preserve actual decisions, dates, names, numbers, and commitments. Those are the signal.
- If the document is entirely filler with no substance, say that.

## Step 4: Output

```markdown
## Un-AI'd

{The rewritten document. Same structure if the structure was meaningful, flattened if it wasn't.}

---

**Compression: {original word count} → {new word count} ({percentage}% reduction)**

**What was lost:** {Nothing meaningful / list anything substantive you cut and why}

**What was never there:** {List any decisions or specifics the original pretended to contain but didn't}
```

## Guidelines

- **Don't add meaning that isn't there.** If the original is vague, your version should be short, not creative.
- **Don't be diplomatic about it.** If the document is 2000 words of nothing, the output should reflect that.
- **Preserve tone where it matters.** If the original makes a strong claim or commitment, keep that. Strip the padding, not the substance.
- **This isn't editing.** You're not making the AI text better — you're replacing it with what a person would have written if they'd skipped the AI and just thought about it for 10 minutes.
