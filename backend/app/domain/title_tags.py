"""Deterministic title facts; bracketed text is not inferred as a department."""

import re

TITLE_TAG_WHITELIST = frozenset({"急", "公众号自助", "小程序自助", "城管"})
_TAG_PATTERN = re.compile(r"(?:【([^【】]+)】|[（(]([^（）()]+)[）)])")


def parse_title_tags(raw_title: str | None) -> tuple[str, ...]:
    if not raw_title:
        return ()
    tags: list[str] = []
    for match in _TAG_PATTERN.finditer(raw_title):
        value = next(group for group in match.groups() if group is not None).strip()
        if value in TITLE_TAG_WHITELIST and value not in tags:
            tags.append(value)
    return tuple(tags)
