from __future__ import annotations

import unittest
from decimal import Decimal
from pathlib import Path

from order_entry_bot.excel_reader import load_orders


class ExcelReaderTest(unittest.TestCase):
    def test_load_sample_orders(self) -> None:
        orders, summary = load_orders(Path("docs/orders.xlsx"))

        self.assertEqual(summary.order_count, 4)
        self.assertEqual(summary.item_count, 7)
        self.assertEqual(orders[0].order_no, "20260706004")
        self.assertEqual(orders[0].order_date.isoformat(), "2026-07-06")
        self.assertEqual(orders[0].total_received, Decimal("243.00"))
        self.assertEqual(len(orders[0].items), 2)
        self.assertEqual(orders[0].items[0].barcode, "6942394154645")
        self.assertEqual(orders[0].items[0].quantity, 1)


if __name__ == "__main__":
    unittest.main()
