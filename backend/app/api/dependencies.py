from typing import Annotated

from fastapi import Depends, Request

from backend.app.application.handlers.health import HealthCheckHandler
from backend.app.application.handlers.imports import ImportHandler
from backend.app.application.services.agent import AgentOrchestrator
from backend.app.application.services.analysis_jobs import AnalysisJobService
from backend.app.application.services.catalog import CatalogService
from backend.app.application.services.review import EventReviewService
from backend.app.domain.attachments import AttachmentStore
from backend.app.domain.ports.export import Exporter
from backend.app.infrastructure.health import DependencyHealthProbe
from backend.app.infrastructure.imports import SourceStager
from backend.app.infrastructure.knowledge.resolver import RuntimeEntityResolver


def get_health_probe(request: Request) -> DependencyHealthProbe:
    return request.app.state.health_probe


HealthProbeDependency = Annotated[DependencyHealthProbe, Depends(get_health_probe)]


def get_health_handler() -> HealthCheckHandler:
    return HealthCheckHandler()


HealthHandlerDependency = Annotated[HealthCheckHandler, Depends(get_health_handler)]


def get_import_handler(request: Request) -> ImportHandler:
    return request.app.state.import_handler


ImportHandlerDependency = Annotated[ImportHandler, Depends(get_import_handler)]


def get_source_stager(request: Request) -> SourceStager:
    return request.app.state.source_stager


SourceStagerDependency = Annotated[SourceStager, Depends(get_source_stager)]


def get_entity_resolver(request: Request) -> RuntimeEntityResolver | None:
    return getattr(request.app.state, "entity_resolver", None)


ResolverDependency = Annotated[RuntimeEntityResolver | None, Depends(get_entity_resolver)]


def get_catalog_service(request: Request) -> CatalogService:
    return request.app.state.catalog_service


CatalogServiceDependency = Annotated[CatalogService, Depends(get_catalog_service)]


def get_agent_orchestrator(request: Request) -> AgentOrchestrator:
    return request.app.state.agent_orchestrator


AgentOrchestratorDependency = Annotated[AgentOrchestrator, Depends(get_agent_orchestrator)]


def get_analysis_job_service(request: Request) -> AnalysisJobService:
    return request.app.state.analysis_job_service


AnalysisJobServiceDependency = Annotated[AnalysisJobService, Depends(get_analysis_job_service)]


def get_review_service(request: Request) -> EventReviewService:
    return request.app.state.review_service


ReviewServiceDependency = Annotated[EventReviewService, Depends(get_review_service)]


def get_exporter(request: Request) -> Exporter:
    return request.app.state.exporter


ExporterDependency = Annotated[Exporter, Depends(get_exporter)]


def get_attachment_store(request: Request) -> AttachmentStore:
    return request.app.state.attachment_store


AttachmentStoreDependency = Annotated[AttachmentStore, Depends(get_attachment_store)]
