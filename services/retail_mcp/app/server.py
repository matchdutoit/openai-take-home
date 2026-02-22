from __future__ import annotations

import os
from typing import Any, Optional

from fastmcp import FastMCP
from fastmcp.server.dependencies import get_http_headers
from starlette.requests import Request
from starlette.responses import JSONResponse

from services.retail_mcp.app.logic import (
    create_ticket_action,
    create_transfer_action,
    fetch_document,
    inventory_lookup_action,
    reserve_item_action,
    search_documents,
)
from services.retail_mcp.app.roles import resolve_role


def _role_from_headers() -> Optional[str]:
    try:
        headers = get_http_headers()
    except Exception:
        return None

    for key, value in headers.items():
        if key.lower() == "x-demo-role":
            return value
    return None


def _resolve_role(role_arg: Optional[str], default_role: str) -> str:
    return resolve_role(
        role_arg=role_arg,
        default_role=default_role,
        header_role=_role_from_headers(),
    )


def build_server() -> FastMCP:
    mcp = FastMCP(name="RetailOps MCP")

    @mcp.custom_route("/health", methods=["GET"], include_in_schema=False)
    async def health(_request: Request) -> JSONResponse:
        return JSONResponse({"status": "ok", "service": "retail_mcp"})

    @mcp.tool
    def search(query: str) -> dict[str, Any]:
        """Search internal markdown knowledge docs and return top citation candidates."""
        return search_documents(query=query, limit=5)

    @mcp.tool
    def fetch(id: str) -> dict[str, Any]:
        """Fetch a specific knowledge section by stable id for citation-ready content."""
        return fetch_document(section_id=id)

    @mcp.tool
    def inventory_lookup(
        sku: str,
        store_id: str,
        radius_miles: float = 25.0,
        role: Optional[str] = None,
    ) -> dict[str, Any]:
        """Lookup inventory availability across nearby stores."""
        return inventory_lookup_action(
            sku=sku,
            store_id=store_id,
            radius_miles=radius_miles,
            role=_resolve_role(role, default_role="associate"),
        )

    @mcp.tool
    def reserve_item(
        sku: str,
        store_id: str,
        qty: int,
        confirm: bool = False,
        role: Optional[str] = None,
    ) -> dict[str, Any]:
        """Create preview/confirmed reserve action in RetailCore."""
        return reserve_item_action(
            sku=sku,
            store_id=store_id,
            qty=qty,
            confirm=confirm,
            role=_resolve_role(role, default_role="associate"),
        )

    @mcp.tool
    def create_transfer(
        from_store: str,
        to_store: str,
        sku: str,
        qty: int,
        confirm: bool = False,
        role: Optional[str] = None,
    ) -> dict[str, Any]:
        """Create preview/confirmed transfer action in RetailCore."""
        return create_transfer_action(
            from_store=from_store,
            to_store=to_store,
            sku=sku,
            qty=qty,
            confirm=confirm,
            role=_resolve_role(role, default_role="merch"),
        )

    @mcp.tool
    def create_ticket(
        store_id: str,
        category: str,
        severity: str,
        description: str,
        role: Optional[str] = None,
    ) -> dict[str, Any]:
        """Create a support ticket in RetailCore."""
        return create_ticket_action(
            store_id=store_id,
            category=category,
            severity=severity,
            description=description,
            role=_resolve_role(role, default_role="support"),
        )

    return mcp


mcp = build_server()


def main() -> None:
    transport = os.getenv("FASTMCP_TRANSPORT", "http")
    host = os.getenv("FASTMCP_HOST", "0.0.0.0")
    port = int(os.getenv("FASTMCP_PORT", os.getenv("PORT", "8081")))
    path = os.getenv("FASTMCP_PATH", "/mcp")

    if transport == "http":
        mcp.run(transport="http", host=host, port=port, path=path)
        return
    if transport == "sse":
        mcp.run(transport="sse", host=host, port=port, path=path)
        return
    if transport == "stdio":
        mcp.run(transport="stdio")
        return

    raise ValueError(f"Unsupported FASTMCP_TRANSPORT '{transport}'")


if __name__ == "__main__":
    main()
