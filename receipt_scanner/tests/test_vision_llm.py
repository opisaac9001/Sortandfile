import unittest
import pathlib
import time
import sys
import os # For creating and removing dummy file more easily

# Assuming tests are run from project root (e.g., /app),
# Python's module discovery should handle imports from receipt_scanner.app
# due to __init__.py files in receipt_scanner/ and receipt_scanner/app/.
from receipt_scanner.app.vision_llm import MockVisionLLM, ReceiptData

class TestMockVisionLLM(unittest.TestCase):
    def setUp(self):
        """
        Set up for each test.
        Creates an instance of the MockVisionLLM and a dummy file for it to process.
        """
        self.llm = MockVisionLLM()
        # Define a name for the dummy file. It will be created in the current working directory
        # (which is typically the project root when running 'python -m unittest discover').
        self.dummy_image_name = "temp_test_receipt_for_vision_llm.jpg"
        self.dummy_image_path = pathlib.Path(self.dummy_image_name)

        # Create the dummy file with some content.
        try:
            self.dummy_image_path.write_text("This is a dummy receipt image file for testing MockVisionLLM.")
        except Exception as e:
            # If file creation fails, it's a setup error, tests might not run correctly.
            print(f"Warning: Could not create dummy file {self.dummy_image_path} in setUp: {e}")


    def tearDown(self):
        """
        Clean up after each test.
        Removes the dummy file created in setUp.
        """
        if self.dummy_image_path.exists():
            try:
                self.dummy_image_path.unlink()
            except Exception as e:
                # If file deletion fails, it might affect subsequent tests or clutter the environment.
                print(f"Warning: Could not delete dummy file {self.dummy_image_path} in tearDown: {e}")


    def test_extract_data_returns_receipt_data_instance_or_none(self):
        """
        Tests that extract_data returns either a ReceiptData object or None.
        The MockVisionLLM has a chance to return None, simulating a failure.
        """
        if not self.dummy_image_path.exists():
            self.fail(f"Setup error: Dummy file {self.dummy_image_path} not created.")

        result = self.llm.extract_data(self.dummy_image_path)
        self.assertTrue(isinstance(result, ReceiptData) or result is None,
                        "Result should be an instance of ReceiptData or None.")

    def test_extract_data_populates_source_file_correctly(self):
        """
        Tests that the 'source_file' field in the returned ReceiptData
        is correctly populated with the absolute path of the input image.
        """
        if not self.dummy_image_path.exists():
            self.fail(f"Setup error: Dummy file {self.dummy_image_path} not created.")

        result = self.llm.extract_data(self.dummy_image_path)
        if result: # Only perform assertion if data extraction was successful
            expected_source_file = str(self.dummy_image_path.resolve())
            self.assertEqual(result.source_file, expected_source_file,
                             f"source_file should be '{expected_source_file}', but got '{result.source_file}'.")
        # If result is None, this test implicitly passes for this aspect,
        # as the condition for checking source_file isn't met.

    def test_extract_data_returns_expected_fields_and_types(self):
        """
        Tests that the ReceiptData object returned by extract_data contains
        the expected fields with plausible data types.
        """
        if not self.dummy_image_path.exists():
            self.fail(f"Setup error: Dummy file {self.dummy_image_path} not created.")

        result = self.llm.extract_data(self.dummy_image_path)
        if result: # Only perform assertions if data extraction was successful
            # Check for presence and type of key fields
            self.assertTrue(hasattr(result, 'vendor'), "Result should have 'vendor' attribute.")
            self.assertIsInstance(result.vendor, (str, type(None)), "Vendor should be str or None.")

            self.assertTrue(hasattr(result, 'date'), "Result should have 'date' attribute.")
            self.assertIsInstance(result.date, (str, type(None)), "Date should be str or None.")

            self.assertTrue(hasattr(result, 'amount'), "Result should have 'amount' attribute.")
            # Amount can be float. In some systems, int might also be acceptable if it's a round number.
            self.assertIsInstance(result.amount, (float, int, type(None)), "Amount should be float, int or None.")

            self.assertTrue(hasattr(result, 'category'), "Result should have 'category' attribute.")
            self.assertIsInstance(result.category, (str, type(None)), "Category should be str or None.")

            self.assertTrue(hasattr(result, 'tags'), "Result should have 'tags' attribute.")
            self.assertIsInstance(result.tags, list, "Tags should be a list.")

            self.assertTrue(hasattr(result, 'confidence_score'), "Result should have 'confidence_score' attribute.")
            self.assertIsInstance(result.confidence_score, (float, type(None))), "Confidence score should be float or None."
            if result.confidence_score is not None:
                self.assertTrue(0.0 <= result.confidence_score <= 1.0,
                                "Confidence score should be between 0.0 and 1.0.")

            self.assertTrue(hasattr(result, 'raw_text'), "Result should have 'raw_text' attribute.")
            self.assertIsInstance(result.raw_text, (str, type(None)), "Raw text should be str or None.")
        # If result is None, this test implicitly passes as field checks are conditional.

    def test_extract_data_simulates_processing_delay(self):
        """
        Tests that the extract_data method simulates a processing delay
        as per the MockVisionLLM's design (sleeps between 0.5 and 1.5 seconds).
        """
        if not self.dummy_image_path.exists():
            self.fail(f"Setup error: Dummy file {self.dummy_image_path} not created.")

        start_time = time.time()
        self.llm.extract_data(self.dummy_image_path)
        end_time = time.time()
        duration = end_time - start_time

        # The mock is designed to sleep for random.uniform(0.5, 1.5).
        # We check if the duration is at least close to the minimum expected sleep time.
        # Allowing for some system overhead, we test if it's >= 0.4s.
        # This test can be a bit sensitive to system load.
        self.assertTrue(duration >= 0.4,
                        f"Processing time was {duration:.4f}s, which is less than the expected minimum simulation delay (approx 0.5s).")

if __name__ == "__main__":
    # This allows running the tests directly from this file (e.g., "python test_vision_llm.py").
    # However, it's generally better to use 'python -m unittest discover' from the project root.
    unittest.main()
