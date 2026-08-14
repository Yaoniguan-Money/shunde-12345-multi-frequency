from backend.app.schemas.health import (
    DependenciesResponse,
    DependencyState,
    HealthSnapshot,
    ReadinessResponse,
)


class HealthCheckHandler:
    def readiness(self, snapshot: HealthSnapshot) -> ReadinessResponse:
        ready = snapshot.database.state is DependencyState.UP
        return ReadinessResponse(
            status="ready" if ready else "not_ready",
            database=snapshot.database,
        )

    def dependencies(self, snapshot: HealthSnapshot) -> DependenciesResponse:
        states = (snapshot.database.state, snapshot.gazetteer.state, snapshot.local_model.state)
        degraded = any(state is DependencyState.DOWN for state in states)
        return DependenciesResponse(
            status="degraded" if degraded else "ok",
            database=snapshot.database,
            gazetteer=snapshot.gazetteer,
            local_model=snapshot.local_model,
        )
