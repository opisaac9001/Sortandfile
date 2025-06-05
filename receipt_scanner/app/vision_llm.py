# Placeholder for vision_llm.py
# This module will contain classes and functions for interacting with
# Vision-capable Large Language Models (LLMs) to extract data from receipts.

import abc
import pathlib
from typing import List, Optional, Dict

from pydantic import BaseModel, Field

import time
import random
import datetime

class ReceiptData(BaseModel):
    """
    Pydantic model to store structured data extracted from a receipt.
    """
    vendor: Optional[str] = Field(default=None, description="Name of the vendor or store.")
    date: Optional[str] = Field(default=None, description="Date of the transaction (YYYY-MM-DD or other format).")
    amount: Optional[float] = Field(default=None, description="Total amount of the transaction.")
    category: Optional[str] = Field(default="Uncategorized", description="Category of the expense.")
    tags: List[str] = Field(default_factory=list, description="Custom tags for the receipt.")
    payment_method: Optional[str] = Field(default=None, description="Method of payment.")
    notes: Optional[str] = Field(default=None, description="User-added notes about the transaction.")
    location: Optional[str] = Field(default=None, description="Location of the vendor.")

    source_file: str = Field(description="Path to the original receipt image or PDF file.")

    confidence_score: Optional[float] = Field(default=None, description="Overall confidence score for the extracted data (0.0 to 1.0).")
    raw_text: Optional[str] = Field(default=None, description="Full raw text extracted from the receipt by OCR, if available.")

    needs_review: bool = Field(default=False, description="Flag indicating if the extracted data needs manual review.")

    class Config:
        validate_assignment = True

class VisionLLMConnector(abc.ABC):
    """
    Abstract Base Class for connectors to different Vision LLM services.
    """
    @abc.abstractmethod
    def extract_data(self, image_path: pathlib.Path) -> Optional[ReceiptData]:
        """
        Extracts structured data from a given receipt image file.
        """
        pass

class MockVisionLLM(VisionLLMConnector):
    """
    Mock implementation of the VisionLLMConnector for testing and development.
    """
    def extract_data(self, image_path: pathlib.Path) -> Optional[ReceiptData]:
        if not isinstance(image_path, pathlib.Path):
            try: image_path = pathlib.Path(image_path)
            except TypeError: print(f"Error: image_path must be a pathlib.Path or string, got {type(image_path)}"); return None

        print(f"MockVisionLLM: Processing image '{image_path.name}'...")
        try:
            time.sleep(random.uniform(0.5, 1.5))
            if random.random() < 0.05: # 5% chance of simulated failure
                print(f"MockVisionLLM: Simulated processing failure for '{image_path.name}'.")
                return None

            confidence = round(random.uniform(0.65, 0.98), 2) # Generate confidence first
            mock_data = ReceiptData(
                vendor=random.choice(["MockMart", "TestCo Retail", "Fake Emporium", "General Goods Inc."]),
                date=datetime.date.today().isoformat(),
                amount=round(random.uniform(1.0, 350.0), 2),
                category=random.choice(["Groceries", "Electronics", "Office Supplies", "Travel", "Dining", "Utilities"]),
                tags=["mock", random.choice(["personal", "business", "travel-related", "office-expense"])],
                payment_method=random.choice(["Credit Card (Visa ****1234)", "Debit Card (MC ****5678)", "Cash", "Mobile Pay"]),
                notes=f"This is a mock receipt processed for file: {image_path.name}.",
                location=random.choice(["Springfield, IL", "Anytown, USA", "Shelbyville, CA", "Metropolis, NY"]),
                source_file=str(image_path.resolve()),
                confidence_score=confidence, # Use the generated confidence
                raw_text=f"Mock OCR Output for: {image_path.name}\nTOTAL: {round(random.uniform(50,150),2)}"
            )

            # Set needs_review based on confidence score
            if mock_data.confidence_score is not None and mock_data.confidence_score < 0.80:
                mock_data.needs_review = True

            print(f"MockVisionLLM: Successfully extracted mock data for '{image_path.name}' (Needs Review: {mock_data.needs_review}).")
            return mock_data
        except Exception as e:
            print(f"An unexpected error in MockVisionLLM for {image_path.name}: {e}")
            return None

if __name__ == '__main__':
    print("Testing ReceiptData model and MockVisionLLM...")
    temp_test_dir = pathlib.Path("./temp_mock_llm_test")
    temp_test_dir.mkdir(exist_ok=True)
    dummy_receipt_file = temp_test_dir / "example_receipt.jpg"
    try:
        dummy_receipt_file.write_text("This is a dummy receipt image file for testing.")
        print(f"\nCreated dummy file: {dummy_receipt_file.resolve()}")

        mock_llm_instance = MockVisionLLM()
        print("\nAttempting to extract data using MockVisionLLM:")

        for i in range(5): # Test a few times to see needs_review logic
            print(f"\n--- Extraction Attempt {i+1} ---")
            extracted_data = mock_llm_instance.extract_data(dummy_receipt_file)
            if extracted_data:
                print("\nSuccessfully extracted mock data:")
                print(extracted_data.model_dump_json(indent=2))
                assert extracted_data.source_file == str(dummy_receipt_file.resolve())
                assert extracted_data.vendor is not None
                if extracted_data.confidence_score is not None:
                    expected_needs_review = extracted_data.confidence_score < 0.80
                    assert extracted_data.needs_review == expected_needs_review, \
                        f"Needs review flag mismatch for score {extracted_data.confidence_score}"
            else:
                print("\nMockVisionLLM returned None (simulated failure or error).")

    finally:
        if dummy_receipt_file.exists(): dummy_receipt_file.unlink()
        if temp_test_dir.exists(): temp_test_dir.rmdir()
        print("\nCleaned up dummy file and directory.")

    print("\nTesting direct ReceiptData instantiation with needs_review:")
    try:
        direct_data = ReceiptData(
            vendor="DirectMart", date="2024-07-04", amount=76.54,
            source_file=str(dummy_receipt_file.resolve()),
            tags=["direct", "holiday"], needs_review=True
        )
        print(direct_data.model_dump_json(indent=2))
        assert direct_data.category == "Uncategorized"
        assert direct_data.needs_review is True
    except Exception as e:
        print(f"Error during direct ReceiptData instantiation: {e}")
