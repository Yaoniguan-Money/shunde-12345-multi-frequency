# ENGINEERING_CONTRACT.md

This file expands the concise root `AGENTS.md`.

## Clean code
- small cohesive functions
- explicit domain names
- typed inputs/outputs
- no cross-layer convenience imports
- no god handler
- no duplicated normalization logic
- no hidden global model clients
- dependency injection at application boundary

## Health
- `/health/live`: process alive
- `/health/ready`: DB + required local dependencies ready
- `/health/dependencies`: model/gazetteer versions and status without leaking secrets
- job metrics: queued/running/failed/completed
- request correlation ID
- structured logs with work-order content redacted

## Data integrity
- raw imported data immutable
- derived AI records versioned
- migrations mandatory
- delete rules tested
- correction audit survives model rerun

## Reliability
- long jobs persisted
- checkpoints between expensive stages
- retry only idempotent operations
- exponential backoff for local service transient errors
- circuit/timeout limits around model/gazetteer adapters

## Change control
- architectural change -> ADR in `DECISIONS.md`
- schema change -> migration + tests
- API change -> OpenAPI/client update + TRAE note
- model change -> benchmark comparison before default switch
