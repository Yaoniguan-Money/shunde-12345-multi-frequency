from httpx import ASGITransport, AsyncClient

from backend.app.api.dependencies import get_health_probe
from backend.app.main import create_app
from backend.app.schemas.health import DependencyState, DependencyStatus, HealthSnapshot


class FakeHealthProbe:
    def __init__(self, *, database_up: bool) -> None:
        self._database_up = database_up

    async def snapshot(self) -> HealthSnapshot:
        return HealthSnapshot(
            database=DependencyStatus(
                state=DependencyState.UP if self._database_up else DependencyState.DOWN
            ),
            gazetteer=DependencyStatus(state=DependencyState.UP, version="1.0"),
            local_model=DependencyStatus(state=DependencyState.NOT_CONFIGURED),
        )


async def test_liveness_does_not_claim_dependency_readiness() -> None:
    app = create_app()
    app.dependency_overrides[get_health_probe] = lambda: FakeHealthProbe(database_up=False)
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        response = await client.get("/health/live")
    assert response.status_code == 200
    assert response.json() == {"status": "alive"}


async def test_readiness_returns_503_when_database_is_down() -> None:
    app = create_app()
    app.dependency_overrides[get_health_probe] = lambda: FakeHealthProbe(database_up=False)
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        response = await client.get("/health/ready")
    assert response.status_code == 503
    assert response.json()["status"] == "not_ready"


async def test_dependencies_report_unconfigured_local_model() -> None:
    app = create_app()
    app.dependency_overrides[get_health_probe] = lambda: FakeHealthProbe(database_up=True)
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        response = await client.get("/health/dependencies")
    assert response.status_code == 200
    assert response.json()["local_model"]["state"] == "not_configured"
