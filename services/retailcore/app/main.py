from __future__ import annotations

import csv
import json
import math
import os
import secrets
import sqlite3
from contextlib import asynccontextmanager
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any, Optional

from fastapi import FastAPI, HTTPException, Request
from fastapi.responses import JSONResponse
from pydantic import BaseModel, Field

VALID_ROLES = {"associate", "merch", "support"}
NO_AUTH_PATHS = {"/health", "/docs", "/openapi.json", "/redoc"}


@dataclass(frozen=True)
class AppConfig:
    data_dir: Path
    db_path: Path
    confirm_token_ttl_seconds: int = 900


class ReserveRequest(BaseModel):
    sku: str
    store_id: str
    qty: int = Field(gt=0)
    confirm: bool = False
    confirm_token: Optional[str] = None


class TransferRequest(BaseModel):
    from_store: str
    to_store: str
    sku: str
    qty: int = Field(gt=0)
    confirm: bool = False
    confirm_token: Optional[str] = None


class TicketCreateRequest(BaseModel):
    store_id: str
    category: str
    severity: str
    description: str = Field(min_length=1)


def _project_root() -> Path:
    return Path(__file__).resolve().parents[3]


def load_config() -> AppConfig:
    root = _project_root()
    data_dir = Path(os.getenv("RETAILCORE_DATA_DIR", str(root / "data"))).resolve()
    db_path = Path(
        os.getenv("RETAILCORE_DB_PATH", str(root / "services" / "retailcore" / "retailcore.db"))
    ).resolve()
    return AppConfig(data_dir=data_dir, db_path=db_path)


def connect_db(db_path: Path) -> sqlite3.Connection:
    db_path.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(db_path, check_same_thread=False)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON;")
    return conn


def _read_csv_rows(data_dir: Path, file_name: str) -> list[dict[str, str]]:
    file_path = data_dir / file_name
    if not file_path.exists():
        raise FileNotFoundError(f"Required CSV file not found: {file_path}")
    with file_path.open("r", newline="", encoding="utf-8") as handle:
        return list(csv.DictReader(handle))


def _reset_schema(conn: sqlite3.Connection) -> None:
    conn.executescript(
        """
        DROP TABLE IF EXISTS inbound_transfers;
        DROP TABLE IF EXISTS transfers;
        DROP TABLE IF EXISTS audit_log;
        DROP TABLE IF EXISTS confirm_tokens;
        DROP TABLE IF EXISTS sales_daily;
        DROP TABLE IF EXISTS tickets;
        DROP TABLE IF EXISTS inventory;
        DROP TABLE IF EXISTS products;
        DROP TABLE IF EXISTS customers;
        DROP TABLE IF EXISTS stores;

        CREATE TABLE stores (
            store_id TEXT PRIMARY KEY,
            store_name TEXT NOT NULL,
            city TEXT NOT NULL,
            state TEXT NOT NULL,
            region TEXT NOT NULL,
            latitude REAL NOT NULL,
            longitude REAL NOT NULL
        );

        CREATE TABLE products (
            sku TEXT PRIMARY KEY,
            style_id TEXT NOT NULL,
            product_name TEXT NOT NULL,
            category TEXT NOT NULL,
            subcategory TEXT NOT NULL,
            color TEXT NOT NULL,
            size TEXT NOT NULL,
            season TEXT NOT NULL,
            unit_price REAL NOT NULL
        );

        CREATE TABLE inventory (
            store_id TEXT NOT NULL,
            sku TEXT NOT NULL,
            on_hand INTEGER NOT NULL,
            reserved INTEGER NOT NULL,
            reorder_point INTEGER NOT NULL,
            last_updated TEXT NOT NULL,
            PRIMARY KEY (store_id, sku),
            FOREIGN KEY (store_id) REFERENCES stores(store_id),
            FOREIGN KEY (sku) REFERENCES products(sku)
        );

        CREATE TABLE sales_daily (
            date TEXT NOT NULL,
            store_id TEXT NOT NULL,
            sku TEXT NOT NULL,
            units_sold INTEGER NOT NULL,
            net_sales REAL NOT NULL,
            FOREIGN KEY (store_id) REFERENCES stores(store_id),
            FOREIGN KEY (sku) REFERENCES products(sku)
        );

        CREATE TABLE tickets (
            ticket_id TEXT PRIMARY KEY,
            opened_date TEXT NOT NULL,
            store_id TEXT NOT NULL,
            category TEXT NOT NULL,
            summary TEXT NOT NULL,
            severity TEXT NOT NULL,
            status TEXT NOT NULL,
            channel TEXT NOT NULL,
            description TEXT NOT NULL DEFAULT '',
            FOREIGN KEY (store_id) REFERENCES stores(store_id)
        );

        CREATE TABLE customers (
            customer_id TEXT PRIMARY KEY,
            loyalty_tier TEXT NOT NULL,
            home_store_id TEXT NOT NULL,
            preferred_channel TEXT NOT NULL,
            lifetime_value_band TEXT NOT NULL,
            FOREIGN KEY (home_store_id) REFERENCES stores(store_id)
        );

        CREATE TABLE transfers (
            transfer_id INTEGER PRIMARY KEY AUTOINCREMENT,
            from_store TEXT NOT NULL,
            to_store TEXT NOT NULL,
            sku TEXT NOT NULL,
            qty INTEGER NOT NULL,
            status TEXT NOT NULL,
            created_at TEXT NOT NULL,
            created_by_role TEXT NOT NULL,
            FOREIGN KEY (from_store) REFERENCES stores(store_id),
            FOREIGN KEY (to_store) REFERENCES stores(store_id),
            FOREIGN KEY (sku) REFERENCES products(sku)
        );

        CREATE TABLE inbound_transfers (
            inbound_id INTEGER PRIMARY KEY AUTOINCREMENT,
            transfer_id INTEGER NOT NULL,
            store_id TEXT NOT NULL,
            sku TEXT NOT NULL,
            qty INTEGER NOT NULL,
            expected_date TEXT NOT NULL,
            status TEXT NOT NULL,
            FOREIGN KEY (transfer_id) REFERENCES transfers(transfer_id),
            FOREIGN KEY (store_id) REFERENCES stores(store_id),
            FOREIGN KEY (sku) REFERENCES products(sku)
        );

        CREATE TABLE audit_log (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            action TEXT NOT NULL,
            role TEXT NOT NULL,
            payload_json TEXT NOT NULL,
            created_at TEXT NOT NULL
        );

        CREATE TABLE confirm_tokens (
            token TEXT PRIMARY KEY,
            action TEXT NOT NULL,
            payload_json TEXT NOT NULL,
            expires_at TEXT NOT NULL,
            used INTEGER NOT NULL DEFAULT 0
        );
        """
    )


def _load_source_data(conn: sqlite3.Connection, data_dir: Path) -> None:
    stores = _read_csv_rows(data_dir, "stores.csv")
    products = _read_csv_rows(data_dir, "products.csv")
    inventory = _read_csv_rows(data_dir, "inventory.csv")
    sales_daily = _read_csv_rows(data_dir, "sales_daily.csv")
    tickets = _read_csv_rows(data_dir, "tickets.csv")
    customers = _read_csv_rows(data_dir, "customers.csv")

    conn.executemany(
        """
        INSERT INTO stores (store_id, store_name, city, state, region, latitude, longitude)
        VALUES (?, ?, ?, ?, ?, ?, ?)
        """,
        [
            (
                row["store_id"],
                row["store_name"],
                row["city"],
                row["state"],
                row["region"],
                float(row["latitude"]),
                float(row["longitude"]),
            )
            for row in stores
        ],
    )

    conn.executemany(
        """
        INSERT INTO products (sku, style_id, product_name, category, subcategory, color, size, season, unit_price)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
        """,
        [
            (
                row["sku"],
                row["style_id"],
                row["product_name"],
                row["category"],
                row["subcategory"],
                row["color"],
                row["size"],
                row["season"],
                float(row["unit_price"]),
            )
            for row in products
        ],
    )

    conn.executemany(
        """
        INSERT INTO inventory (store_id, sku, on_hand, reserved, reorder_point, last_updated)
        VALUES (?, ?, ?, ?, ?, ?)
        """,
        [
            (
                row["store_id"],
                row["sku"],
                int(row["on_hand"]),
                int(row["reserved"]),
                int(row["reorder_point"]),
                row["last_updated"],
            )
            for row in inventory
        ],
    )

    conn.executemany(
        """
        INSERT INTO sales_daily (date, store_id, sku, units_sold, net_sales)
        VALUES (?, ?, ?, ?, ?)
        """,
        [
            (
                row["date"],
                row["store_id"],
                row["sku"],
                int(row["units_sold"]),
                float(row["net_sales"]),
            )
            for row in sales_daily
        ],
    )

    conn.executemany(
        """
        INSERT INTO tickets (ticket_id, opened_date, store_id, category, summary, severity, status, channel, description)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
        """,
        [
            (
                row["ticket_id"],
                row["opened_date"],
                row["store_id"],
                row["category"],
                row["summary"],
                row["severity"],
                row["status"],
                row["channel"],
                row["summary"],
            )
            for row in tickets
        ],
    )

    conn.executemany(
        """
        INSERT INTO customers (customer_id, loyalty_tier, home_store_id, preferred_channel, lifetime_value_band)
        VALUES (?, ?, ?, ?, ?)
        """,
        [
            (
                row["customer_id"],
                row["loyalty_tier"],
                row["home_store_id"],
                row["preferred_channel"],
                row["lifetime_value_band"],
            )
            for row in customers
        ],
    )


def initialize_database(config: AppConfig) -> None:
    with connect_db(config.db_path) as conn:
        _reset_schema(conn)
        _load_source_data(conn, config.data_dir)
        conn.commit()


def _row_to_dict(row: sqlite3.Row) -> dict[str, Any]:
    return {column: row[column] for column in row.keys()}


def _canonical_payload(payload: dict[str, Any]) -> str:
    return json.dumps(payload, sort_keys=True, separators=(",", ":"))


def issue_confirmation_token(
    conn: sqlite3.Connection,
    action: str,
    payload: dict[str, Any],
    ttl_seconds: int,
) -> tuple[str, str]:
    token = secrets.token_urlsafe(24)
    expires_at = (datetime.now(timezone.utc) + timedelta(seconds=ttl_seconds)).isoformat()
    conn.execute(
        """
        INSERT INTO confirm_tokens (token, action, payload_json, expires_at, used)
        VALUES (?, ?, ?, ?, 0)
        """,
        (token, action, _canonical_payload(payload), expires_at),
    )
    return token, expires_at


def _parse_datetime(value: str) -> datetime:
    parsed = datetime.fromisoformat(value)
    if parsed.tzinfo is None:
        return parsed.replace(tzinfo=timezone.utc)
    return parsed


def validate_confirmation_token(
    conn: sqlite3.Connection,
    token: str,
    action: str,
    payload: dict[str, Any],
) -> bool:
    row = conn.execute(
        """
        SELECT token, action, payload_json, expires_at, used
        FROM confirm_tokens
        WHERE token = ?
        """,
        (token,),
    ).fetchone()
    if row is None:
        return False
    if int(row["used"]) == 1:
        return False
    if row["action"] != action:
        return False
    if row["payload_json"] != _canonical_payload(payload):
        return False
    if datetime.now(timezone.utc) > _parse_datetime(row["expires_at"]):
        return False
    conn.execute("UPDATE confirm_tokens SET used = 1 WHERE token = ?", (token,))
    return True


def log_audit(conn: sqlite3.Connection, action: str, role: str, payload: dict[str, Any]) -> None:
    conn.execute(
        """
        INSERT INTO audit_log (action, role, payload_json, created_at)
        VALUES (?, ?, ?, ?)
        """,
        (action, role, json.dumps(payload, sort_keys=True), datetime.now(timezone.utc).isoformat()),
    )


def haversine_miles(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    radius_miles = 3958.8
    lat1_rad = math.radians(lat1)
    lon1_rad = math.radians(lon1)
    lat2_rad = math.radians(lat2)
    lon2_rad = math.radians(lon2)
    d_lat = lat2_rad - lat1_rad
    d_lon = lon2_rad - lon1_rad
    a = math.sin(d_lat / 2) ** 2 + math.cos(lat1_rad) * math.cos(lat2_rad) * math.sin(d_lon / 2) ** 2
    c = 2 * math.atan2(math.sqrt(a), math.sqrt(1 - a))
    return radius_miles * c


def _conn_from_request(request: Request) -> sqlite3.Connection:
    config: AppConfig = request.app.state.config
    return connect_db(config.db_path)


def create_app() -> FastAPI:
    config = load_config()

    @asynccontextmanager
    async def lifespan(app: FastAPI):
        initialize_database(config)
        app.state.config = config
        yield

    app = FastAPI(
        title="RetailCore API",
        version="0.1.0",
        lifespan=lifespan,
    )

    @app.middleware("http")
    async def role_auth_middleware(request: Request, call_next):
        if request.url.path in NO_AUTH_PATHS:
            return await call_next(request)

        role = request.headers.get("X-DEMO-ROLE")
        if role not in VALID_ROLES:
            return JSONResponse(
                status_code=401,
                content={"detail": "Missing or invalid X-DEMO-ROLE header"},
            )
        request.state.role = role
        return await call_next(request)

    @app.get("/health")
    async def health() -> dict[str, str]:
        return {"status": "ok"}

    @app.get("/inventory/lookup")
    async def inventory_lookup(
        request: Request,
        sku: str,
        store_id: str,
        radius_miles: float = 25.0,
    ) -> dict[str, Any]:
        with _conn_from_request(request) as conn:
            base_store = conn.execute(
                """
                SELECT store_id, store_name, latitude, longitude
                FROM stores
                WHERE store_id = ?
                """,
                (store_id,),
            ).fetchone()
            if base_store is None:
                raise HTTPException(status_code=404, detail=f"Store not found: {store_id}")

            rows = conn.execute(
                """
                SELECT s.store_id, s.store_name, s.city, s.state, s.latitude, s.longitude,
                       i.on_hand, i.reserved, i.last_updated
                FROM inventory i
                JOIN stores s ON s.store_id = i.store_id
                WHERE i.sku = ?
                """,
                (sku,),
            ).fetchall()
            if not rows:
                raise HTTPException(status_code=404, detail=f"SKU not found in inventory: {sku}")

            nearby: list[dict[str, Any]] = []
            for row in rows:
                distance = haversine_miles(
                    float(base_store["latitude"]),
                    float(base_store["longitude"]),
                    float(row["latitude"]),
                    float(row["longitude"]),
                )
                if distance <= radius_miles:
                    on_hand = int(row["on_hand"])
                    reserved = int(row["reserved"])
                    nearby.append(
                        {
                            "store_id": row["store_id"],
                            "store_name": row["store_name"],
                            "city": row["city"],
                            "state": row["state"],
                            "distance_miles": round(distance, 2),
                            "on_hand": on_hand,
                            "reserved": reserved,
                            "available": on_hand - reserved,
                            "last_updated": row["last_updated"],
                        }
                    )
            nearby.sort(key=lambda item: item["distance_miles"])

            return {
                "sku": sku,
                "query_store_id": store_id,
                "radius_miles": radius_miles,
                "stores": nearby,
            }

    @app.get("/products/{sku}")
    async def get_product(request: Request, sku: str) -> dict[str, Any]:
        with _conn_from_request(request) as conn:
            row = conn.execute("SELECT * FROM products WHERE sku = ?", (sku,)).fetchone()
            if row is None:
                raise HTTPException(status_code=404, detail=f"Product not found: {sku}")
            return _row_to_dict(row)

    @app.post("/reserve")
    async def reserve_inventory(request: Request, payload: ReserveRequest):
        role = request.state.role
        update_time = datetime.now(timezone.utc).isoformat()
        action_payload = {
            "sku": payload.sku,
            "store_id": payload.store_id,
            "qty": payload.qty,
        }

        with _conn_from_request(request) as conn:
            row = conn.execute(
                """
                SELECT store_id, sku, on_hand, reserved, last_updated
                FROM inventory
                WHERE store_id = ? AND sku = ?
                """,
                (payload.store_id, payload.sku),
            ).fetchone()
            if row is None:
                raise HTTPException(status_code=404, detail="Inventory row not found for store/SKU")

            on_hand = int(row["on_hand"])
            reserved = int(row["reserved"])
            if not payload.confirm:
                if payload.confirm_token:
                    token_ok = validate_confirmation_token(
                        conn=conn,
                        token=payload.confirm_token,
                        action="reserve",
                        payload=action_payload,
                    )
                    if not token_ok:
                        raise HTTPException(status_code=400, detail="Invalid or expired confirm_token")
                else:
                    token, expires_at = issue_confirmation_token(
                        conn=conn,
                        action="reserve",
                        payload=action_payload,
                        ttl_seconds=request.app.state.config.confirm_token_ttl_seconds,
                    )
                    return JSONResponse(
                        status_code=202,
                        content={
                            "status": "preview",
                            "action": "reserve",
                            "confirm_token": token,
                            "confirm_token_expires_at": expires_at,
                            "can_reserve": on_hand >= payload.qty,
                            "current_on_hand": on_hand,
                            "current_reserved": reserved,
                            "preview_on_hand_after": on_hand - payload.qty,
                            "preview_reserved_after": reserved + payload.qty,
                        },
                    )

            if on_hand < payload.qty:
                raise HTTPException(status_code=409, detail="Insufficient on_hand inventory to reserve qty")

            conn.execute(
                """
                UPDATE inventory
                SET on_hand = on_hand - ?, reserved = reserved + ?, last_updated = ?
                WHERE store_id = ? AND sku = ?
                """,
                (payload.qty, payload.qty, update_time, payload.store_id, payload.sku),
            )
            updated = conn.execute(
                """
                SELECT on_hand, reserved, last_updated
                FROM inventory
                WHERE store_id = ? AND sku = ?
                """,
                (payload.store_id, payload.sku),
            ).fetchone()
            log_audit(
                conn=conn,
                action="reserve",
                role=role,
                payload={**action_payload, "confirmed": True},
            )
            conn.commit()
            return {
                "status": "reserved",
                "store_id": payload.store_id,
                "sku": payload.sku,
                "qty": payload.qty,
                "on_hand": int(updated["on_hand"]),
                "reserved": int(updated["reserved"]),
                "last_updated": updated["last_updated"],
            }

    @app.post("/transfer")
    async def create_transfer(request: Request, payload: TransferRequest):
        role = request.state.role
        if role != "merch":
            raise HTTPException(status_code=403, detail="Only merch role can create transfers")
        if payload.from_store == payload.to_store:
            raise HTTPException(status_code=400, detail="from_store and to_store must differ")

        action_payload = {
            "from_store": payload.from_store,
            "to_store": payload.to_store,
            "sku": payload.sku,
            "qty": payload.qty,
        }

        with _conn_from_request(request) as conn:
            source_row = conn.execute(
                """
                SELECT on_hand
                FROM inventory
                WHERE store_id = ? AND sku = ?
                """,
                (payload.from_store, payload.sku),
            ).fetchone()
            target_row = conn.execute(
                """
                SELECT on_hand
                FROM inventory
                WHERE store_id = ? AND sku = ?
                """,
                (payload.to_store, payload.sku),
            ).fetchone()
            if source_row is None:
                raise HTTPException(status_code=404, detail="Source inventory row not found")
            if target_row is None:
                raise HTTPException(status_code=404, detail="Target inventory row not found")

            source_on_hand = int(source_row["on_hand"])
            if not payload.confirm:
                if payload.confirm_token:
                    token_ok = validate_confirmation_token(
                        conn=conn,
                        token=payload.confirm_token,
                        action="transfer",
                        payload=action_payload,
                    )
                    if not token_ok:
                        raise HTTPException(status_code=400, detail="Invalid or expired confirm_token")
                else:
                    token, expires_at = issue_confirmation_token(
                        conn=conn,
                        action="transfer",
                        payload=action_payload,
                        ttl_seconds=request.app.state.config.confirm_token_ttl_seconds,
                    )
                    return JSONResponse(
                        status_code=202,
                        content={
                            "status": "preview",
                            "action": "transfer",
                            "confirm_token": token,
                            "confirm_token_expires_at": expires_at,
                            "can_transfer": source_on_hand >= payload.qty,
                            "source_on_hand": source_on_hand,
                            "note": "Transfer creates inbound record; source on_hand remains unchanged immediately.",
                        },
                    )

            if source_on_hand < payload.qty:
                raise HTTPException(status_code=409, detail="Insufficient source on_hand inventory for transfer")

            created_at = datetime.now(timezone.utc).isoformat()
            expected_date = (datetime.now(timezone.utc) + timedelta(days=2)).date().isoformat()
            cursor = conn.execute(
                """
                INSERT INTO transfers (from_store, to_store, sku, qty, status, created_at, created_by_role)
                VALUES (?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    payload.from_store,
                    payload.to_store,
                    payload.sku,
                    payload.qty,
                    "pending",
                    created_at,
                    role,
                ),
            )
            transfer_id = int(cursor.lastrowid)
            conn.execute(
                """
                INSERT INTO inbound_transfers (transfer_id, store_id, sku, qty, expected_date, status)
                VALUES (?, ?, ?, ?, ?, ?)
                """,
                (
                    transfer_id,
                    payload.to_store,
                    payload.sku,
                    payload.qty,
                    expected_date,
                    "inbound_pending",
                ),
            )
            log_audit(
                conn=conn,
                action="transfer",
                role=role,
                payload={**action_payload, "confirmed": True},
            )
            conn.commit()
            return {
                "status": "created",
                "transfer_id": transfer_id,
                "from_store": payload.from_store,
                "to_store": payload.to_store,
                "sku": payload.sku,
                "qty": payload.qty,
                "inbound_status": "inbound_pending",
                "expected_date": expected_date,
            }

    @app.post("/tickets", status_code=201)
    async def create_ticket(request: Request, payload: TicketCreateRequest):
        role = request.state.role
        with _conn_from_request(request) as conn:
            store_exists = conn.execute(
                "SELECT 1 FROM stores WHERE store_id = ?",
                (payload.store_id,),
            ).fetchone()
            if store_exists is None:
                raise HTTPException(status_code=404, detail=f"Store not found: {payload.store_id}")

            max_existing = conn.execute(
                """
                SELECT COALESCE(MAX(CAST(SUBSTR(ticket_id, 5) AS INTEGER)), 0) AS max_id
                FROM tickets
                """
            ).fetchone()
            next_id = int(max_existing["max_id"]) + 1
            ticket_id = f"TCKT{next_id:04d}"
            opened_date = datetime.now(timezone.utc).date().isoformat()
            summary = payload.description[:80]

            conn.execute(
                """
                INSERT INTO tickets (ticket_id, opened_date, store_id, category, summary, severity, status, channel, description)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    ticket_id,
                    opened_date,
                    payload.store_id,
                    payload.category,
                    summary,
                    payload.severity,
                    "open",
                    "api",
                    payload.description,
                ),
            )
            log_audit(
                conn=conn,
                action="create_ticket",
                role=role,
                payload={
                    "ticket_id": ticket_id,
                    "store_id": payload.store_id,
                    "category": payload.category,
                    "severity": payload.severity,
                },
            )
            conn.commit()
            return {
                "ticket_id": ticket_id,
                "opened_date": opened_date,
                "store_id": payload.store_id,
                "category": payload.category,
                "severity": payload.severity,
                "status": "open",
            }

    @app.get("/auditlog")
    async def get_audit_log(request: Request):
        with _conn_from_request(request) as conn:
            rows = conn.execute(
                """
                SELECT id, action, role, payload_json, created_at
                FROM audit_log
                ORDER BY id ASC
                """
            ).fetchall()
            entries = []
            for row in rows:
                entries.append(
                    {
                        "id": int(row["id"]),
                        "action": row["action"],
                        "role": row["role"],
                        "payload": json.loads(row["payload_json"]),
                        "created_at": row["created_at"],
                    }
                )
            return {"count": len(entries), "entries": entries}

    return app


app = create_app()
