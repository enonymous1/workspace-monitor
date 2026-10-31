"""Shared pagination for list endpoints.

v2.0 copy-pasted ``limit``/``offset`` Query parameters into seven
endpoints. Changing the cap meant changing seven places. There is
now exactly one definition; endpoints declare
``page: Pagination = Depends(pagination)`` and use
``page.limit`` / ``page.offset``.
"""

from __future__ import annotations

from dataclasses import dataclass

from fastapi import Query


@dataclass(frozen=True)
class Pagination:
    limit: int = 100
    offset: int = 0


def pagination(
    limit: int = Query(100, ge=1, le=500),
    offset: int = Query(0, ge=0),
) -> Pagination:
    return Pagination(limit=limit, offset=offset)
