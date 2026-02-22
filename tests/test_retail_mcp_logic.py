from __future__ import annotations

import unittest

from services.retail_mcp.app.logic import (
    create_transfer_action,
    fetch_document,
    inventory_lookup_action,
    reserve_item_action,
    search_documents,
)


class RetailMCPCoreLogicTests(unittest.TestCase):
    def test_search_returns_top_results_with_stable_ids(self) -> None:
        result = search_documents("hold duration policy")
        self.assertIn("results", result)
        self.assertGreaterEqual(len(result["results"]), 1)
        top = result["results"][0]
        self.assertTrue(top["id"].startswith("doc:"))
        self.assertIn("#section-", top["id"])
        self.assertIn("url", top)

    def test_fetch_returns_citation_ready_content(self) -> None:
        section = fetch_document("doc:Returns_and_Holds_Policy#section-3")
        self.assertEqual(section["id"], "doc:Returns_and_Holds_Policy#section-3")
        self.assertIn("content", section)
        self.assertIn("store holds", section["content"].lower())
        self.assertIn("https://retailnext.internal/docs/returns#section-3", section["url"])

    def test_unknown_sku_rejected(self) -> None:
        with self.assertRaises(ValueError):
            inventory_lookup_action(
                sku="NOT-A-REAL-SKU",
                store_id="ST001",
                radius_miles=25.0,
                role="associate",
                base_url="http://localhost:8080",
            )

    def test_qty_guardrail_rejects_out_of_range(self) -> None:
        with self.assertRaises(ValueError):
            reserve_item_action(
                sku="AST-LIN-BLZ-SND-M",
                store_id="ST002",
                qty=0,
                confirm=False,
                role="associate",
                base_url="http://localhost:8080",
            )

    def test_transfer_requires_merch_role(self) -> None:
        with self.assertRaises(ValueError):
            create_transfer_action(
                from_store="ST002",
                to_store="ST001",
                sku="AST-LIN-BLZ-SND-M",
                qty=1,
                confirm=False,
                role="associate",
                base_url="http://localhost:8080",
            )


if __name__ == "__main__":
    unittest.main()
