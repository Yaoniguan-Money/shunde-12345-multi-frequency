"""Taxonomy 基础设施包。

包含 CSV 加载器、完整性校验和代码/路径解析器。
"""

from backend.app.infrastructure.taxonomy.loader import (
    load_appendix_a,
    validate_integrity,
)
from backend.app.infrastructure.taxonomy.resolver import (
    resolve_by_full_path,
    resolve_by_printed_code,
)

__all__ = [
    "load_appendix_a",
    "resolve_by_full_path",
    "resolve_by_printed_code",
    "validate_integrity",
]
