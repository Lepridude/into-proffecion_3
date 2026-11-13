from __future__ import annotations

import tempfile
import unittest
from datetime import date, timedelta
from pathlib import Path

import pandas as pd

import sys
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from analysis import calculate_transactions, compare_segments


class AnalysisTests(unittest.TestCase):
    def _transactions_csv(self, directory: Path) -> Path:
        rows = [
            # One-visit customer, two product rows on the same calendar date.
            ["c_low", "cheap", "01.01.2020", 1, 2],
            ["c_low", "cheap", "01.01.2020", 1, 4],
            # Another one-visit customer: average item price is above 10.
            ["c_one2", "expensive", "02.01.2020", 2, 50],
            ["c_one2", "expensive", "02.01.2020", 1, 25],
            # Multi-visit customer.
            ["c_multi", "cheap", "03.01.2020", 2, 2],
            ["c_multi", "cheap", "04.01.2020", 2, 2],
            # Zero quantity must remain in client expenditure but not be used in price.
            ["c_zero", "cheap", "05.01.2020", 0, 10],
        ]
        start = date(2020, 1, 1)
        for offset in range(51):
            rows.append([
                "c_many", "cheap",
                (start + timedelta(days=offset)).strftime("%d.%m.%Y"),
                1, 1,
            ])

        frame = pd.DataFrame(
            rows,
            columns=["clientID", "item", "trDte", "quantity", "amount"],
        )
        path = directory / "transactions.csv"
        frame.to_csv(path, index=False, encoding="utf-8-sig")
        return path

    def test_client_and_price_metrics(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            path = self._transactions_csv(Path(tmp))
            result = calculate_transactions(str(path), "utf-8-sig", ",")
            metrics = result["metrics"]

            self.assertEqual(metrics["clients_spend_le_100"], 5)
            self.assertEqual(metrics["one_visit_clients"], 3)
            self.assertAlmostEqual(metrics["one_visit_mean_spend"], (6 + 75 + 10) / 3)
            self.assertEqual(metrics["clients_visits_gt_50"], 1)
            self.assertEqual(metrics["zero_quantity_rows"], 1)
            self.assertEqual(metrics["products_simple_mean_le_10"], 1)
            self.assertAlmostEqual(result["prices"].loc["cheap", "Простая средняя цена"], 59 / 55)
            self.assertAlmostEqual(result["prices"].loc["expensive", "Простая средняя цена"], 25.0)

    def test_segment_comparison_uses_only_common_items_and_full_pair(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            full = root / "all.csv"
            recent = root / "recent.csv"
            pd.DataFrame(
                [
                    ["item_a", "A", "X"],
                    ["item_b", "B", "Y"],
                ],
                columns=["Товар", "Группа ABC", "Группа XYZ"],
            ).to_csv(full, index=False, encoding="utf-8-sig")
            pd.DataFrame(
                [
                    ["item_a", "A", "Z"],
                    ["item_c", "C", "X"],
                ],
                columns=["Товар", "Группа ABC", "Группа XYZ"],
            ).to_csv(recent, index=False, encoding="utf-8-sig")

            result = compare_segments(str(full), str(recent), "utf-8-sig", ",", root)

            self.assertEqual(result["common_products"], 1)
            self.assertEqual(result["changed_products"], 1)
            changes = pd.read_csv(result["file"], encoding="utf-8-sig")
            self.assertEqual(changes.loc[0, "Товар"], "item_a")
            self.assertEqual(changes.loc[0, "Сегмент за весь период"], "AX")
            self.assertEqual(changes.loc[0, "Сегмент за 6 месяцев"], "AZ")

    def test_segment_comparison_rejects_duplicate_products(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            duplicate = pd.DataFrame(
                [
                    ["item_a", "A", "X"],
                    ["item_a", "B", "Y"],
                ],
                columns=["Товар", "Группа ABC", "Группа XYZ"],
            )
            valid = pd.DataFrame(
                [["item_a", "A", "X"]],
                columns=["Товар", "Группа ABC", "Группа XYZ"],
            )
            full = root / "all.csv"
            recent = root / "recent.csv"
            duplicate.to_csv(full, index=False, encoding="utf-8-sig")
            valid.to_csv(recent, index=False, encoding="utf-8-sig")

            with self.assertRaises(SystemExit):
                compare_segments(str(full), str(recent), "utf-8-sig", ",", root)


if __name__ == "__main__":
    unittest.main()
