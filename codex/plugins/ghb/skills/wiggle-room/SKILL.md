---
name: wiggle-room
description: "Measure how much a test suite actually pins — delete a bounded module's implementation, have cheap isolated models rebuild it from the tests alone, and diff the rebuilds' behavior against the original. Every divergence is a gap in the spec, a free choice, or a bug in the original."
---

# wiggle-room

First read [Codex runtime instructions](../../references/codex.md).

Read and follow the [wiggle-room workflow](../../commands/wiggle-room.md). Use the user's request and flags as its input. Resolve linked resources relative to the file containing the link.
