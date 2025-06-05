import unittest
import pathlib
import shutil
import sys
import os
import uuid

# Ensure the 'receipt_scanner' directory (which contains 'app') is in sys.path
# This allows 'from receipt_scanner.app import ingest'
# Assumes this test script is in receipt_scanner/tests/test_ingest.py
# Project root would then be Path(__file__).parent.parent.parent
# We need the directory containing 'receipt_scanner' to be in the path if we run tests from outside.
# However, if running 'python -m unittest discover -s receipt_scanner/tests' from the project root,
# Python's module resolution should handle this correctly due to __init__.py files.
# For robustness in various execution environments, an explicit path addition can be useful.
# Let's try without explicit sys.path modification first, relying on standard discovery.
# If imports fail, this is the place to adjust.
# sys.path.insert(0, str(pathlib.Path(__file__).parent.parent.parent))

from receipt_scanner.app import ingest

# Mock UploadedFile class
class MockUploadedFile:
    def __init__(self, name, content_bytes):
        self.name = name
        self.content_bytes = content_bytes
        # Simulate 'read' method of a file-like object
        self._pointer = 0
    def read(self):
        # Simple read simulation, returns all content once
        if self._pointer == 0:
            self._pointer = len(self.content_bytes)
            return self.content_bytes
        return b'' # Subsequent reads return empty bytes like a file cursor at EOF

    def seek(self, offset, whence=0): # pylint: disable=unused-argument
        # Basic seek for compatibility if any part of code uses it (though ingest doesn't)
        if whence == 0: # absolute
            self._pointer = offset
        elif whence == 1: # relative
            self._pointer += offset
        elif whence == 2: # from end
            self._pointer = len(self.content_bytes) + offset
        else:
            raise ValueError("invalid whence (%r, should be 0, 1 or 2)" % whence)
        return self._pointer

    def tell(self):
        return self._pointer


class TestIngest(unittest.TestCase):
    def setUp(self):
        # Create a unique temporary directory for each test run or test class
        # to avoid conflicts if tests run in parallel or if teardown fails.
        self.test_dir_parent = pathlib.Path("./temp_test_ingest_data")
        self.test_dir_parent.mkdir(parents=True, exist_ok=True) # Ensure parent for test_dir exists

        # Specific test directory for this test class instance
        self.test_dir = self.test_dir_parent / str(uuid.uuid4())
        self.test_dir.mkdir(parents=True, exist_ok=True)

        self.source_dir = self.test_dir / "source_receipts"
        self.source_dir.mkdir(parents=True, exist_ok=True)

        self.receipts_target_dir = self.test_dir / "target_receipts"
        self.receipts_target_dir.mkdir(parents=True, exist_ok=True)

        # Monkey patch the RECEIPTS_DIR in the ingest module for the duration of the tests
        self.original_receipts_dir = ingest.RECEIPTS_DIR
        ingest.RECEIPTS_DIR = self.receipts_target_dir

        # Monkey patch ALLOWED_EXTENSIONS for consistency if needed, though current tests rely on its definition
        self.original_allowed_extensions = ingest.ALLOWED_EXTENSIONS
        ingest.ALLOWED_EXTENSIONS = {".jpg", ".jpeg", ".png", ".pdf"}


    def tearDown(self):
        # Remove the specific temporary directory for this test class instance
        if self.test_dir.exists():
            shutil.rmtree(self.test_dir)

        # Clean up parent only if it's empty (optional, depends on desired cleanup strategy)
        # if self.test_dir_parent.exists() and not any(self.test_dir_parent.iterdir()):
        #     shutil.rmtree(self.test_dir_parent)

        # Restore original RECEIPTS_DIR and ALLOWED_EXTENSIONS
        ingest.RECEIPTS_DIR = self.original_receipts_dir
        ingest.ALLOWED_EXTENSIONS = self.original_allowed_extensions

    def test_save_uploaded_file_success_jpg(self):
        mock_file = MockUploadedFile("test.jpg", b"dummy jpg data")
        saved_path = ingest.save_uploaded_file(mock_file)
        self.assertIsNotNone(saved_path, "Should return a path for successful save.")
        self.assertTrue(saved_path.exists(), "Saved file should exist.")
        self.assertEqual(saved_path.parent, self.receipts_target_dir, "File should be in the mocked receipts dir.")
        self.assertTrue(saved_path.name.endswith(".jpg"), "File extension should be preserved.")
        # Check if filename is UUID-based (original name is 'test.jpg')
        self.assertNotEqual(saved_path.stem, "test", "Filename stem should be a UUID, not original.")
        # A more robust check for UUID might involve regex, but length diff is a good heuristic
        self.assertTrue(len(saved_path.stem) > 30, "Filename stem should be long like a UUID.")

    def test_save_uploaded_file_success_pdf(self):
        mock_file = MockUploadedFile("document.pdf", b"dummy pdf data")
        saved_path = ingest.save_uploaded_file(mock_file)
        self.assertIsNotNone(saved_path)
        self.assertTrue(saved_path.exists())
        self.assertEqual(saved_path.suffix.lower(), ".pdf")

    def test_save_uploaded_file_unsupported_type_txt(self):
        mock_file = MockUploadedFile("test.txt", b"dummy text data")
        saved_path = ingest.save_uploaded_file(mock_file)
        self.assertIsNone(saved_path, "Should return None for unsupported file types.")
        # Check that no file was created in the target directory
        self.assertEqual(len(list(self.receipts_target_dir.iterdir())), 0, "No file should be created for unsupported type.")

    def test_save_uploaded_file_unique_names_for_same_original_name(self):
        mock_file1 = MockUploadedFile("same_name.png", b"dummy png data 1")
        # Reset read pointer for mock_file2 if it were the same object, but it's a new one.
        mock_file2 = MockUploadedFile("same_name.png", b"dummy png data 2")

        saved_path1 = ingest.save_uploaded_file(mock_file1)
        saved_path2 = ingest.save_uploaded_file(mock_file2)

        self.assertIsNotNone(saved_path1, "First file should save successfully.")
        self.assertIsNotNone(saved_path2, "Second file should save successfully.")
        self.assertTrue(saved_path1.exists())
        self.assertTrue(saved_path2.exists())
        self.assertNotEqual(saved_path1.name, saved_path2.name, "Saved filenames should be unique even if original names are the same.")
        self.assertEqual(saved_path1.suffix, ".png")
        self.assertEqual(saved_path2.suffix, ".png")

    def test_scan_folder_empty_source_directory(self):
        copied_files = ingest.scan_folder_for_receipts(str(self.source_dir))
        self.assertEqual(len(copied_files), 0, "Should return an empty list for an empty source directory.")

    def test_scan_folder_with_only_allowed_file_types(self):
        (self.source_dir / "receipt1.jpg").write_bytes(b"dummy image data one")
        (self.source_dir / "document1.pdf").write_bytes(b"dummy pdf data one")

        copied_files = ingest.scan_folder_for_receipts(str(self.source_dir))
        self.assertEqual(len(copied_files), 2, "Should copy two allowed files.")

        target_filenames = {f.name for f in self.receipts_target_dir.iterdir()}
        self.assertEqual(len(target_filenames), 2, "Two files should be in the target directory.")
        for f_path in copied_files:
            self.assertTrue(f_path.exists(), f"Copied file {f_path} should exist.")
            self.assertEqual(f_path.parent, self.receipts_target_dir, "Copied file should be in target directory.")
            self.assertTrue(f_path.suffix.lower() in ingest.ALLOWED_EXTENSIONS, "Copied file should have an allowed extension.")

    def test_scan_folder_with_mixed_allowed_and_disallowed_files(self):
        (self.source_dir / "receipt_pic.png").write_bytes(b"png image data")
        (self.source_dir / "important_notes.txt").write_bytes(b"this is a text file")
        (self.source_dir / "another_receipt.jpeg").write_bytes(b"jpeg image data")
        (self.source_dir / "archive.zip").write_bytes(b"zip file data")

        copied_files = ingest.scan_folder_for_receipts(str(self.source_dir))
        self.assertEqual(len(copied_files), 2, "Should only copy the two allowed files (png, jpeg).")

        copied_extensions = {f_path.suffix.lower() for f_path in copied_files}
        self.assertIn(".png", copied_extensions)
        self.assertIn(".jpeg", copied_extensions)
        self.assertNotIn(".txt", copied_extensions)
        self.assertNotIn(".zip", copied_extensions)

        target_filenames = {f.name for f in self.receipts_target_dir.iterdir()}
        self.assertEqual(len(target_filenames), 2, "Only two files should be in the target directory.")


    def test_scan_folder_source_directory_does_not_exist(self):
        non_existent_source_dir = self.test_dir / "this_folder_does_not_exist"
        # Ensure it really doesn't exist before test
        self.assertFalse(non_existent_source_dir.exists())

        copied_files = ingest.scan_folder_for_receipts(str(non_existent_source_dir))
        self.assertEqual(len(copied_files), 0, "Should return an empty list if source directory doesn't exist.")

    def test_scan_folder_copied_files_receive_unique_names(self):
        # Create two files with the same name in different subdirectories of source_dir (or just two distinct files)
        # This test primarily ensures that all copied files end up with UUID names.
        (self.source_dir / "my_receipt.jpg").write_bytes(b"image data version 1")

        # Create another directory inside source_dir to test recursion (though scan_folder isn't recursive)
        # For this test, just another file is fine.
        (self.source_dir / "another_receipt.pdf").write_bytes(b"pdf data version 1")

        copied_files = ingest.scan_folder_for_receipts(str(self.source_dir))
        self.assertEqual(len(copied_files), 2)

        names = set()
        for f_path in copied_files:
            self.assertTrue(f_path.exists())
            self.assertNotEqual(f_path.stem, "my_receipt") # Original stem
            self.assertNotEqual(f_path.stem, "another_receipt") # Original stem
            self.assertTrue(len(f_path.stem) > 30) # UUID-like length
            names.add(f_path.name)
        self.assertEqual(len(names), 2, "All copied filenames must be unique.")

    def test_scan_folder_does_not_copy_subdirectories(self):
        (self.source_dir / "receipt_in_root.jpg").write_bytes(b"root image")
        subdir = self.source_dir / "subfolder"
        subdir.mkdir()
        (subdir / "receipt_in_sub.pdf").write_bytes(b"sub image")

        copied_files = ingest.scan_folder_for_receipts(str(self.source_dir))
        self.assertEqual(len(copied_files), 1, "Should only copy files from the root of source_dir, not subdirectories.")
        self.assertTrue(copied_files[0].name.endswith(".jpg"))


if __name__ == "__main__":
    # This allows running the tests directly from this file, e.g., "python test_ingest.py"
    # It's often better to use 'python -m unittest discover' from the project root.
    unittest.main()
