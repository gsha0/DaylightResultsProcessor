"""Unit tests for process_sda.py"""

import os
import sys
import unittest

# Ensure project root is on the path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from process_sda import parse_wpd_file
from sda_utils import load_room_area_lookup

FIXTURES = os.path.join(os.path.dirname(__file__), "fixtures")


class TestParseWpdFile(unittest.TestCase):
    def test_valid_file_b1000220(self):
        result = parse_wpd_file(os.path.join(FIXTURES, "B1000220_SDA.wpd"))
        self.assertEqual(result["ZoneID"], "B1000220")
        self.assertIn("Tenancy Y", result["Room Name"])
        self.assertEqual(result["sDA Pct"], "0.1538")
        # Should have 10 MMA values
        for i in range(1, 11):
            self.assertIn(f"MMA_{i}", result)

    def test_valid_file_b100023c(self):
        result = parse_wpd_file(os.path.join(FIXTURES, "B100023C_SDA.wpd"))
        self.assertEqual(result["ZoneID"], "B100023C")
        self.assertEqual(result["sDA Pct"], "1.0000")

    def test_valid_file_b1000256(self):
        result = parse_wpd_file(os.path.join(FIXTURES, "B1000256_SDA.wpd"))
        self.assertEqual(result["ZoneID"], "B1000256")
        self.assertEqual(result["sDA Pct"], "0.5455")

    def test_missing_zone(self):
        with self.assertRaises(ValueError) as ctx:
            parse_wpd_file(os.path.join(FIXTURES, "no_zone_SDA.wpd"))
        self.assertIn("[Zone]", str(ctx.exception))

    def test_all_invalid_data(self):
        with self.assertRaises(ValueError) as ctx:
            parse_wpd_file(os.path.join(FIXTURES, "all_invalid_SDA.wpd"))
        self.assertIn("No valid data points", str(ctx.exception))

    def test_mma_count(self):
        result = parse_wpd_file(os.path.join(FIXTURES, "B1000220_SDA.wpd"))
        mma_keys = [k for k in result if k.startswith("MMA_")]
        self.assertEqual(len(mma_keys), 10)


class TestLoadRoomAreaLookup(unittest.TestCase):
    def test_valid_lookup(self):
        lookup = load_room_area_lookup(FIXTURES)
        self.assertIsNotNone(lookup)
        self.assertIn("B1000220", lookup)
        self.assertEqual(lookup["B1000220"], "13.879")

    def test_missing_file(self):
        lookup = load_room_area_lookup("/nonexistent/path")
        self.assertIsNone(lookup)

    def test_lookup_keys(self):
        lookup = load_room_area_lookup(FIXTURES)
        self.assertIn("B100023C", lookup)
        self.assertIn("B1000256", lookup)


if __name__ == "__main__":
    unittest.main()
