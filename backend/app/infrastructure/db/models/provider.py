from datetime import datetime

from sqlalchemy import DateTime, String
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from backend.app.infrastructure.db.models.base import Base, TimestampMixin


class ProviderProfile(TimestampMixin, Base):
    __tablename__ = "provider_profiles"

    profile_id: Mapped[str] = mapped_column(String(128), primary_key=True)
    deployment_kind: Mapped[str] = mapped_column(String(16), nullable=False)
    display_name: Mapped[str] = mapped_column(String(255), nullable=False)
    configured: Mapped[bool] = mapped_column(nullable=False, default=False)
    validation_status: Mapped[str] = mapped_column(String(32), nullable=False)
    last_validated_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    model_display_name: Mapped[str | None] = mapped_column(String(255))
    service_description: Mapped[str] = mapped_column(String(1000), nullable=False)
    configuration_version: Mapped[str] = mapped_column(String(255), nullable=False)
    adapter_config: Mapped[dict[str, object]] = mapped_column(JSONB, nullable=False, default=dict)
