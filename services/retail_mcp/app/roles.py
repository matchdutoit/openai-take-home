from __future__ import annotations

from typing import Optional


def resolve_role(
    role_arg: Optional[str],
    default_role: str,
    header_role: Optional[str] = None,
) -> str:
    if header_role:
        return header_role
    if role_arg:
        return role_arg
    return default_role
