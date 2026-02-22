#!/usr/bin/env python3
from __future__ import annotations

import json
import os
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from services.retail_mcp.app.logic import (  # noqa: E402
    create_ticket_action,
    create_transfer_action,
    inventory_lookup_action,
    reserve_item_action,
)

HERO_SKU = os.getenv("HERO_SKU", "AST-LIN-BLZ-SND-M")
QUERY_STORE = os.getenv("QUERY_STORE_ID", "ST001")
LOOKUP_RADIUS_MILES = float(os.getenv("LOOKUP_RADIUS_MILES", "25"))
DEFAULT_TICKET_CATEGORY = os.getenv("GOLDEN_TICKET_CATEGORY", "POS Sync Failure")
DEFAULT_TICKET_SEVERITY = os.getenv("GOLDEN_TICKET_SEVERITY", "high")
RETAILCORE_BASE_URL = os.getenv("RETAILCORE_BASE_URL", "http://localhost:8080")


def _pick_store_for_reserve(stores: list[dict[str, object]], query_store: str) -> str:
    for store in stores:
        if store.get("store_id") == query_store:
            continue
        available = int(store.get("available", 0))
        if available >= 1:
            return str(store["store_id"])
    raise RuntimeError("No nearby store with available stock for reserve action.")


def _pick_store_for_transfer(stores: list[dict[str, object]], query_store: str) -> str:
    for store in stores:
        if store.get("store_id") == query_store:
            continue
        on_hand = int(store.get("on_hand", 0))
        if on_hand >= 1:
            return str(store["store_id"])
    raise RuntimeError("No nearby store with on_hand inventory for transfer action.")


def main() -> None:
    outputs: dict[str, object] = {}

    lookup = inventory_lookup_action(
        sku=HERO_SKU,
        store_id=QUERY_STORE,
        radius_miles=LOOKUP_RADIUS_MILES,
        role="associate",
        base_url=RETAILCORE_BASE_URL,
    )
    outputs["inventory_lookup"] = lookup
    nearby_stores = lookup.get("stores", [])
    if not isinstance(nearby_stores, list):
        raise RuntimeError("Unexpected inventory_lookup response format.")

    reserve_store = _pick_store_for_reserve(nearby_stores, QUERY_STORE)
    reserve_result = reserve_item_action(
        sku=HERO_SKU,
        store_id=reserve_store,
        qty=1,
        confirm=True,
        role="associate",
        base_url=RETAILCORE_BASE_URL,
    )
    outputs["reserve_item"] = reserve_result

    post_reserve_lookup = inventory_lookup_action(
        sku=HERO_SKU,
        store_id=QUERY_STORE,
        radius_miles=LOOKUP_RADIUS_MILES,
        role="merch",
        base_url=RETAILCORE_BASE_URL,
    )
    transfer_source = _pick_store_for_transfer(post_reserve_lookup.get("stores", []), QUERY_STORE)
    transfer_result = create_transfer_action(
        from_store=transfer_source,
        to_store=QUERY_STORE,
        sku=HERO_SKU,
        qty=1,
        confirm=True,
        role="merch",
        base_url=RETAILCORE_BASE_URL,
    )
    outputs["create_transfer"] = transfer_result

    ticket_result = create_ticket_action(
        store_id=QUERY_STORE,
        category=DEFAULT_TICKET_CATEGORY,
        severity=DEFAULT_TICKET_SEVERITY,
        description=(
            "Golden path demo ticket: recurring POS synchronization failure during peak traffic."
        ),
        role="support",
        base_url=RETAILCORE_BASE_URL,
    )
    outputs["create_ticket"] = ticket_result

    print(json.dumps(outputs, indent=2))


if __name__ == "__main__":
    main()
