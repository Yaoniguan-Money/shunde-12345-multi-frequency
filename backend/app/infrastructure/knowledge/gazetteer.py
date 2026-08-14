from dataclasses import dataclass
from typing import Any, cast
from uuid import NAMESPACE_URL, uuid5

import httpx

from backend.app.domain.types import (
    CanonicalEntity,
    EntityCandidate,
    EntityCandidateSet,
    EntityId,
    GazetteerHealth,
    GazetteerSnapshot,
    ResolutionState,
)


class GazetteerContractError(RuntimeError):
    """The live service does not expose the required schema-driven operation."""


@dataclass(frozen=True, slots=True)
class _BatchOperation:
    path: str
    parameter: str


class GazetteerHttpAdapter:
    """HTTP adapter that discovers the real OpenAPI batch operation at runtime."""

    def __init__(self, base_url: str, timeout_seconds: float = 2.0) -> None:
        self._base_url = base_url.rstrip("/")
        self._timeout = timeout_seconds
        self._operation: _BatchOperation | None = None
        self._version: str | None = None

    async def health(self) -> GazetteerHealth:
        try:
            async with httpx.AsyncClient(timeout=self._timeout) as client:
                response = await client.get(f"{self._base_url}/openapi.json")
                response.raise_for_status()
                document = response.json()
            self._discover(cast(dict[str, Any], document))
            return GazetteerHealth(True, self._version)
        except (httpx.HTTPError, ValueError, TypeError, GazetteerContractError):
            return GazetteerHealth(False, None)

    async def snapshot(self) -> GazetteerSnapshot:
        raise GazetteerContractError(
            "远端 OpenAPI 只提供归一化查询，没有实体枚举端点；请用交接包 SQLite 构建运行时快照"
        )

    async def lookup_many(self, mentions: tuple[str, ...]) -> tuple[EntityCandidateSet, ...]:
        if not mentions:
            return ()
        operation = await self._ensure_operation()
        query = ",".join(dict.fromkeys(mention.strip() for mention in mentions if mention.strip()))
        if not query:
            return tuple(
                EntityCandidateSet(mention, ResolutionState.UNRESOLVED) for mention in mentions
            )
        try:
            async with httpx.AsyncClient(timeout=self._timeout) as client:
                response = await client.get(
                    f"{self._base_url}{operation.path}", params={operation.parameter: query}
                )
                response.raise_for_status()
                payload = cast(dict[str, Any], response.json())
        except (httpx.HTTPError, ValueError, TypeError) as error:
            raise GazetteerContractError("地名服务批量查询失败") from error
        result_items = cast(list[dict[str, Any]], payload.get("results", []))
        result_by_query: dict[str, dict[str, Any]] = {
            str(item["query"]): item for item in result_items if item.get("query") is not None
        }
        return tuple(
            self._parse_result(mention, result_by_query.get(mention)) for mention in mentions
        )

    async def _ensure_operation(self) -> _BatchOperation:
        if self._operation is not None:
            return self._operation
        try:
            async with httpx.AsyncClient(timeout=self._timeout) as client:
                response = await client.get(f"{self._base_url}/openapi.json")
                response.raise_for_status()
                self._discover(cast(dict[str, Any], response.json()))
        except (httpx.HTTPError, ValueError, TypeError) as error:
            raise GazetteerContractError("无法读取地名服务 OpenAPI") from error
        if self._operation is None:
            raise GazetteerContractError("OpenAPI 未发现支持 items 批量查询的操作")
        return self._operation

    def _discover(self, document: dict[str, Any]) -> None:
        info = document.get("info")
        info_data = cast(dict[str, Any], info) if isinstance(info, dict) else None
        self._version = info_data.get("version") if info_data is not None else None
        paths = document.get("paths")
        if not isinstance(paths, dict):
            raise GazetteerContractError("OpenAPI 缺少 paths")
        typed_paths = cast(dict[str, object], paths)
        for path, operations in typed_paths.items():
            if not isinstance(operations, dict):
                continue
            typed_operations = cast(dict[str, object], operations)
            for method, operation in typed_operations.items():
                if method.lower() != "get" or not isinstance(operation, dict):
                    continue
                typed_operation = cast(dict[str, Any], operation)
                parameters = typed_operation.get("parameters", [])
                if not isinstance(parameters, list):
                    continue
                for parameter in cast(list[object], parameters):
                    if (
                        isinstance(parameter, dict)
                        and cast(dict[str, Any], parameter).get("name") == "items"
                        and cast(dict[str, Any], parameter).get("in") == "query"
                    ):
                        self._operation = _BatchOperation(str(path), "items")
                        return

    @staticmethod
    def _parse_result(mention: str, result: dict[str, Any] | None) -> EntityCandidateSet:
        if not result or not result.get("matched"):
            return EntityCandidateSet(mention, ResolutionState.UNRESOLVED)
        raw_candidates: object = result.get("candidates") or result.get("semantic_candidates") or []
        candidates = cast(list[object], raw_candidates) if isinstance(raw_candidates, list) else []
        if not candidates and result.get("standard"):
            candidates = [result]
        parsed: list[EntityCandidate] = []
        for item in candidates:
            if not isinstance(item, dict):
                continue
            item_data = cast(dict[str, Any], item)
            if not item_data.get("standard"):
                continue
            standard = str(item_data["standard"])
            entity_type = str(item_data.get("type") or "unknown")
            entity = CanonicalEntity(
                entity_id=EntityId(uuid5(NAMESPACE_URL, f"shunde:remote:{entity_type}:{standard}")),
                standard_name=standard,
                entity_type=entity_type,
                aliases=(mention,),
            )
            confidence = item_data.get(
                "confidence", item_data.get("score", result.get("confidence", 0.0))
            )
            try:
                score = max(0.0, min(1.0, float(confidence)))
            except (TypeError, ValueError):
                score = 0.0
            evidence = tuple(
                str(value)
                for value in (
                    item_data.get("match"),
                    item_data.get("matched_text"),
                    result.get("layer"),
                )
                if value
            )
            parsed.append(EntityCandidate(entity, score, evidence))
        if not parsed:
            return EntityCandidateSet(mention, ResolutionState.UNRESOLVED)
        state = ResolutionState.RESOLVED if len(parsed) == 1 else ResolutionState.AMBIGUOUS
        return EntityCandidateSet(mention, state, tuple(parsed))
