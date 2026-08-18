from collections.abc import AsyncGenerator
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from backend.app.api.agent import router as agent_router
from backend.app.api.analysis import router as analysis_router
from backend.app.api.attachments import router as attachments_router
from backend.app.api.catalog import router as catalog_router
from backend.app.api.entities import router as entities_router
from backend.app.api.health import router as health_router
from backend.app.api.imports import router as imports_router
from backend.app.api.review import router as review_router
from backend.app.application.handlers.imports import ImportHandler
from backend.app.application.services.agent import AgentOrchestrator
from backend.app.application.services.analysis_jobs import AnalysisJobService
from backend.app.application.services.catalog import CatalogService
from backend.app.application.services.review import EventReviewService
from backend.app.config import get_settings
from backend.app.infrastructure.attachments import LocalAttachmentStore
from backend.app.infrastructure.db.agent import AgentRepository
from backend.app.infrastructure.db.catalog import SQLAlchemyCatalogRepository
from backend.app.infrastructure.db.imports import SQLAlchemyImportRepository
from backend.app.infrastructure.db.review import SQLAlchemyEventReviewRepository
from backend.app.infrastructure.db.session import create_engine, create_session_factory
from backend.app.infrastructure.export import SQLAlchemyCSVExporter
from backend.app.infrastructure.health import DependencyHealthProbe
from backend.app.infrastructure.imports import PolarsTabularReader, SourceStager
from backend.app.infrastructure.knowledge.gazetteer import GazetteerHttpAdapter
from backend.app.infrastructure.knowledge.resolver import RuntimeEntityResolver
from backend.app.infrastructure.knowledge.snapshot import (
    GazetteerSnapshotBuilder,
    RuntimeSnapshotStore,
)


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncGenerator[None]:
    settings = get_settings()
    engine = create_engine(settings)
    session_factory = create_session_factory(engine)
    catalog_repository = SQLAlchemyCatalogRepository(
        session_factory, settings.analysis_pipeline_version
    )
    app.state.catalog_service = CatalogService(catalog_repository)
    app.state.agent_orchestrator = AgentOrchestrator.create(
        AgentRepository(session_factory), settings
    )
    analysis_job_service = AnalysisJobService(settings, session_factory)
    app.state.analysis_job_service = analysis_job_service
    app.state.review_service = EventReviewService(SQLAlchemyEventReviewRepository(session_factory))
    app.state.exporter = SQLAlchemyCSVExporter(session_factory)
    app.state.attachment_store = LocalAttachmentStore(
        settings.runtime_dir / "attachments", settings.attachment_max_bytes
    )
    app.state.health_probe = DependencyHealthProbe(engine, settings)
    app.state.import_handler = ImportHandler(
        PolarsTabularReader(), SQLAlchemyImportRepository(session_factory)
    )
    app.state.source_stager = SourceStager(settings.runtime_dir)
    app.state.entity_resolver = None
    if settings.gazetteer_home is not None or settings.gazetteer_database_path is not None:
        database_path = settings.gazetteer_database_path or (
            settings.gazetteer_home / "地名服务" / "shunde_places.db"
            if settings.gazetteer_home is not None
            else None
        )
        if database_path is None:
            raise RuntimeError("gazetteer_home or gazetteer_database_path must be configured")
        snapshot = GazetteerSnapshotBuilder(database_path).build()
        RuntimeSnapshotStore(settings.gazetteer_snapshot_path).save(snapshot)
        remote = GazetteerHttpAdapter(
            str(settings.gazetteer_api_base_url), settings.dependency_timeout_seconds
        )
        app.state.entity_resolver = RuntimeEntityResolver(snapshot, remote)
    await analysis_job_service.resume_incomplete()
    yield
    await analysis_job_service.shutdown()
    await engine.dispose()


def create_app() -> FastAPI:
    settings = get_settings()
    application = FastAPI(title=settings.app_name, version="0.1.0", lifespan=lifespan)
    application.add_middleware(
        CORSMiddleware,
        allow_origins=list(settings.cors_origins),
        allow_credentials=False,
        allow_methods=["GET", "POST", "PUT", "PATCH", "DELETE"],
        allow_headers=["Content-Type", "X-Correlation-ID"],
    )
    application.include_router(health_router)
    application.include_router(analysis_router)
    application.include_router(attachments_router)
    application.include_router(imports_router)
    application.include_router(entities_router)
    application.include_router(review_router)
    application.include_router(catalog_router)
    application.include_router(agent_router)
    return application


app = create_app()
