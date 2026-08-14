# LOCAL_KNOWLEDGE_BASE.md

## Current package

Expected Windows package root:

`C:\Users\Lenovo\Desktop\顺德地名库交接包`

Phase 0 live inspection on 2026-08-15 confirmed OpenAPI version `1.0` and these exact paths:

`/`, `/batch`, `/match`, `/normalize`, `/search`, `/stats`

The live `/stats` response reported 217 standard places, 232 aliases, 12 organization synonyms, 8 suffix rules and 488 semantic candidates. The README states 545 semantic candidates; this discrepancy remains documented and unresolved. Live behavior is evidence, but the upstream package must not be silently rewritten.

User-provided handoff instructions say:

- drag `顺德地名库` into an Obsidian vault;
- start reading from `顺德地名知识库.md`;
- start service from `地名服务` with `python server.py`;
- inspect `http://localhost:8000/docs`.

## Integration rule

Do NOT hardcode guessed endpoints. Codex must inspect README and live OpenAPI first.

Do NOT call Obsidian/service once per entity mention. Build a runtime snapshot and exact alias automaton.

## Runtime resolution order

1. exact alias snapshot
2. fuzzy string candidates
3. entity embedding candidates
4. batched LLM disambiguation only when needed

All results include source/snapshot version and confidence.

## Update flow

AI-discovered alias -> proposal -> manual knowledge review -> source update -> snapshot rebuild.
