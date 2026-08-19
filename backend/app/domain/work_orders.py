"""Stable business identities derived from immutable work-order source fields."""

import re

_CHILD_WORK_ORDER_SUFFIX = re.compile(r"-(?:\d{2})$")


def canonical_root_work_order_number(external_work_order_number: str | None) -> str | None:
    """Return the parent identity for explicit ``-01`` style child work orders.

    Only a final hyphen plus exactly two digits is a child suffix.  Other
    hyphenated identifiers are retained verbatim so this derivation never
    truncates an ordinary source number.
    """

    if external_work_order_number is None:
        return None
    number = external_work_order_number.strip()
    if not number:
        return None
    return _CHILD_WORK_ORDER_SUFFIX.sub("", number)
