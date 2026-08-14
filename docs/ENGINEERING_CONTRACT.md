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

## Dependency acquisition and mirrors

- 在网络环境受限或官方 CDN 明显低速时，优先使用可信、可审计的正规镜像源。
- 当前 Python 默认镜像：清华大学 TUNA PyPI；当前 npm 默认镜像：npmmirror。
- Docker Hub 拉取可使用 DaoCloud 的透明镜像代理，但镜像仍须保持上游 repository/tag，并记录 digest。
- lockfile、固定版本、包名和校验信息仍是可复现依据；镜像源不得成为替换包、降级依赖或绕过审计的理由。
- 镜像不可用时回退官方源；不得使用来源不明的二进制或模型文件。
