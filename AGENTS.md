# AGENTS.md

## Mission
Build the Shunde 12345 multi-frequency work-order system as a real, local-first, evidence-based product. Codex owns the hard architecture; downstream UI agents may polish presentation but must not weaken contracts.

## Source-of-truth order
1. Latest explicit product decisions in `docs/PRODUCT_SCOPE.md` and master plan.
2. Locked pain-point source if present (`docs/PAIN_POINTS_LOCKED.md`). Never rewrite it.
3. Real government input files and the real local gazetteer service.
4. `docs/ARCHITECTURE.md`, ADRs and tests.
5. Existing code.
6. Agent inference.

If sources conflict, stop and document the conflict instead of silently guessing.

## Non-negotiable architecture
- API routes are thin. Business logic lives in application handlers/domain services.
- Domain code must not depend on FastAPI, SQLAlchemy, Obsidian, vLLM or UI code.
- Infrastructure is behind typed ports/adapters.
- Obsidian/gazetteer is a knowledge source, not a per-mention hot-path call.
- Resolve all mentions in a work order in batch; use runtime alias snapshot first.
- Embedding is retrieval evidence, never the final same-event judge.
- Do not perform O(N^2) pairwise comparison across the full corpus.
- Local LLM is used only on bounded ambiguous work; batch calls where possible.
- Raw work-order text is immutable. AI-derived fields are separate.
- Human corrections are separate immutable/audited records and are not silently overwritten by reruns.
- AI directly produces multi-frequency results; human correction is available but is not a mandatory review gate.
- Event business-handling status is separate from AI confidence/correction status.

## No degradation
- Never replace required real behavior with a TODO, stub, static fixture or mock in the production path.
- Mocks/fakes are test-only and must use an explicit test provider.
- Never silently swap local inference to a cloud API.
- Never remove a required module because installation/performance is inconvenient.
- Never delete/skip a failing test just to make CI green.
- Never swallow errors or return fake success.
- Never fabricate unknown entities/locations/evidence. Return explicit unknown/unresolved states.
- Never claim target-state capability as shipped-state.
- If blocked by hardware, auth, data or permissions, mark `BLOCKED` in `docs/CURRENT_STATE.md` and preserve the acceptance criterion.

## Engineering health
- Prefer small cohesive modules and explicit interfaces over god services.
- Avoid files > ~500 lines unless generated or strongly justified; split by responsibility before they become unreviewable.
- Avoid functions with mixed orchestration + persistence + model calls; separate them.
- Public boundary data uses Pydantic models/types; no loose `dict[str, Any]` across layers without justification.
- Database schema changes require Alembic migration.
- Background work must be idempotent and resumable.
- Expensive model outputs/embeddings must be cacheable and versioned.
- No secrets, raw government datasets, model weights or runtime caches in Git.

## Required validation before each phase commit
Run the repo-provided check script. Until scripts exist, run equivalent commands:

```bash
uv sync --locked
uv run ruff check .
uv run ruff format --check .
uv run pyright backend
uv run pytest -q
```

Frontend (once present):

```bash
pnpm install --frozen-lockfile
pnpm lint
pnpm test --run
pnpm build
```

Add Playwright E2E once the main flow exists.

A phase is not complete when code merely compiles. Record actual command outputs/summary in `docs/CURRENT_STATE.md`.

## Tests that must exist
- import mapping / malformed rows / partial continuation / idempotency
- raw-data immutability
- multi-mention batch entity resolution
- alias exact match and ambiguous-name cases
- same entity + different event negative case
- similar text + different location negative case
- unknown entity/location does not hallucinate
- retrieval benchmark and hard negatives
- same-event structured output validation
- cluster consistency
- correction survives model rerun
- delete cascade/audit behavior
- job retry/resume/idempotency
- local gazetteer contract/health test

## Performance discipline
- Measure before optimizing.
- Benchmark 1k, 10k and full-scale separately.
- Record hardware, model, quantization, batch size, index settings and dataset version.
- Report P50/P95 and throughput, not a single cherry-picked latency.
- Quality metrics require a named Gold Set. Never invent accuracy numbers.

## Git discipline
- Initialize Git before feature work.
- One coherent, verified hard-install phase per commit.
- Do not commit with failing mandatory checks.
- Do not force-push or rewrite history unless the user explicitly requests it.
- Before handoff: `git status` should be clean or every remaining file must be documented.
- Run `gh auth status`. If remote creation cannot be completed, do not pretend it succeeded; mark `REMOTE_PENDING` and leave exact instructions/script.

## Documentation discipline
- Major architecture changes require an ADR entry in `docs/DECISIONS.md`.
- `docs/CURRENT_STATE.md` distinguishes `DONE / PARTIAL / BLOCKED / PLANNED`.
- Update docs in the same commit as behavior changes.
- TRAE-facing contracts live in `docs/TRAE_HANDOFF.md`.

## Local privacy
- Default to no external telemetry and no cloud model calls.
- Redact work-order text from routine logs; log IDs, timings and structured error metadata.
- `.env` and government data directories are gitignored.

## Final handoff
Before declaring Codex hard-install complete:
1. run all checks,
2. run one real import smoke test,
3. run one real gazetteer lookup,
4. run one real local-model structured inference,
5. run retrieval/same-event benchmark on current Gold Set,
6. update `CURRENT_STATE.md`,
7. update TRAE handoff,
8. commit,
9. push or explicitly record `REMOTE_PENDING`.
