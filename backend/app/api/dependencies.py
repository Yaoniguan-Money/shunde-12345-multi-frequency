from typing import Annotated

from fastapi import Depends, Request

from backend.app.application.handlers.health import HealthCheckHandler
from backend.app.infrastructure.health import DependencyHealthProbe


def get_health_probe(request: Request) -> DependencyHealthProbe:
    return request.app.state.health_probe


HealthProbeDependency = Annotated[DependencyHealthProbe, Depends(get_health_probe)]


def get_health_handler() -> HealthCheckHandler:
    return HealthCheckHandler()


HealthHandlerDependency = Annotated[HealthCheckHandler, Depends(get_health_handler)]
