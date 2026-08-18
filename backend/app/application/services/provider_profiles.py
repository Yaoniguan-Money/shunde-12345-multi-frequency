import time
from collections.abc import Awaitable, Callable
from dataclasses import dataclass
from datetime import UTC, datetime
from typing import cast

from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from backend.app.config import Settings
from backend.app.domain.taxonomy import (
    ClassificationDecision,
    ClassificationOutcome,
    TaxonomyNodeId,
    TaxonomyTree,
)
from backend.app.domain.types import (
    EmbeddingRequest,
    LLMRequest,
    ProviderMode,
    ProviderRoute,
)
from backend.app.infrastructure.ai.factory import AIProviderBundle, build_provider_bundle
from backend.app.infrastructure.db.models import ProviderProfile as ProviderProfileModel
from backend.app.infrastructure.taxonomy.validator import TaxonomyClassificationValidator
from backend.app.schemas.ai import SameEventResponse, WorkOrderUnderstanding
from backend.app.schemas.provider_profiles import (
    ProviderDeploymentKind,
    ProviderProfileResponse,
    ProviderValidationResponse,
    ProviderValidationStage,
    ProviderValidationStatus,
)


@dataclass(frozen=True, slots=True)
class _ProfileDefinition:
    profile_id: str
    deployment_kind: str
    display_name: str


class ProviderProfileService:
    """Expose safe provider choices and run real synthetic capability validation."""

    _profiles = (
        _ProfileDefinition("local-default", "local", "本地模型"),
        _ProfileDefinition("cloud-qwen", "cloud", "云端模型（千问，已适配）"),
    )

    def __init__(
        self,
        settings: Settings,
        taxonomy_tree: TaxonomyTree | None = None,
        session_factory: async_sessionmaker[AsyncSession] | None = None,
    ) -> None:
        self._settings = settings
        self._taxonomy_tree = taxonomy_tree
        self._session_factory = session_factory
        self._validation: dict[str, ProviderProfileResponse] = {}

    async def ensure_defaults(self) -> None:
        if self._session_factory is None:
            return
        async with self._session_factory() as session:
            async with session.begin():
                for definition in self._profiles:
                    profile = await self._profile_response(definition)
                    stored = await session.get(ProviderProfileModel, definition.profile_id)
                    if stored is None:
                        session.add(_profile_model(profile))
                    else:
                        _update_profile_model(stored, profile)

    async def list_profiles(self) -> list[ProviderProfileResponse]:
        await self.ensure_defaults()
        return [await self._profile_response(definition) for definition in self._profiles]

    async def validate(self, profile_id: str) -> ProviderValidationResponse:
        definition = next(
            (profile for profile in self._profiles if profile.profile_id == profile_id), None
        )
        if definition is None:
            raise LookupError(f"provider profile not found: {profile_id}")
        mode = ProviderMode.LOCAL if definition.deployment_kind == "local" else ProviderMode.REMOTE
        settings = self._settings.model_copy(
            update={
                "ai_provider_mode": mode,
                **_model_override_update(self._settings, definition.deployment_kind),
            }
        )
        stages: list[ProviderValidationStage] = []
        try:
            bundle = build_provider_bundle(settings)
            await self._run_stage(stages, "health", bundle.health)
            route = ProviderRoute.LOCAL if mode is ProviderMode.LOCAL else ProviderRoute.REMOTE
            await self._run_structured_stage(bundle, route, stages)
            status = "validated"
            profile = await self._profile_response(definition, status=status)
        except Exception as error:
            stages.append(
                ProviderValidationStage(
                    name="validation",
                    status="failed",
                    latency_ms=0,
                    error=_safe_error(error),
                )
            )
            profile = await self._profile_response(definition, status="validation_failed")
        self._validation[profile_id] = profile
        await self._persist_profile(profile)
        return ProviderValidationResponse(profile=profile, stages=stages)

    async def require_validated(self, profile_id: str | None) -> ProviderProfileResponse:
        if profile_id is None:
            raise ValueError("provider_profile_id is required")
        profile = self._validation.get(profile_id)
        if profile is None and self._session_factory is not None:
            async with self._session_factory() as session:
                stored = await session.get(ProviderProfileModel, profile_id)
                if stored is not None:
                    profile = _profile_response_from_model(stored)
                    self._validation[profile_id] = profile
        if profile is None or profile.validation_status != "validated":
            raise ValueError(f"provider profile is not validated: {profile_id}")
        return profile

    async def _profile_response(
        self,
        definition: _ProfileDefinition,
        *,
        status: str | None = None,
    ) -> ProviderProfileResponse:
        settings = self._settings.model_copy(
            update={
                "ai_provider_mode": (
                    ProviderMode.LOCAL
                    if definition.deployment_kind == "local"
                    else ProviderMode.REMOTE
                ),
                **_model_override_update(self._settings, definition.deployment_kind),
            }
        )
        configured = _is_configured(settings, definition.deployment_kind)
        previous = self._validation.get(definition.profile_id)
        if previous is None and self._session_factory is not None:
            async with self._session_factory() as session:
                stored = await session.get(ProviderProfileModel, definition.profile_id)
                if stored is not None:
                    previous = _profile_response_from_model(stored)
        configuration_version = _configuration_version(settings, definition.deployment_kind)
        same_configuration = (
            previous is not None and previous.configuration_version == configuration_version
        )
        previous_last_validated_at = (
            previous.last_validated_at if same_configuration and previous is not None else None
        )
        return ProviderProfileResponse(
            profile_id=definition.profile_id,
            deployment_kind=definition.deployment_kind,  # type: ignore[arg-type]
            display_name=definition.display_name,
            configured=configured,
            validation_status=(
                status
                or (
                    previous.validation_status
                    if same_configuration and previous is not None
                    else "configured"
                )
            ),  # type: ignore[arg-type]
            last_validated_at=(
                datetime.now(UTC) if status == "validated" else previous_last_validated_at
            ),
            model_display_name=(
                settings.ai_local_llm_model_id
                if definition.deployment_kind == "local"
                else settings.ai_remote_llm_model_id
            ),
            service_description=(
                "本机模型服务，地址由服务端配置管理"
                if definition.deployment_kind == "local"
                else "云端千问兼容服务，地址和密钥不向浏览器暴露"
            ),
            configuration_version=_configuration_version(settings, definition.deployment_kind),
        )

    async def _persist_profile(self, profile: ProviderProfileResponse) -> None:
        if self._session_factory is None:
            return
        async with self._session_factory() as session:
            async with session.begin():
                stored = await session.get(ProviderProfileModel, profile.profile_id)
                if stored is None:
                    session.add(_profile_model(profile))
                else:
                    _update_profile_model(stored, profile)

    async def _run_structured_stage(
        self,
        bundle: AIProviderBundle,
        route: ProviderRoute,
        stages: list[ProviderValidationStage],
    ) -> None:
        started = time.perf_counter()
        understanding_request = LLMRequest(
            request_id="provider-validation-understanding",
            prompt="投诉：凤城某项目夜间施工扰民，请处理。",
            output_schema=WorkOrderUnderstanding.model_json_schema(),
            schema_version="provider-validation.v1",
            pipeline_version="provider-validation.v1",
            route=route,
        )
        outputs = await bundle.llm.generate_batch((understanding_request,))
        WorkOrderUnderstanding.model_validate(outputs[0].structured_output)
        stages.append(
            ProviderValidationStage(
                name="structured_understanding",
                status="passed",
                latency_ms=_elapsed_ms(started),
                model_id=outputs[0].trace.model_id,
            )
        )

        started = time.perf_counter()
        embedding = await bundle.embeddings.embed_batch(
            (
                EmbeddingRequest(
                    item_id="provider-validation-embedding",
                    text="凤城某项目夜间施工扰民",
                    schema_version="provider-validation.v1",
                    pipeline_version="provider-validation.v1",
                    route=route,
                ),
            )
        )
        if not embedding or not embedding[0].vector:
            raise ValueError("embedding returned an empty vector")
        stages.append(
            ProviderValidationStage(
                name="embedding",
                status="passed",
                latency_ms=_elapsed_ms(started),
                model_id=embedding[0].model_id,
            )
        )

        started = time.perf_counter()
        same_event_request = LLMRequest(
            request_id="provider-validation-same-event",
            prompt="判断两条相同项目、相同地点、相同问题的投诉是否为同一事件，只输出 JSON。",
            output_schema=SameEventResponse.model_json_schema(),
            schema_version="provider-validation.v1",
            pipeline_version="provider-validation.v1",
            route=route,
        )
        outputs = await bundle.llm.generate_batch((same_event_request,))
        SameEventResponse.model_validate(outputs[0].structured_output)
        stages.append(
            ProviderValidationStage(
                name="same_event_structured",
                status="passed",
                latency_ms=_elapsed_ms(started),
                model_id=outputs[0].trace.model_id,
            )
        )

        if self._taxonomy_tree is not None:
            node = next(
                (node for node in self._taxonomy_tree.nodes if node.level.value == "3"), None
            )
            if node is not None:
                outcome = ClassificationOutcome(
                    classification_node_id=TaxonomyNodeId(node.node_id),
                    candidate_node_ids=(TaxonomyNodeId(node.node_id),),
                    decision=ClassificationDecision.RESOLVED,
                    confidence=1.0,
                    evidence_refs=("synthetic-validation",),
                    reason="synthetic taxonomy contract",
                    provider_profile=None,
                    taxonomy_version=self._taxonomy_tree.version.standard_name,
                )
                await TaxonomyClassificationValidator().validate(outcome, self._taxonomy_tree)
                stages.append(
                    ProviderValidationStage(
                        name="taxonomy_validation",
                        status="passed",
                        latency_ms=0,
                        model_id=None,
                    )
                )

    @staticmethod
    async def _run_stage(
        stages: list[ProviderValidationStage],
        name: str,
        operation: Callable[[], Awaitable[object]],
    ) -> None:
        started = time.perf_counter()
        await operation()
        stages.append(
            ProviderValidationStage(name=name, status="passed", latency_ms=_elapsed_ms(started))
        )


def _is_configured(settings: Settings, deployment_kind: str) -> bool:
    if deployment_kind == "local":
        return bool(
            (settings.ai_local_llm_base_url or settings.model_api_base_url)
            and (settings.ai_local_llm_model_id or settings.llm_model_id)
            and (settings.ai_local_embedding_base_url or settings.embedding_api_base_url)
            and (settings.ai_local_embedding_model_id or settings.embedding_model_id)
        )
    return bool(
        settings.ai_remote_base_url
        and settings.ai_remote_llm_model_id
        and settings.ai_remote_embedding_model_id
        and settings.ai_remote_api_key
    )


def _profile_model(profile: ProviderProfileResponse) -> ProviderProfileModel:
    return ProviderProfileModel(
        profile_id=profile.profile_id,
        deployment_kind=profile.deployment_kind,
        display_name=profile.display_name,
        configured=profile.configured,
        validation_status=profile.validation_status,
        last_validated_at=profile.last_validated_at,
        model_display_name=profile.model_display_name,
        service_description=profile.service_description,
        configuration_version=profile.configuration_version,
        adapter_config={"profile_id": profile.profile_id},
    )


def _profile_response_from_model(model: ProviderProfileModel) -> ProviderProfileResponse:
    return ProviderProfileResponse(
        profile_id=model.profile_id,
        deployment_kind=cast(ProviderDeploymentKind, model.deployment_kind),
        display_name=model.display_name,
        configured=model.configured,
        validation_status=cast(ProviderValidationStatus, model.validation_status),
        last_validated_at=model.last_validated_at,
        model_display_name=model.model_display_name,
        service_description=model.service_description,
        configuration_version=model.configuration_version,
    )


def _configuration_version(settings: Settings, deployment_kind: str) -> str:
    endpoint = (
        settings.ai_local_llm_base_url
        if deployment_kind == "local"
        else settings.ai_remote_base_url
    )
    model = (
        settings.ai_local_llm_model_id
        if deployment_kind == "local"
        else settings.ai_remote_llm_model_id
    )
    return f"{deployment_kind}:{endpoint or 'unconfigured'}:{model or 'unconfigured'}"


def _model_override_update(settings: Settings, deployment_kind: str) -> dict[str, object]:
    if deployment_kind == "local":
        return {}
    return {
        "ai_remote_llm_model_id": (
            settings.ai_remote_flash_llm_model_id or settings.ai_remote_llm_model_id
        )
    }


def _update_profile_model(stored: ProviderProfileModel, profile: ProviderProfileResponse) -> None:
    stored.deployment_kind = profile.deployment_kind
    stored.display_name = profile.display_name
    stored.configured = profile.configured
    stored.validation_status = profile.validation_status
    stored.last_validated_at = profile.last_validated_at
    stored.model_display_name = profile.model_display_name
    stored.service_description = profile.service_description
    stored.configuration_version = profile.configuration_version


def _elapsed_ms(started: float) -> int:
    return round((time.perf_counter() - started) * 1000)


def _safe_error(error: Exception) -> str:
    return str(error).replace("Authorization", "[redacted]")[:500]
