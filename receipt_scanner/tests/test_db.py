import unittest
import pathlib
import sqlite3
import json
import os
import sys
import shutil

from receipt_scanner.app import db
from receipt_scanner.app.db import (
    initialize_database, save_receipt_data, get_receipt_by_id,
    get_all_receipts, search_receipts, update_receipt_category,
    update_receipt_tags, get_distinct_categories, get_distinct_tags,
    update_receipt_review_status, backup_database,
    count_receipts_for_tag, rename_tag_globally, delete_tag_globally,
    count_search_results # Added import
)
from receipt_scanner.app.vision_llm import ReceiptData

class TestDatabaseOperations(unittest.TestCase):
    def _add_sample_receipts(self):
        self.sample_receipts_data = [
            ReceiptData(vendor="GroceryMart", date="2023-10-01", amount=50.00, category="Groceries", tags=["food", "weekly"], source_file="/img/r1.jpg", notes="Weekly groceries", raw_text="GroceryMart receipt for apples and milk", needs_review=False),
            ReceiptData(vendor="TechStore", date="2023-10-05", amount=250.00, category="Electronics", tags=["tech", "gadget"], source_file="/img/r2.png", notes="New keyboard", raw_text="TechStore invoice for RGB keyboard", needs_review=True),
            ReceiptData(vendor="GroceryMart", date="2023-10-08", amount=30.00, category="Groceries", tags=["food", "snacks"], source_file="/img/r3.pdf", notes="Snacks for party", raw_text="GroceryMart receipt for chips and soda", needs_review=False),
            ReceiptData(vendor="OfficeSuppliesCo", date="2023-10-02", amount=75.00, category="Office", tags=["work", "stationery"], source_file="/img/r4.jpg", notes="Pens and paper", raw_text="Invoice for office supplies: pens, paper, stationery", needs_review=True),
            ReceiptData(vendor="BookWorld", date="2023-11-01", amount=25.00, category="Books", tags=["reading", "hobby", "tech"], source_file="/img/r5.jpg", notes="New tech manual", raw_text="BookWorld: The Art of Unit Testing", needs_review=False),
            ReceiptData(vendor="EmptyStore", date="2023-10-10", amount=10.00, category="", tags=[], source_file="/img/r6.jpg", notes="Empty category and tags test", raw_text="Empty data", needs_review=False)
        ]
        self.sample_receipt_ids = [save_receipt_data(r) for r in self.sample_receipts_data]
        self.all_receipt_data_map = {id: data for id, data in zip(self.sample_receipt_ids, self.sample_receipts_data)}
        self.r1_id, self.r2_id, self.r3_id, self.r4_id, self.r5_id, self.r6_id = self.sample_receipt_ids
        # Assign individual data for easier access in tests if needed
        for i, r_id in enumerate(self.sample_receipt_ids):
            setattr(self, f"r{i+1}_data", self.all_receipt_data_map[r_id])


    def setUp(self):
        self.test_dir = pathlib.Path("./temp_unittest_data_dir_phase9")
        self.test_dir.mkdir(parents=True, exist_ok=True)
        self.test_db_name = "test_receipts_phase9.sqlite"
        self.test_db_path = self.test_dir / self.test_db_name
        self.test_backups_dir = self.test_dir / "backups_for_test_phase9"
        self.original_db_path = db.DATABASE_PATH
        self.original_backups_dir = db.BACKUPS_DIR
        db.DATABASE_PATH = self.test_db_path
        db.BACKUPS_DIR = self.test_backups_dir
        initialize_database()
        self._add_sample_receipts()

    def tearDown(self):
        db.DATABASE_PATH = self.original_db_path
        db.BACKUPS_DIR = self.original_backups_dir
        if self.test_dir.exists():
            try: shutil.rmtree(self.test_dir)
            except Exception as e: print(f"Warning: Could not delete temp dir {self.test_dir}: {e}")

    # --- Existing tests (abbreviated for diff clarity, no functional change in them) ---
    def test_initialize_database_creates_table_and_columns(self):
        conn = sqlite3.connect(self.test_db_path); cursor = conn.cursor()
        cursor.execute("PRAGMA table_info(receipts);"); columns_info = cursor.fetchall()
        column_details = {info[1]: info for info in columns_info}
        self.assertIn('needs_review', column_details); self.assertEqual(column_details['needs_review'][2].upper(), 'INTEGER'); self.assertEqual(column_details['needs_review'][4], '0')
        conn.close()
    def test_save_receipt_data_inserts_row_correctly_and_needs_review(self):
        r_data = ReceiptData(vendor="SaveTest", date="2024-01-01", amount=1.0, source_file="/s.jpg", needs_review=True)
        r_id = save_receipt_data(r_data); retrieved = get_receipt_by_id(r_id)
        self.assertTrue(retrieved['needs_review'])
    def test_backup_database_creates_file_correctly(self): # Renamed from test_backup_database_creates_file
        backup_filepath_str = backup_database("test_suite_backup")
        self.assertIsNotNone(backup_filepath_str); backup_filepath = pathlib.Path(backup_filepath_str)
        self.assertTrue(backup_filepath.exists()); self.assertTrue(backup_filepath.name.startswith("test_suite_backup_"))
        self.assertEqual(backup_filepath.stat().st_size, self.test_db_path.stat().st_size)
    # Search tests for amount
    def test_search_receipts_by_amount_min_only(self): self.assertEqual(len(search_receipts(amount_min=50.0)), 3)
    def test_search_receipts_by_amount_max_only(self): self.assertEqual(len(search_receipts(amount_max=50.0)), 4)
    def test_search_receipts_by_amount_min_and_max(self): self.assertEqual(len(search_receipts(amount_min=30.0, amount_max=75.0)), 3)
    def test_search_receipts_by_amount_range_no_match(self): self.assertEqual(len(search_receipts(amount_min=500.0)), 0)
    def test_search_receipts_by_amount_exact_match(self): self.assertEqual(len(search_receipts(amount_min=50.0, amount_max=50.0)), 1)
    # Tag count tests
    def test_count_receipts_for_tag_existing(self): self.assertEqual(count_receipts_for_tag("food"), 2)
    def test_count_receipts_for_tag_existing_single(self): self.assertEqual(count_receipts_for_tag("weekly"), 1)
    def test_count_receipts_for_tag_non_existent(self): self.assertEqual(count_receipts_for_tag("nonexistent"), 0)
    def test_count_receipts_for_tag_case_sensitivity(self):
        # SQLite's LIKE is case-insensitive by default for ASCII.
        # The pattern '%"tag"%' will match '%"Food"%' if the stored tag is "food".
        # Our sample data has "food" (lowercase).
        self.assertEqual(count_receipts_for_tag("Food"), 2)
        self.assertEqual(count_receipts_for_tag("food"), 2)
    # Global tag rename tests
    def test_rename_tag_globally_basic_rename(self):
        rename_count = rename_tag_globally("weekly", "recurring"); self.assertEqual(rename_count, 1)
        self.assertEqual(count_receipts_for_tag("weekly"), 0); self.assertEqual(count_receipts_for_tag("recurring"), 1)
        r1_updated = get_receipt_by_id(self.r1_id); self.assertIn("recurring", r1_updated['tags'])
    def test_rename_tag_globally_to_existing_tag(self): # weekly (on r1) -> food (on r1, r3)
        rename_count = rename_tag_globally("weekly", "food"); self.assertEqual(rename_count, 1)
        self.assertEqual(count_receipts_for_tag("weekly"), 0); self.assertEqual(count_receipts_for_tag("food"), 2)
        r1_updated = get_receipt_by_id(self.r1_id); self.assertListEqual(sorted(r1_updated['tags']), ["food"])
    # Global tag delete tests
    def test_delete_tag_globally_existing_tag(self):
        delete_count = delete_tag_globally("work"); self.assertEqual(delete_count, 1)
        self.assertEqual(count_receipts_for_tag("work"), 0)
        r4_updated = get_receipt_by_id(self.r4_id); self.assertNotIn("work", r4_updated['tags'])

    # --- Tests for count_search_results ---
    def test_count_search_results_no_filters(self):
        count = count_search_results()
        self.assertEqual(count, len(self.sample_receipt_ids))

    def test_count_search_results_by_vendor(self):
        count = count_search_results(vendor="GroceryMart") # r1, r3
        self.assertEqual(count, 2)

    def test_count_search_results_by_category(self):
        count = count_search_results(category="Electronics") # r2
        self.assertEqual(count, 1)

    def test_count_search_results_by_date_range(self):
        count = count_search_results(date_from="2023-10-01", date_to="2023-10-05") # r1, r2, r4
        self.assertEqual(count, 3)

    def test_count_search_results_by_single_tag(self):
        count = count_search_results(tags_include_any=["weekly"]) # r1
        self.assertEqual(count, 1)

    def test_count_search_results_by_multiple_tags_any(self):
        count = count_search_results(tags_include_any=["food", "tech"]) # r1,r3 (food); r2,r5 (tech) = 4 unique receipts
        self.assertEqual(count, 4)

    def test_count_search_results_by_search_term(self):
        count = count_search_results(search_term="keyboard") # r2 (notes, raw_text)
        self.assertEqual(count, 1)

    def test_count_search_results_by_needs_review_true(self):
        count = count_search_results(needs_review_filter=True) # r2, r4
        self.assertEqual(count, 2)

    def test_count_search_results_by_needs_review_false(self):
        count = count_search_results(needs_review_filter=False) # r1, r3, r5, r6
        self.assertEqual(count, 4)

    def test_count_search_results_by_amount_min(self):
        count = count_search_results(amount_min=75.0) # r2 (250), r4 (75)
        self.assertEqual(count, 2)

    def test_count_search_results_by_amount_max(self):
        count = count_search_results(amount_max=30.0) # r3 (30), r5 (25), r6 (10)
        self.assertEqual(count, 3)

    def test_count_search_results_by_amount_range(self):
        count = count_search_results(amount_min=25.0, amount_max=75.0) # r1(50), r3(30), r4(75), r5(25)
        self.assertEqual(count, 4)

    def test_count_search_results_combined_filters(self):
        # GroceryMart (r1, r3), tag "food" (r1, r3), amount_max 40.0 (r3)
        count = count_search_results(vendor="GroceryMart", tags_include_any=["food"], amount_max=40.0)
        self.assertEqual(count, 1) # Should be r3

    def test_count_search_results_no_match(self):
        count = count_search_results(vendor="NonExistent SuperStore")
        self.assertEqual(count, 0)

if __name__ == '__main__':
    unittest.main()
