"""Unit tests for process_csv.py"""

import csv
import os
import sys
import tempfile
import unittest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from process_csv import detect_level, weighted_avg_sda, run


class TestDetectLevel(unittest.TestCase):
    CODES = ["GF", "MZ", "L1", "L2", "L3", "L4"]

    def test_exact_match(self):
        self.assertEqual(detect_level("Room L3-001", self.CODES), "L3")

    def test_no_match(self):
        self.assertEqual(detect_level("Some Room Name", self.CODES), "Other")

    def test_multi_match(self):
        self.assertEqual(detect_level("Room L3 to L4 corridor", self.CODES), "Multi")

    def test_case_insensitive(self):
        self.assertEqual(detect_level("room l3-001", self.CODES), "L3")
        self.assertEqual(detect_level("ground floor gf area", self.CODES), "GF")

    def test_word_boundary(self):
        # "L1" should not match "L10"
        self.assertEqual(detect_level("Room L10-001", self.CODES), "Other")

    def test_word_boundary_prefix(self):
        # "L1" should not match "AL1"
        self.assertEqual(detect_level("Room AL1-001", self.CODES), "Other")

    def test_empty_room_name(self):
        self.assertEqual(detect_level("", self.CODES), "Other")

    def test_embedded_in_parentheses(self):
        self.assertEqual(
            detect_level("C01.03.711 Tenancy Y (VAV-W-L3-342)", self.CODES), "L3"
        )


class TestWeightedAvgSda(unittest.TestCase):
    def test_normal(self):
        rooms = [
            {"_area": 10.0, "_sda": 0.5},
            {"_area": 20.0, "_sda": 1.0},
        ]
        avg, total = weighted_avg_sda(rooms)
        self.assertAlmostEqual(avg, (10 * 0.5 + 20 * 1.0) / 30)
        self.assertAlmostEqual(total, 30.0)

    def test_empty(self):
        avg, total = weighted_avg_sda([])
        self.assertIsNone(avg)
        self.assertAlmostEqual(total, 0.0)

    def test_single_room(self):
        rooms = [{"_area": 15.0, "_sda": 0.75}]
        avg, total = weighted_avg_sda(rooms)
        self.assertAlmostEqual(avg, 0.75)
        self.assertAlmostEqual(total, 15.0)


class TestIntegration(unittest.TestCase):
    """Integration test: run full pipeline on fixture data."""

    def test_full_pipeline(self):
        fixtures = os.path.join(os.path.dirname(__file__), "fixtures")

        # First, run process_sda extraction into a temp dir
        from process_sda import run as run_sda
        import logging
        logging.basicConfig(level=logging.WARNING)

        with tempfile.TemporaryDirectory() as tmpdir:
            # Copy WPD files and RoomArea.csv to temp dir
            import shutil
            for f in os.listdir(fixtures):
                shutil.copy2(os.path.join(fixtures, f), tmpdir)

            # Run extraction (exclude edge-case fixtures)
            csv_path = run_sda(
                folder=tmpdir,
                output="test_output.csv",
                pattern="B*_SDA.wpd",
            )
            self.assertIsNotNone(csv_path)
            self.assertTrue(os.path.exists(csv_path))

            # Verify extraction output
            with open(csv_path, encoding="utf-8-sig") as f:
                reader = csv.DictReader(f)
                rows = list(reader)
            self.assertEqual(len(rows), 3)
            zone_ids = {r["ZoneID"] for r in rows}
            self.assertEqual(zone_ids, {"B1000220", "B100023C", "B1000256"})

            # Run post-processing
            processed_path = os.path.join(tmpdir, "test_output_processed.csv")
            run(input_path=csv_path, output_path=processed_path)

            self.assertTrue(os.path.exists(processed_path))

            # Verify processed output has Level column
            with open(processed_path, encoding="utf-8-sig") as f:
                reader = csv.DictReader(f)
                proc_rows = list(reader)
            self.assertEqual(len(proc_rows), 3)
            self.assertIn("Level", reader.fieldnames)

            # Verify summary
            summary_path = os.path.join(tmpdir, "test_output_processed_summary.csv")
            self.assertTrue(os.path.exists(summary_path))
            with open(summary_path, encoding="utf-8-sig") as f:
                reader = csv.DictReader(f)
                summary_rows = list(reader)

            # Find WHOLE BUILDING row
            building_row = next(r for r in summary_rows if r["Level"] == "WHOLE BUILDING")
            self.assertAlmostEqual(float(building_row["Weighted sDA"]), 0.5801, places=4)
            self.assertAlmostEqual(float(building_row["Total Area (m²)"]), 51.750, places=3)
            self.assertEqual(building_row["Room Count"], "3")


if __name__ == "__main__":
    unittest.main()
