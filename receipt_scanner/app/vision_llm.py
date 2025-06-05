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

        prompt = '''SYSTEM MESSAGE / INSTRUCTION
You are a financial document parser.
Your task is to analyze receipt images and return structured data in a JSON format for tax documentation purposes.
You must extract all relevant information cleanly and accurately. If information is unclear or missing, return null for the field and provide a confidence score for the overall result.

USER MESSAGE / IMAGE + PROMPT TEXT

Please analyze the receipt image provided and extract the following fields as structured JSON.

🎯 Required Output Format (JSON):

{{
  "vendor": "string",                   // The store or business name (e.g., 'Costco')
  "date": "YYYY-MM-DD",                // The transaction date (ISO format)
  "total_amount": 0.00,                // The total amount paid (numeric)
  "currency": "USD",                   // Currency symbol or ISO code. If not USD, try to include it in notes or as a tag like 'currency:XXX'.
  "category": "string",                // Suggested tax category (e.g., 'Office Supplies', 'Meals')
  "tags": ["tag1", "tag2"],            // Suggested tags (e.g., ['Gas', 'Client Travel'])
  "payment_method": "string",          // If visible (e.g., 'Visa', 'Cash'), otherwise null
  "location": "string",                // City/state if visible or inferred, otherwise null
  "notes": "string",                   // Any visible memo, client/job note, or hand-written annotation. Include currency here if non-USD and not in a tag.
  "raw_text": "string",                // Full OCR text if possible, otherwise null
  "confidence_score": 0.00             // Confidence score from 0.0 to 1.0 for the overall extraction
}}

🧠 Instructions for Each Field:
    • vendor: Extract from store logo, name, or header. Clean it to be consistent (no address unless embedded).
    • date: Extract only the transaction date (not print time or batch number). Return in YYYY-MM-DD format. If year is missing, try to infer from context or use current year.
    • total_amount: Return the total amount charged to the customer, not subtotal or tip unless labeled as the final total. Must be a numeric value.
    • currency: If shown, extract symbol or use ‘USD’ if unknown. Accept $, €, etc. If not USD, please try to note it in the 'notes' field or add a tag like 'currency:EUR'.
    • category: Suggest a tax-deductible category based on the receipt. Example categories: Office Supplies, Meals & Entertainment, Gas, Travel, Lodging, Software, Equipment, Other.
    • tags: Generate up to 3-5 relevant, short keyword-style tags to help the user sort expenses. These may include purpose, item type, vendor class, etc.
    • payment_method: If shown (card type, cash, etc.), extract it. Otherwise return null.
    • location: If city, store address, or region is visible, extract it. If not visible, return null.
    • notes: Include any handwritten or printed memo fields, such as purpose, client name, project, or hand-written tax notes. If currency is other than USD and not captured elsewhere, include it here.
    • raw_text: Provide the full raw text extracted from the receipt by OCR, if possible. If not, return null.
    • confidence_score: Assign an overall confidence score from 0.0 to 1.0 based on clarity, legibility, and completeness of data extracted for the key fields (vendor, date, total_amount).

🔁 Special Handling:
    • If the receipt contains handwriting, do your best to interpret and extract it. If unsure, return the field as null and note it in confidence.
    • If there are multiple totals, choose the most prominent or labeled final total.
    • Ignore non-transactional text like footer ads or surveys.
    • Do not hallucinate data — return null for fields not confidently detected.
    • Ensure the entire output is ONLY the JSON object, with no surrounding text or markdown.

Example Output (for guidance, actual content will vary):

{{
  "vendor": "Shell",
  "date": "2025-06-03",
  "total_amount": 45.90,
  "currency": "USD",
  "category": "Travel",
  "tags": ["Gas", "Client Visit", "Vehicle", "currency:USD"],
  "payment_method": "Visa",
  "location": "Santa Monica, CA",
  "notes": "Fuel for client site trip.",
  "raw_text": "Shell Station #123 ...",
  "confidence_score": 0.91
}}
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

            # Map to ReceiptData fields, aligning with the new prompt's JSON structure
            vendor = parsed_data_dict.get('vendor')
            receipt_date_str = parsed_data_dict.get('date')
            amount_val = parsed_data_dict.get('total_amount') # Changed from 'amount'
            category = parsed_data_dict.get('category', "Uncategorized") # Pydantic default
            tags = parsed_data_dict.get('tags', []) # Pydantic default
            payment_method = parsed_data_dict.get('payment_method')
            notes = parsed_data_dict.get('notes')
            location = parsed_data_dict.get('location')
            raw_text_from_llm = parsed_data_dict.get('raw_text')

            # Handle confidence score from LLM if provided and valid
            confidence_from_llm = parsed_data_dict.get('confidence_score')
            final_confidence_score = None
            if isinstance(confidence_from_llm, (float, int)) and 0.0 <= confidence_from_llm <= 1.0:
                final_confidence_score = float(confidence_from_llm)
            else:
                if confidence_from_llm is not None: # Log if score is present but invalid
                    print(f"OllamaVisionLLM: Warning - LLM provided invalid confidence score: {confidence_from_llm}. Will calculate based on fields.")
                # If not provided or invalid, it will be determined based on field presence / parsing status

            # Initial needs_review status from parsing step (e.g. if JSON was malformed)
            current_needs_review = needs_manual_review

            # Validate amount type
            parsed_amount = None
            if amount_val is not None:
                try:
                    parsed_amount = float(amount_val)
                except (ValueError, TypeError):
                    print(f"OllamaVisionLLM: Warning - Could not parse 'total_amount' ({amount_val}) as float. Flagging for review.")
                    current_needs_review = True
                    notes = f"{notes or ''} [System Note: Original amount '{amount_val}' could not be parsed]".strip()


            # Check for essential fields to determine needs_review and adjust confidence
            if not all([vendor, receipt_date_str, parsed_amount is not None]):
                print("OllamaVisionLLM: Essential fields (vendor, date, or total_amount) missing or invalid. Flagging for review.")
                current_needs_review = True
                # If confidence wasn't already lowered by parsing issues, set a lower one
                if final_confidence_score is None or final_confidence_score > 0.6:
                     final_confidence_score = 0.60

            if final_confidence_score is None: # If still None after checks (e.g. LLM didn't provide one, and key fields were okay)
                final_confidence_score = 0.85 # Default if everything seems okay but no score from LLM

            # Further reduce confidence if needs_review is true for other reasons
            if current_needs_review and (final_confidence_score > 0.7): # Cap confidence if review needed
                 final_confidence_score = 0.7


            receipt_info = ReceiptData(
                vendor=vendor,
                date=receipt_date_str,
                amount=parsed_amount,
                category=category,
                tags=tags if isinstance(tags, list) else [],
                payment_method=payment_method,
                notes=notes,
                location=location,
                source_file=str(image_path.resolve()),
                confidence_score=final_confidence_score,
                raw_text=raw_text_from_llm if raw_text_from_llm else (extracted_json_str if needs_manual_review else None),
                needs_review=current_needs_review
            )
            print(f"OllamaVisionLLM: Data extraction processed for {image_path.name} (Needs Review: {receipt_info.needs_review}, Confidence: {receipt_info.confidence_score})")

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
