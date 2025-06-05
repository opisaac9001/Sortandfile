import unittest
import pathlib
import pandas as pd
import os
import shutil # For rmtree
from typing import List, Dict, Any # For sample data type hints

# Assuming tests are run from project root, so app can be imported
from receipt_scanner.app import export # To monkeypatch EXPORTS_DIR
from receipt_scanner.app.export import export_to_excel, export_to_csv, _prepare_dataframe, PREFERRED_EXPORT_COLUMNS

class TestExportFunctions(unittest.TestCase):
    def setUp(self):
        self.sample_receipts: List[Dict[str, Any]] = [
            {'id': 1, 'date': '2023-01-01', 'vendor': 'Store A', 'amount': 10.0, 'category': 'Food', 'tags': ['food', 'urgent'], 'notes': 'Lunch', 'needs_review': False},
            {'id': 2, 'date': '2023-01-02', 'vendor': 'Store B', 'amount': 20.5, 'category': 'Electronics', 'tags': ['tech'], 'notes': 'Cable', 'needs_review': True},
            {'id': 3, 'date': '2023-01-03', 'vendor': 'Store C', 'amount': 5.75, 'category': 'Coffee', 'tags': [], 'notes': 'Morning coffee', 'needs_review': False},
            {'id': 4, 'date': None, 'vendor': 'Store D', 'amount': None, 'category': None, 'tags': None, 'notes': None, 'needs_review': True, 'extra_field': 'extra_val'},
            {'id': 5, 'date': '2023-01-05', 'vendor': 'Store E', 'amount': 15.0, 'category': 'Books', 'tags': "single_tag_as_string", 'notes': 'Book', 'needs_review': False} # Test tag as string
        ]

        # Create a temporary directory for exports
        self.test_exports_dir = pathlib.Path("./temp_test_exports_dir")
        self.test_exports_dir.mkdir(parents=True, exist_ok=True)

        # Monkey patch EXPORTS_DIR in the export module
        self.original_exports_dir = export.EXPORTS_DIR
        export.EXPORTS_DIR = self.test_exports_dir

    def tearDown(self):
        # Restore original EXPORTS_DIR
        export.EXPORTS_DIR = self.original_exports_dir
        # Remove the temporary directory and its contents
        if self.test_exports_dir.exists():
            shutil.rmtree(self.test_exports_dir)

    def test_prepare_dataframe_empty_input(self):
        df = _prepare_dataframe([])
        self.assertIsNone(df, "Should return None for empty list input.")

    def test_prepare_dataframe_tags_conversion(self):
        df = _prepare_dataframe(self.sample_receipts)
        self.assertIsNotNone(df)
        self.assertIn('tags', df.columns)

        # Check specific tag conversions
        self.assertEqual(df.loc[df['id'] == 1, 'tags'].iloc[0], "food, urgent")
        self.assertEqual(df.loc[df['id'] == 2, 'tags'].iloc[0], "tech")
        self.assertEqual(df.loc[df['id'] == 3, 'tags'].iloc[0], "")  # Empty list becomes empty string
        self.assertEqual(df.loc[df['id'] == 4, 'tags'].iloc[0], "")  # None tags becomes empty string
        self.assertEqual(df.loc[df['id'] == 5, 'tags'].iloc[0], "single_tag_as_string") # String tags remain as is

    def test_prepare_dataframe_column_order_and_content(self):
        df = _prepare_dataframe(self.sample_receipts)
        self.assertIsNotNone(df)

        # Check if preferred columns are first and in order (if they exist in data)
        expected_initial_cols = [col for col in PREFERRED_EXPORT_COLUMNS if col in df.columns]
        for i, col_name in enumerate(expected_initial_cols):
            self.assertEqual(df.columns[i], col_name)

        # Check if 'extra_field' (not in preferred) is at the end
        if 'extra_field' in df.columns:
             self.assertIn('extra_field', df.columns[-1]) # It might not be the very last if multiple extra

        # Check a few values
        self.assertEqual(df.loc[df['id'] == 1, 'vendor'].iloc[0], 'Store A')
        self.assertEqual(df.loc[df['id'] == 2, 'amount'].iloc[0], 20.5)
        self.assertEqual(df.loc[df['id'] == 4, 'needs_review'].iloc[0], True) # Assuming needs_review is passed through

    def test_export_to_excel_creates_file(self):
        filename = "test_receipts.xlsx" # Test with extension
        filepath_str = export_to_excel(self.sample_receipts, filename)
        self.assertIsNotNone(filepath_str)

        filepath = pathlib.Path(filepath_str)
        self.assertTrue(filepath.exists(), f"Excel file should be created at {filepath}")
        self.assertEqual(filepath.name, filename)
        self.assertTrue(filepath.parent == self.test_exports_dir.resolve()) # Check it's in the temp dir

        # Optional: Read back and verify basic properties
        try:
            df_read = pd.read_excel(filepath)
            self.assertEqual(len(df_read), len(self.sample_receipts))
            self.assertIn('vendor', df_read.columns)
        except Exception as e:
            self.fail(f"Failed to read back exported Excel file: {e}")

    def test_export_to_excel_no_extension_in_filename(self):
        filename_no_ext = "test_receipts_no_ext"
        expected_filename = filename_no_ext + ".xlsx"
        filepath_str = export_to_excel(self.sample_receipts, filename_no_ext)
        self.assertIsNotNone(filepath_str)
        filepath = pathlib.Path(filepath_str)
        self.assertTrue(filepath.exists())
        self.assertEqual(filepath.name, expected_filename)

    def test_export_to_excel_empty_data(self):
        filepath = export_to_excel([], "empty_export.xlsx")
        self.assertIsNone(filepath, "Exporting empty data to Excel should return None.")

    def test_export_to_csv_creates_file(self):
        filename = "test_receipts.csv"
        filepath_str = export_to_csv(self.sample_receipts, filename)
        self.assertIsNotNone(filepath_str)

        filepath = pathlib.Path(filepath_str)
        self.assertTrue(filepath.exists(), f"CSV file should be created at {filepath}")
        self.assertEqual(filepath.name, filename)
        self.assertTrue(filepath.parent == self.test_exports_dir.resolve())

        # Optional: Read back and verify
        try:
            df_read = pd.read_csv(filepath)
            self.assertEqual(len(df_read), len(self.sample_receipts))
            self.assertIn('tags', df_read.columns) # Check if tags (now string) is there
            # For CSV, tags would be "food, urgent". For Excel, it might be just "food, urgent"
            # This was handled by _prepare_dataframe
            self.assertEqual(df_read.loc[df_read['id'] == 1, 'tags'].iloc[0], "food, urgent")

        except Exception as e:
            self.fail(f"Failed to read back exported CSV file: {e}")

    def test_export_to_csv_no_extension_in_filename(self):
        filename_no_ext = "test_receipts_no_ext_csv"
        expected_filename = filename_no_ext + ".csv"
        filepath_str = export_to_csv(self.sample_receipts, filename_no_ext)
        self.assertIsNotNone(filepath_str)
        filepath = pathlib.Path(filepath_str)
        self.assertTrue(filepath.exists())
        self.assertEqual(filepath.name, expected_filename)

    def test_export_to_csv_empty_data(self):
        filepath = export_to_csv([], "empty_export.csv")
        self.assertIsNone(filepath, "Exporting empty data to CSV should return None.")

if __name__ == '__main__':
    unittest.main()
