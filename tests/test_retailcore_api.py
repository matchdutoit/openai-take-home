from __future__ import annotations

import importlib
import os
import subprocess
import sys
from pathlib import Path

import pytest
from fastapi.testclient import TestClient


PROJECT_ROOT = Path(__file__).resolve().parents[1]
GENERATOR_SCRIPT = PROJECT_ROOT / "scripts" / "generate_demo_pack.py"
DATA_DIR = PROJECT_ROOT / "data"


def _headers(role: str) -> dict[str, str]:
    return {"X-DEMO-ROLE": role}


@pytest.fixture()
def client(tmp_path):
    subprocess.run([sys.executable, str(GENERATOR_SCRIPT)], cwd=PROJECT_ROOT, check=True)

    original_data_dir = os.environ.get("RETAILCORE_DATA_DIR")
    original_db_path = os.environ.get("RETAILCORE_DB_PATH")
    db_path = tmp_path / "retailcore-test.db"
    os.environ["RETAILCORE_DATA_DIR"] = str(DATA_DIR)
    os.environ["RETAILCORE_DB_PATH"] = str(db_path)

    try:
        retailcore_main = importlib.import_module("services.retailcore.app.main")
        retailcore_main = importlib.reload(retailcore_main)
        app = retailcore_main.create_app()
        with TestClient(app) as test_client:
            yield test_client
    finally:
        if original_data_dir is None:
            os.environ.pop("RETAILCORE_DATA_DIR", None)
        else:
            os.environ["RETAILCORE_DATA_DIR"] = original_data_dir

        if original_db_path is None:
            os.environ.pop("RETAILCORE_DB_PATH", None)
        else:
            os.environ["RETAILCORE_DB_PATH"] = original_db_path


def test_health_endpoint(client: TestClient):
    response = client.get("/health")
    assert response.status_code == 200
    assert response.json() == {"status": "ok"}


def test_auth_header_required_for_protected_endpoints(client: TestClient):
    response = client.get("/products/AST-LIN-BLZ-SND-M")
    assert response.status_code == 401


def test_get_product_by_sku(client: TestClient):
    response = client.get("/products/AST-LIN-BLZ-SND-M", headers=_headers("associate"))
    assert response.status_code == 200
    body = response.json()
    assert body["product_name"] == "Aster Linen Blazer"
    assert body["style_id"] == "AST-LIN-BLZ"


def test_inventory_lookup_returns_nearby_with_last_updated(client: TestClient):
    response = client.get(
        "/inventory/lookup",
        headers=_headers("associate"),
        params={"sku": "AST-LIN-BLZ-SND-M", "store_id": "ST001", "radius_miles": 25},
    )
    assert response.status_code == 200
    body = response.json()
    assert body["sku"] == "AST-LIN-BLZ-SND-M"
    assert len(body["stores"]) >= 1
    assert all("last_updated" in row for row in body["stores"])
    st002 = next(row for row in body["stores"] if row["store_id"] == "ST002")
    assert st002["on_hand"] == 4


def test_reserve_preview_then_confirm_token(client: TestClient):
    preview = client.post(
        "/reserve",
        headers=_headers("associate"),
        json={"sku": "AST-LIN-BLZ-SND-M", "store_id": "ST002", "qty": 1},
    )
    assert preview.status_code == 202
    token = preview.json()["confirm_token"]

    confirmed = client.post(
        "/reserve",
        headers=_headers("associate"),
        json={
            "sku": "AST-LIN-BLZ-SND-M",
            "store_id": "ST002",
            "qty": 1,
            "confirm_token": token,
        },
    )
    assert confirmed.status_code == 200
    confirmed_body = confirmed.json()
    assert confirmed_body["status"] == "reserved"
    assert confirmed_body["on_hand"] == 3
    assert confirmed_body["reserved"] >= 1


def test_reserve_with_confirm_true(client: TestClient):
    response = client.post(
        "/reserve",
        headers=_headers("associate"),
        json={"sku": "AST-LIN-BLZ-SND-M", "store_id": "ST003", "qty": 1, "confirm": True},
    )
    assert response.status_code == 200
    body = response.json()
    assert body["status"] == "reserved"
    assert body["on_hand"] == 1


def test_transfer_requires_merch_role(client: TestClient):
    response = client.post(
        "/transfer",
        headers=_headers("associate"),
        json={
            "from_store": "ST002",
            "to_store": "ST001",
            "sku": "AST-LIN-BLZ-SND-M",
            "qty": 1,
            "confirm": True,
        },
    )
    assert response.status_code == 403


def test_transfer_preview_then_confirm_merch_without_on_hand_change(client: TestClient):
    before_lookup = client.get(
        "/inventory/lookup",
        headers=_headers("merch"),
        params={"sku": "AST-LIN-BLZ-SND-M", "store_id": "ST002", "radius_miles": 1.0},
    )
    before_st002 = next(row for row in before_lookup.json()["stores"] if row["store_id"] == "ST002")
    before_on_hand = before_st002["on_hand"]

    preview = client.post(
        "/transfer",
        headers=_headers("merch"),
        json={"from_store": "ST002", "to_store": "ST001", "sku": "AST-LIN-BLZ-SND-M", "qty": 1},
    )
    assert preview.status_code == 202
    token = preview.json()["confirm_token"]

    confirmed = client.post(
        "/transfer",
        headers=_headers("merch"),
        json={
            "from_store": "ST002",
            "to_store": "ST001",
            "sku": "AST-LIN-BLZ-SND-M",
            "qty": 1,
            "confirm_token": token,
        },
    )
    assert confirmed.status_code == 200
    confirmed_body = confirmed.json()
    assert confirmed_body["status"] == "created"
    assert confirmed_body["to_store"] == "ST001"

    after_lookup = client.get(
        "/inventory/lookup",
        headers=_headers("merch"),
        params={"sku": "AST-LIN-BLZ-SND-M", "store_id": "ST002", "radius_miles": 1.0},
    )
    after_st002 = next(row for row in after_lookup.json()["stores"] if row["store_id"] == "ST002")
    assert after_st002["on_hand"] == before_on_hand


def test_create_ticket_and_auditlog(client: TestClient):
    reserve = client.post(
        "/reserve",
        headers=_headers("associate"),
        json={"sku": "AST-LIN-BLZ-SND-M", "store_id": "ST002", "qty": 1, "confirm": True},
    )
    assert reserve.status_code == 200

    transfer = client.post(
        "/transfer",
        headers=_headers("merch"),
        json={
            "from_store": "ST002",
            "to_store": "ST001",
            "sku": "AST-LIN-BLZ-SND-M",
            "qty": 1,
            "confirm": True,
        },
    )
    assert transfer.status_code == 200

    ticket = client.post(
        "/tickets",
        headers=_headers("support"),
        json={
            "store_id": "ST001",
            "category": "POS Sync Failure",
            "severity": "high",
            "description": "POS synchronization is failing during evening rush window.",
        },
    )
    assert ticket.status_code == 201
    assert ticket.json()["ticket_id"].startswith("TCKT")

    audit = client.get("/auditlog", headers=_headers("support"))
    assert audit.status_code == 200
    actions = [entry["action"] for entry in audit.json()["entries"]]
    assert "reserve" in actions
    assert "transfer" in actions
    assert "create_ticket" in actions
