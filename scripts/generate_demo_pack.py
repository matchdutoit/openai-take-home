#!/usr/bin/env python3
"""Generate deterministic demo assets for the RetailNext onsite scenario."""

from __future__ import annotations

import csv
import json
import random
from collections import Counter
from datetime import date, timedelta
from pathlib import Path
from textwrap import dedent

SEED = 20260417
BASE_DATE = date(2026, 2, 22)
SALES_DAYS = 28

ROOT = Path(__file__).resolve().parents[1]
DATA_DIR = ROOT / "data"
KNOWLEDGE_DIR = ROOT / "docs" / "knowledge"

HERO_STYLE_ID = "AST-LIN-BLZ"
HERO_PRODUCT_NAME = "Aster Linen Blazer"
HERO_TARGET_SKU = "AST-LIN-BLZ-SND-M"

HERO_TARGET_AVAILABILITY = {
    "ST001": 0,  # SoHo Flagship (query store)
    "ST002": 4,  # nearby
    "ST003": 2,  # nearby
    "ST004": 1,  # nearby
    "ST005": 0,
    "ST006": 0,
    "ST007": 0,
    "ST008": 0,
}

HIGH_DEMAND_LOW_INVENTORY_SKUS = [
    "ECL-RUN-SNK-WHT-08",
    "NVA-UTL-TOT-CML-OS",
    "LUN-WRP-DRS-COR-M",
    "ORI-SLM-JEA-IND-30",
    "HBR-LTH-SND-TAN-09",
]

TICKET_CLUSTER_COUNTS = {
    "POS Sync Failure": 18,
    "Price Label Mismatch": 16,
    "BOPIS Pickup Delay": 14,
    "Fitting Room QR Scanner": 12,
}


def write_csv(path: Path, fieldnames: list[str], rows: list[dict[str, str]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows)


def write_markdown(path: Path, content: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content.rstrip() + "\n", encoding="utf-8")


def build_stores() -> list[dict[str, str]]:
    return [
        {
            "store_id": "ST001",
            "store_name": "SoHo Flagship",
            "city": "New York",
            "state": "NY",
            "region": "Northeast",
            "latitude": "40.7233",
            "longitude": "-74.0030",
        },
        {
            "store_id": "ST002",
            "store_name": "Chelsea Market",
            "city": "New York",
            "state": "NY",
            "region": "Northeast",
            "latitude": "40.7422",
            "longitude": "-74.0060",
        },
        {
            "store_id": "ST003",
            "store_name": "Brooklyn Heights",
            "city": "Brooklyn",
            "state": "NY",
            "region": "Northeast",
            "latitude": "40.6959",
            "longitude": "-73.9952",
        },
        {
            "store_id": "ST004",
            "store_name": "Upper East Side",
            "city": "New York",
            "state": "NY",
            "region": "Northeast",
            "latitude": "40.7736",
            "longitude": "-73.9566",
        },
        {
            "store_id": "ST005",
            "store_name": "Jersey City Newport",
            "city": "Jersey City",
            "state": "NJ",
            "region": "Northeast",
            "latitude": "40.7269",
            "longitude": "-74.0324",
        },
        {
            "store_id": "ST006",
            "store_name": "Queens Astoria",
            "city": "Queens",
            "state": "NY",
            "region": "Northeast",
            "latitude": "40.7644",
            "longitude": "-73.9235",
        },
        {
            "store_id": "ST007",
            "store_name": "Boston Back Bay",
            "city": "Boston",
            "state": "MA",
            "region": "Northeast",
            "latitude": "42.3503",
            "longitude": "-71.0810",
        },
        {
            "store_id": "ST008",
            "store_name": "Philadelphia Center City",
            "city": "Philadelphia",
            "state": "PA",
            "region": "Mid-Atlantic",
            "latitude": "39.9526",
            "longitude": "-75.1652",
        },
    ]


def build_products() -> list[dict[str, str]]:
    products: list[dict[str, str]] = []
    hero_colors = [("SND", "Sand"), ("NVY", "Navy"), ("SGE", "Sage")]
    hero_sizes = ["XS", "S", "M", "L"]
    for color_code, color_name in hero_colors:
        for size in hero_sizes:
            products.append(
                {
                    "sku": f"{HERO_STYLE_ID}-{color_code}-{size}",
                    "style_id": HERO_STYLE_ID,
                    "product_name": HERO_PRODUCT_NAME,
                    "category": "Apparel",
                    "subcategory": "Blazer",
                    "color": color_name,
                    "size": size,
                    "season": "Spring 2026",
                    "unit_price": "128.00",
                }
            )

    products.extend(
        [
            {
                "sku": "ECL-RUN-SNK-WHT-08",
                "style_id": "ECL-RUN-SNK",
                "product_name": "Eclipse Runner Sneaker",
                "category": "Footwear",
                "subcategory": "Sneaker",
                "color": "White",
                "size": "8",
                "season": "Spring 2026",
                "unit_price": "96.00",
            },
            {
                "sku": "NVA-UTL-TOT-CML-OS",
                "style_id": "NVA-UTL-TOT",
                "product_name": "Nova Utility Tote",
                "category": "Accessories",
                "subcategory": "Bag",
                "color": "Camel",
                "size": "OS",
                "season": "Spring 2026",
                "unit_price": "84.00",
            },
            {
                "sku": "LUN-WRP-DRS-COR-M",
                "style_id": "LUN-WRP-DRS",
                "product_name": "Luna Wrap Dress",
                "category": "Apparel",
                "subcategory": "Dress",
                "color": "Coral",
                "size": "M",
                "season": "Spring 2026",
                "unit_price": "112.00",
            },
            {
                "sku": "ORI-SLM-JEA-IND-30",
                "style_id": "ORI-SLM-JEA",
                "product_name": "Orion Slim Jeans",
                "category": "Apparel",
                "subcategory": "Jeans",
                "color": "Indigo",
                "size": "30",
                "season": "Core",
                "unit_price": "98.00",
            },
            {
                "sku": "HBR-LTH-SND-TAN-09",
                "style_id": "HBR-LTH-SND",
                "product_name": "Harbor Leather Sandal",
                "category": "Footwear",
                "subcategory": "Sandal",
                "color": "Tan",
                "size": "9",
                "season": "Spring 2026",
                "unit_price": "89.00",
            },
            {
                "sku": "MRD-CRW-TEE-WHT-M",
                "style_id": "MRD-CRW-TEE",
                "product_name": "Meridian Crew Tee",
                "category": "Apparel",
                "subcategory": "Top",
                "color": "White",
                "size": "M",
                "season": "Core",
                "unit_price": "32.00",
            },
            {
                "sku": "MRD-CRW-TEE-BLK-L",
                "style_id": "MRD-CRW-TEE",
                "product_name": "Meridian Crew Tee",
                "category": "Apparel",
                "subcategory": "Top",
                "color": "Black",
                "size": "L",
                "season": "Core",
                "unit_price": "32.00",
            },
            {
                "sku": "RIV-PLT-SKR-OLV-S",
                "style_id": "RIV-PLT-SKR",
                "product_name": "Riviera Pleated Skirt",
                "category": "Apparel",
                "subcategory": "Skirt",
                "color": "Olive",
                "size": "S",
                "season": "Spring 2026",
                "unit_price": "74.00",
            },
            {
                "sku": "KST-DNM-JKT-LTB-M",
                "style_id": "KST-DNM-JKT",
                "product_name": "Keystone Denim Jacket",
                "category": "Apparel",
                "subcategory": "Jacket",
                "color": "Light Blue",
                "size": "M",
                "season": "Core",
                "unit_price": "118.00",
            },
            {
                "sku": "STR-CVS-SNK-NAV-10",
                "style_id": "STR-CVS-SNK",
                "product_name": "Stratus Canvas Sneaker",
                "category": "Footwear",
                "subcategory": "Sneaker",
                "color": "Navy",
                "size": "10",
                "season": "Core",
                "unit_price": "68.00",
            },
            {
                "sku": "VLY-SLK-SCF-BLS-OS",
                "style_id": "VLY-SLK-SCF",
                "product_name": "Valley Silk Scarf",
                "category": "Accessories",
                "subcategory": "Scarf",
                "color": "Blush",
                "size": "OS",
                "season": "Spring 2026",
                "unit_price": "58.00",
            },
            {
                "sku": "PRM-CHN-BLT-CRM-OS",
                "style_id": "PRM-CHN-BLT",
                "product_name": "Prime Chain Belt",
                "category": "Accessories",
                "subcategory": "Belt",
                "color": "Cream",
                "size": "OS",
                "season": "Spring 2026",
                "unit_price": "46.00",
            },
        ]
    )
    return products


def build_inventory(
    rng: random.Random, stores: list[dict[str, str]], products: list[dict[str, str]]
) -> list[dict[str, str]]:
    rows: list[dict[str, str]] = []
    for store in stores:
        store_id = store["store_id"]
        for product in products:
            sku = product["sku"]
            if sku == HERO_TARGET_SKU:
                on_hand = HERO_TARGET_AVAILABILITY[store_id]
            elif sku in HIGH_DEMAND_LOW_INVENTORY_SKUS:
                on_hand = rng.choice([0, 0, 1, 1, 2, 2, 3])
            elif sku.startswith(HERO_STYLE_ID):
                on_hand = rng.randint(1, 8)
            else:
                on_hand = rng.randint(4, 32)

            reserved = 0 if on_hand == 0 else min(on_hand, rng.choice([0, 0, 1, 1, 2, 3]))
            if sku in HIGH_DEMAND_LOW_INVENTORY_SKUS:
                reorder_point = 8
            elif sku.startswith(HERO_STYLE_ID):
                reorder_point = 5
            else:
                reorder_point = 12

            rows.append(
                {
                    "store_id": store_id,
                    "sku": sku,
                    "on_hand": str(on_hand),
                    "reserved": str(reserved),
                    "reorder_point": str(reorder_point),
                    "last_updated": BASE_DATE.isoformat(),
                }
            )
    return rows


def build_sales_daily(
    rng: random.Random, stores: list[dict[str, str]], products: list[dict[str, str]]
) -> list[dict[str, str]]:
    rows: list[dict[str, str]] = []
    dates = [BASE_DATE - timedelta(days=delta) for delta in range(SALES_DAYS - 1, -1, -1)]
    for day in dates:
        for store in stores:
            store_id = store["store_id"]
            for product in products:
                sku = product["sku"]
                if sku in HIGH_DEMAND_LOW_INVENTORY_SKUS:
                    units_sold = rng.randint(4, 11)
                elif sku.startswith(HERO_STYLE_ID):
                    units_sold = rng.randint(0, 5)
                else:
                    units_sold = rng.randint(0, 4)

                unit_price = float(product["unit_price"])
                rows.append(
                    {
                        "date": day.isoformat(),
                        "store_id": store_id,
                        "sku": sku,
                        "units_sold": str(units_sold),
                        "net_sales": f"{units_sold * unit_price:.2f}",
                    }
                )
    return rows


def build_tickets(rng: random.Random, stores: list[dict[str, str]]) -> list[dict[str, str]]:
    rows: list[dict[str, str]] = []
    stores_ids = [store["store_id"] for store in stores]
    summary_templates = {
        "POS Sync Failure": "Register sync timeout at lane {slot}",
        "Price Label Mismatch": "Shelf label mismatch on aisle {slot}",
        "BOPIS Pickup Delay": "Pickup handoff exceeded SLA by {slot} minutes",
        "Fitting Room QR Scanner": "Fitting room QR scanner failed code parse at room {slot}",
    }
    severity_defaults = {
        "POS Sync Failure": "high",
        "Price Label Mismatch": "medium",
        "BOPIS Pickup Delay": "medium",
        "Fitting Room QR Scanner": "low",
    }

    ticket_num = 1
    for category, count in TICKET_CLUSTER_COUNTS.items():
        for _ in range(count):
            opened = BASE_DATE - timedelta(days=rng.randint(0, 20))
            status = rng.choice(["open", "in_progress", "resolved"])
            channel = rng.choice(["store_portal", "chat", "email"])
            slot = rng.randint(1, 9)
            summary = summary_templates[category].format(slot=slot)
            rows.append(
                {
                    "ticket_id": f"TCKT{ticket_num:04d}",
                    "opened_date": opened.isoformat(),
                    "store_id": rng.choice(stores_ids),
                    "category": category,
                    "summary": summary,
                    "severity": severity_defaults[category],
                    "status": status,
                    "channel": channel,
                }
            )
            ticket_num += 1
    return rows


def build_customers(rng: random.Random, stores: list[dict[str, str]]) -> list[dict[str, str]]:
    rows: list[dict[str, str]] = []
    tiers = ["Bronze", "Silver", "Gold", "Platinum"]
    channels = ["email", "sms", "app_push"]
    ltv_bands = ["low", "medium", "high"]
    store_ids = [store["store_id"] for store in stores]

    for index in range(1, 201):
        rows.append(
            {
                "customer_id": f"CUST{index:04d}",
                "loyalty_tier": rng.choices(tiers, weights=[40, 32, 20, 8], k=1)[0],
                "home_store_id": rng.choice(store_ids),
                "preferred_channel": rng.choice(channels),
                "lifetime_value_band": rng.choices(ltv_bands, weights=[45, 40, 15], k=1)[0],
            }
        )
    return rows


def build_knowledge_docs() -> dict[str, str]:
    return {
        "Returns_and_Holds_Policy.md": dedent(
            """
            # Returns and Holds Policy

            ## Standard Return Window
            - Most full-price items may be returned within 30 days with receipt.
            - Sale items may be exchanged within 14 days unless marked final sale.

            ## Store Holds
            - Standard hold duration is 24 hours.
            - Associates must confirm size, color, and customer callback number before placing hold.
            - Same-day holds may be extended once by a manager for an additional 24 hours.

            ## Restricted Categories
            - Personal accessories and final-sale markdown items are non-returnable.
            - Damaged item returns require manager override and ticket documentation.
            """
        ).strip(),
        "Associate_Playbook.md": dedent(
            """
            # Associate Playbook

            ## Customer Availability Flow
            1. Verify the requested SKU variant in inventory lookup.
            2. Offer nearby store options within the same metro area.
            3. Confirm hold details and submit reservation with explicit confirmation.

            ## Styling Guidance
            - Lead with one hero item and two complementary add-ons.
            - Recommend one premium and one value option for each look.
            - Use the Spring 2026 styling guide for seasonal pairings.

            ## Escalation Rules
            - Escalate to merch when stockout risk persists for 3+ days.
            - Escalate to support when POS, pickup, or scanner incidents repeat during a shift.
            """
        ).strip(),
        "Merch_Transfer_Playbook.md": dedent(
            """
            # Merch Transfer Playbook

            ## Transfer Triggers
            - Prioritize SKUs with less than 7 days of cover in top-selling stores.
            - Use regional balancing before markdowns when donor stores have overstock.

            ## Transfer Approval Guardrails
            - Transfers require merch role and explicit confirmation.
            - Transfers should include source, destination, quantity, and reason code.
            - Re-check donor store safety stock before finalizing.

            ## Markdown Decision Notes
            - Use markdowns only if transfer lead-time misses demand window.
            - Keep markdown rationale linked to weekly sell-through trend.
            """
        ).strip(),
        "Support_Runbook.md": dedent(
            """
            # Support Runbook

            ## Triage Categories
            - POS Sync Failure
            - Price Label Mismatch
            - BOPIS Pickup Delay
            - Fitting Room QR Scanner

            ## Ticket Handling
            1. Validate store, category, and severity.
            2. Link repeat incidents to prior tickets in same category.
            3. Assign owner and due date based on severity matrix.

            ## Weekly Digest
            - Publish top issue categories by count.
            - Highlight recurring stores and aging tickets over 7 days.
            """
        ).strip(),
        "Styling_Guide_Spring_2026.md": dedent(
            """
            # Styling Guide Spring 2026

            ## Seasonal Direction
            - Core palette: sand, sage, navy, coral, and soft neutrals.
            - Fabric focus: breathable linens, light denim, and structured cotton.

            ## Hero Outfit: Aster Linen Blazer
            - Pair with Riviera Pleated Skirt for polished daytime styling.
            - Pair with Orion Slim Jeans and Stratus Canvas Sneaker for smart casual looks.
            - Add Valley Silk Scarf for color contrast.

            ## Associate Suggestion Pattern
            - Start with fit confirmation.
            - Offer one layering add-on and one accessory.
            - Confirm stock before promising same-day hold.
            """
        ).strip(),
    }


def build_manifest(
    stores: list[dict[str, str]],
    inventory_rows: list[dict[str, str]],
    sales_rows: list[dict[str, str]],
    tickets_rows: list[dict[str, str]],
) -> dict[str, object]:
    store_lookup = {row["store_id"]: row["store_name"] for row in stores}
    network_on_hand = Counter()
    for row in inventory_rows:
        network_on_hand[row["sku"]] += int(row["on_hand"])

    sales_totals = Counter()
    for row in sales_rows:
        sales_totals[row["sku"]] += int(row["units_sold"])

    high_demand_entries = []
    for sku in HIGH_DEMAND_LOW_INVENTORY_SKUS:
        high_demand_entries.append(
            {
                "sku": sku,
                "network_on_hand_units": network_on_hand[sku],
                "average_daily_units_sold": round(sales_totals[sku] / SALES_DAYS, 2),
            }
        )

    nearby_store_distances = {"ST002": 1.6, "ST003": 3.1, "ST004": 2.4}
    nearby_expectations = []
    for store_id, distance in nearby_store_distances.items():
        nearby_expectations.append(
            {
                "store_id": store_id,
                "store_name": store_lookup[store_id],
                "distance_miles": distance,
                "on_hand": HERO_TARGET_AVAILABILITY[store_id],
            }
        )

    ticket_counts = Counter(row["category"] for row in tickets_rows)

    return {
        "seed": SEED,
        "base_date": BASE_DATE.isoformat(),
        "generated_for": "RetailNext internal productivity demo",
        "files": [
            "data/stores.csv",
            "data/products.csv",
            "data/inventory.csv",
            "data/sales_daily.csv",
            "data/tickets.csv",
            "data/customers.csv",
        ],
        "anomalies": {
            "hero_sku": {
                "product_name": HERO_PRODUCT_NAME,
                "target_sku": HERO_TARGET_SKU,
                "style_id": HERO_STYLE_ID,
                "availability_distribution_on_hand": HERO_TARGET_AVAILABILITY,
                "expected_nearby_stores_for_ST001": nearby_expectations,
            },
            "high_demand_low_inventory_skus": high_demand_entries,
            "support_ticket_clusters": {
                "expected_category_counts": dict(TICKET_CLUSTER_COUNTS),
                "observed_category_counts": dict(ticket_counts),
            },
        },
        "expected_ground_truth": {
            "associate_inventory_lookup": {
                "query_store_id": "ST001",
                "query_sku": HERO_TARGET_SKU,
                "expected_result_summary": (
                    "No on-hand units at ST001; nearby stock exists at ST002, ST004, and ST003."
                ),
            },
            "merch_analysis_focus": {
                "stockout_risk_skus": HIGH_DEMAND_LOW_INVENTORY_SKUS,
                "transfer_candidate_example": {
                    "sku": "ECL-RUN-SNK-WHT-08",
                    "recommended_destination_store": "ST001",
                },
            },
            "support_cluster_focus": {
                "top_categories": list(TICKET_CLUSTER_COUNTS.keys()),
                "expected_ticket_total": sum(TICKET_CLUSTER_COUNTS.values()),
            },
        },
    }


def main() -> None:
    rng = random.Random(SEED)
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    KNOWLEDGE_DIR.mkdir(parents=True, exist_ok=True)

    stores = build_stores()
    products = build_products()
    inventory = build_inventory(rng, stores, products)
    sales_daily = build_sales_daily(rng, stores, products)
    tickets = build_tickets(rng, stores)
    customers = build_customers(rng, stores)

    write_csv(
        DATA_DIR / "stores.csv",
        ["store_id", "store_name", "city", "state", "region", "latitude", "longitude"],
        stores,
    )
    write_csv(
        DATA_DIR / "products.csv",
        [
            "sku",
            "style_id",
            "product_name",
            "category",
            "subcategory",
            "color",
            "size",
            "season",
            "unit_price",
        ],
        products,
    )
    write_csv(
        DATA_DIR / "inventory.csv",
        ["store_id", "sku", "on_hand", "reserved", "reorder_point", "last_updated"],
        inventory,
    )
    write_csv(
        DATA_DIR / "sales_daily.csv",
        ["date", "store_id", "sku", "units_sold", "net_sales"],
        sales_daily,
    )
    write_csv(
        DATA_DIR / "tickets.csv",
        [
            "ticket_id",
            "opened_date",
            "store_id",
            "category",
            "summary",
            "severity",
            "status",
            "channel",
        ],
        tickets,
    )
    write_csv(
        DATA_DIR / "customers.csv",
        [
            "customer_id",
            "loyalty_tier",
            "home_store_id",
            "preferred_channel",
            "lifetime_value_band",
        ],
        customers,
    )

    for file_name, content in build_knowledge_docs().items():
        write_markdown(KNOWLEDGE_DIR / file_name, content)

    manifest = build_manifest(stores, inventory, sales_daily, tickets)
    (DATA_DIR / "demo_manifest.json").write_text(
        json.dumps(manifest, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )

    print("Generated deterministic demo pack:")
    print(f"- Stores: {len(stores)}")
    print(f"- Products: {len(products)}")
    print(f"- Inventory rows: {len(inventory)}")
    print(f"- Daily sales rows: {len(sales_daily)}")
    print(f"- Tickets: {len(tickets)}")
    print(f"- Customers: {len(customers)}")
    print(f"- Manifest: {(DATA_DIR / 'demo_manifest.json').as_posix()}")


if __name__ == "__main__":
    main()
