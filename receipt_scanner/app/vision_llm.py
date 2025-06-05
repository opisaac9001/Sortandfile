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
import requests # Added for OllamaVisionLLMConnector
import base64   # Added for OllamaVisionLLMConnector
import json     # Added for OllamaVisionLLMConnector (parsing nested JSON)

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

class MockVisionLLM(VisionLLMConnector): # ... (MockVisionLLM class remains unchanged) ...
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
            if random.random() < 0.05:
                print(f"MockVisionLLM: Simulated processing failure for '{image_path.name}'.")
                return None

            confidence = round(random.uniform(0.65, 0.98), 2)
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
                confidence_score=confidence,
                raw_text=f"Mock OCR Output for: {image_path.name}\nTOTAL: {round(random.uniform(50,150),2)}"
            )
            if mock_data.confidence_score is not None and mock_data.confidence_score < 0.80:
                mock_data.needs_review = True
            print(f"MockVisionLLM: Successfully extracted mock data for '{image_path.name}' (Needs Review: {mock_data.needs_review}).")
            return mock_data
        except Exception as e:
            print(f"An unexpected error in MockVisionLLM for {image_path.name}: {e}")
            return None

class OllamaVisionLLMConnector(VisionLLMConnector):
    def __init__(self, ollama_base_url: str = "http://localhost:11434", model_name: str = "llava:latest"):
        self.ollama_base_url = ollama_base_url.rstrip('/')
        self.model_name = model_name
        self.api_url = f"{self.ollama_base_url}/api/generate"
        print(f"OllamaVisionLLMConnector initialized for model '{self.model_name}' at '{self.api_url}'")

    def _encode_image_to_base64(self, image_path: pathlib.Path) -> Optional[str]:
        try:
            with open(image_path, "rb") as image_file:
                image_bytes = image_file.read()
                base64_bytes = base64.b64encode(image_bytes)
                return base64_bytes.decode('utf-8')
        except FileNotFoundError:
            print(f"❌ Error: Image file not found at {image_path}")
            return None
        except Exception as e:
            print(f"❌ Error encoding image {image_path} to base64: {e}")
            return None

    def extract_data(self, image_path: pathlib.Path) -> Optional[ReceiptData]:
        print(f"OllamaVisionLLM: Starting data extraction for image: {image_path.name}")
        base64_image_string = self._encode_image_to_base64(image_path)
        if base64_image_string is None:
            return None

        prompt = f'''You are an expert receipt processing AI. Analyze the provided receipt image and extract the following information. Return ONLY a valid JSON object with the specified fields. Do not include any explanatory text or markdown formatting before or after the JSON.

        JSON fields to extract:
        - vendor: string (name of the store or vendor)
        - date: string (date of the receipt in YYYY-MM-DD format. If year is missing, assume current year. If format is different, convert it.)
        - amount: float (total amount paid)
        - category: string (e.g., "Groceries", "Electronics", "Restaurant", "Travel", "Office Supplies", "Other". Infer from items if possible.)
        - tags: list of strings (relevant keywords or items from the receipt, e.g., ["milk", "apples", "printer ink"])
        - payment_method: string (e.g., "Credit Card", "Cash", "Debit Card")
        - notes: string (any brief additional notes, or a summary of items if full itemization is too complex for primary fields)
        - location: string (store address or city, if available)
        - raw_text: string (the full raw text extracted from the receipt by OCR, if you can provide it)

        Example JSON:
        {{
          "vendor": "ExampleMart",
          "date": "2024-03-15",
          "amount": 123.45,
          "category": "Groceries",
          "tags": ["apples", "milk", "bread"],
          "payment_method": "Visa ****1234",
          "notes": "Weekly grocery run.",
          "location": "123 Main St, Anytown",
          "raw_text": "..."
        }}

        Ensure all string values are properly escaped within the JSON.
        The receipt image is provided. Extract the data now.
        '''

        payload = {
            "model": self.model_name,
            "prompt": prompt,
            "images": [base64_image_string],
            "format": "json",
            "stream": False,
            "options": { # Options to try and make output more deterministic / less creative
                "temperature": 0.0,
                # "top_k": 1, # Consider if needed
                # "top_p": 0.01 # Consider if needed
            }
        }

        receipt_info = None
        needs_manual_review = False
        extraction_confidence = 0.85 # Default placeholder confidence

        try:
            print(f"OllamaVisionLLM: Sending request to {self.api_url} for model {self.model_name}...")
            response = requests.post(self.api_url, json=payload, timeout=60) # 60-second timeout
            response.raise_for_status()  # Raise an exception for HTTP errors (4xx or 5xx)

            api_response_dict = response.json()
            extracted_json_str = api_response_dict.get('response', '{}')

            print(f"OllamaVisionLLM: Raw response string: '{extracted_json_str[:200]}...'") # Log snippet

            if not extracted_json_str.strip(): # Handle empty response string
                print("❌ OllamaVisionLLM: Received empty response string from model.")
                needs_manual_review = True
                extraction_confidence = 0.30 # Low confidence for empty response
                parsed_data_dict = {}
            else:
                try:
                    parsed_data_dict = json.loads(extracted_json_str)
                    if not isinstance(parsed_data_dict, dict): # Ensure it's a dict
                        print(f"❌ OllamaVisionLLM: Parsed JSON is not a dictionary. Response: {extracted_json_str}")
                        needs_manual_review = True; parsed_data_dict = {}
                        extraction_confidence = 0.40
                except json.JSONDecodeError as je:
                    print(f"❌ OllamaVisionLLM: Failed to parse JSON from model response: {je}")
                    print(f"   Full response string was: {extracted_json_str}")
                    needs_manual_review = True; parsed_data_dict = {}
                    extraction_confidence = 0.20 # Very low confidence for unparsable JSON

            # Map to ReceiptData, handling potential missing keys gracefully
            receipt_info = ReceiptData(
                vendor=parsed_data_dict.get('vendor'),
                date=parsed_data_dict.get('date'), # Further validation/parsing can be added here or in Pydantic model
                amount=parsed_data_dict.get('amount'),
                category=parsed_data_dict.get('category', "Uncategorized"),
                tags=parsed_data_dict.get('tags', []),
                payment_method=parsed_data_dict.get('payment_method'),
                notes=parsed_data_dict.get('notes'),
                location=parsed_data_dict.get('location'),
                source_file=str(image_path.resolve()),
                confidence_score=extraction_confidence, # Placeholder
                raw_text=parsed_data_dict.get('raw_text', extracted_json_str if needs_manual_review else None), # Store original string if parsing failed
                needs_review=needs_manual_review
            )

            # Additional check for essential fields to flag for review
            if not receipt_info.vendor or not receipt_info.date or receipt_info.amount is None:
                print("OllamaVisionLLM: Essential fields (vendor, date, or amount) missing. Flagging for review.")
                receipt_info.needs_review = True
                if receipt_info.confidence_score == extraction_confidence: # If not already lowered by parsing error
                    receipt_info.confidence_score = 0.60 # Lower confidence if key fields are missing

            print(f"OllamaVisionLLM: Data extraction successful for {image_path.name} (Needs Review: {receipt_info.needs_review})")

        except requests.exceptions.RequestException as e:
            print(f"❌ OllamaVisionLLM: API request failed: {e}")
            return None # Network or HTTP error
        except Exception as e: # Catch any other unexpected errors during processing
            print(f"❌ OllamaVisionLLM: An unexpected error occurred during extraction: {e}")
            # Create a minimal ReceiptData object if possible, flagged for review
            return ReceiptData(
                source_file=str(image_path.resolve()),
                notes=f"Extraction failed with error: {e}",
                needs_review=True,
                confidence_score=0.10
            )

        return receipt_info

if __name__ == '__main__': # ... (if __name__ block remains unchanged) ...
    print("Testing ReceiptData model and MockVisionLLM...")
    temp_test_dir = pathlib.Path("./temp_mock_llm_test")
    temp_test_dir.mkdir(exist_ok=True)
    dummy_receipt_file = temp_test_dir / "example_receipt.jpg"
    try:
        dummy_receipt_file.write_text("This is a dummy receipt image file for testing.")
        print(f"\nCreated dummy file: {dummy_receipt_file.resolve()}")

        mock_llm_instance = MockVisionLLM()
        print("\nAttempting to extract data using MockVisionLLM:")

        for i in range(5):
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

    # Example for OllamaVisionLLMConnector (requires Ollama running with a model like llava)
    # print("\n--- Testing OllamaVisionLLMConnector (requires Ollama server) ---")
    # ollama_connector = OllamaVisionLLMConnector() # Uses default http://localhost:11434 and llava:latest
    # Create a dummy image file (e.g., a real jpg or png receipt image)
    # test_image_path = pathlib.Path("./my_test_receipt.jpg") # Replace with a real image path
    # if test_image_path.exists():
    #     extracted_ollama_data = ollama_connector.extract_data(test_image_path)
    #     if extracted_ollama_data:
    #         print("\nData extracted by Ollama:")
    #         print(extracted_ollama_data.model_dump_json(indent=2))
    #     else:
    #         print("\nOllamaVisionLLMConnector failed to extract data.")
    # else:
    #     print(f"\nTest image for Ollama not found at {test_image_path}, skipping Ollama test.")
