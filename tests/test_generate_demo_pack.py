from __future__ import annotations

import csv
import json
import subprocess
import sys
import unittest
from collections import Counter
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[1]
GENERATOR_SCRIPT = PROJECT_ROOT / "scripts" / "generate_demo_pack.py"
DATA_DIR = PROJECT_ROOT / "data"


def read_csv(path: Path) -> list[dict[str, str]]:
    with path.open("r", newline="", encoding="utf-8") as handle:
        return list(csv.DictReader(handle))


class DemoPackGenerationTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        subprocess.run(
            [sys.executable, str(GENERATOR_SCRIPT)],
            cwd=PROJECT_ROOT,
            check=True,
        )
        cls.products = read_csv(DATA_DIR / "products.csv")
        cls.inventory = read_csv(DATA_DIR / "inventory.csv")
        cls.tickets = read_csv(DATA_DIR / "tickets.csv")
        cls.manifest = json.loads((DATA_DIR / "demo_manifest.json").read_text(encoding="utf-8"))

    def test_hero_sku_product_attributes(self) -> None:
        hero_variants = [row for row in self.products if row["product_name"] == "Aster Linen Blazer"]
        self.assertEqual(len(hero_variants), 12, "Expected 12 color/size variants for hero SKU style")

        target_sku = self.manifest["anomalies"]["hero_sku"]["target_sku"]
        target_rows = [row for row in self.products if row["sku"] == target_sku]
        self.assertEqual(len(target_rows), 1, "Expected one exact row for hero target SKU")
        target = target_rows[0]

        self.assertEqual(target["style_id"], "AST-LIN-BLZ")
        self.assertEqual(target["category"], "Apparel")
        self.assertEqual(target["subcategory"], "Blazer")
        self.assertEqual(target["color"], "Sand")
        self.assertEqual(target["size"], "M")
        self.assertEqual(target["season"], "Spring 2026")

    def test_inventory_has_scripted_hero_distribution(self) -> None:
        hero_info = self.manifest["anomalies"]["hero_sku"]
        expected_distribution = hero_info["availability_distribution_on_hand"]
        target_sku = hero_info["target_sku"]

        actual_distribution: dict[str, int] = {}
        for row in self.inventory:
            if row["sku"] == target_sku:
                actual_distribution[row["store_id"]] = int(row["on_hand"])

        self.assertEqual(actual_distribution, expected_distribution)
        stocked_locations = [store_id for store_id, on_hand in actual_distribution.items() if on_hand > 0]
        self.assertGreaterEqual(len(stocked_locations), 3)

    def test_ticket_clusters_match_manifest_counts(self) -> None:
        expected_counts = self.manifest["anomalies"]["support_ticket_clusters"]["expected_category_counts"]
        observed_counts = Counter(row["category"] for row in self.tickets)

        self.assertGreaterEqual(len(expected_counts), 3)
        self.assertLessEqual(len(expected_counts), 4)
        self.assertEqual(
            {category: observed_counts.get(category, 0) for category in expected_counts},
            expected_counts,
        )


if __name__ == "__main__":
    unittest.main()
