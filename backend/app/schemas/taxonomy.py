"""Taxonomy API schemas."""

from __future__ import annotations

from datetime import datetime
from typing import Literal
from uuid import UUID

from pydantic import BaseModel, Field

TaxonomyLevelLiteral = Literal["1", "2", "3"]
TaxonomyVersionStatusLiteral = Literal["draft", "active", "retired"]
DisplayNameSourceLiteral = Literal["printed", "level_2_inherited", "level_1_inherited"]


class TaxonomyVersionResponse(BaseModel):
    version_id: UUID
    standard_name: str
    source_sha256: str
    extracted_resource_sha256: str
    status: TaxonomyVersionStatusLiteral
    activated_at: datetime | None
    level_1_count: int
    level_2_count: int
    level_3_count: int
    distinct_level_3_code_count: int
    duplicate_printed_codes: list[str]
    empty_level_3_name_count: int


class TaxonomyNodeResponse(BaseModel):
    node_id: str
    taxonomy_version_id: UUID
    level: TaxonomyLevelLiteral
    printed_code: str
    printed_name: str | None
    parent_node_id: str | None
    full_path: list[str]
    remark: str | None
    source_page: int | None
    source_anomaly: str | None
    display_name: str
    display_name_source: DisplayNameSourceLiteral


class TaxonomyTreeResponse(BaseModel):
    version: TaxonomyVersionResponse
    nodes: list[TaxonomyNodeResponse]


class TaxonomyStatsResponse(BaseModel):
    level_1_count: int
    level_2_count: int
    level_3_count: int
    distinct_level_3_code_count: int
    duplicate_printed_codes: list[tuple[str, int]]
    empty_level_3_name_count: int
    duplicate_printed_code_paths: list[tuple[str, list[str]]]


class CodeResolutionResponse(BaseModel):
    printed_code: str
    ambiguous: bool
    resolved_node: TaxonomyNodeResponse | None
    candidates: list[TaxonomyNodeResponse]


class TaxonomyListResponse(BaseModel):
    items: list[TaxonomyVersionResponse]


class TaxonomySeedRequest(BaseModel):
    """种子请求：从 reference CSV 创建 draft 并激活。"""

    csv_path: str = Field(
        ...,
        description="db44t2479-2024-appendix-a.csv 的绝对路径",
    )
    activate: bool = Field(
        True,
        description="创建后是否立即激活（必须通过完整性校验）",
    )


class TaxonomySeedResponse(BaseModel):
    version: TaxonomyVersionResponse
    activated: bool
    validation_errors: list[str] | None = None
