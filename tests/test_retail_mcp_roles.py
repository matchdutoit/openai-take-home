from __future__ import annotations

from services.retail_mcp.app.roles import resolve_role


def test_resolve_role_prefers_header():
    assert resolve_role(role_arg="associate", default_role="merch", header_role="support") == "support"


def test_resolve_role_uses_argument_without_header():
    assert resolve_role(role_arg="associate", default_role="support", header_role=None) == "associate"


def test_resolve_role_uses_default_when_missing():
    assert resolve_role(role_arg=None, default_role="merch", header_role=None) == "merch"
