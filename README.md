## Deployment (Self-Hosted)

This section describes how to deploy and run the Receipt Scanner application on your own server or local machine.

1.  **Clone the Repository**:
    ```bash
    git clone https://github.com/yourusername/receipt_scanner_project.git # Replace with actual repository URL
    cd receipt_scanner_project
    ```

2.  **Create and Activate a Virtual Environment** (Recommended):
    ```bash
    python3 -m venv .venv
    source .venv/bin/activate  # On Windows: .venv\Scripts\activate
    ```

3.  **Install Dependencies**:
    ```bash
    pip install -r requirements.txt
    ```
    This will install Streamlit, Pandas, OpenpyXL, Pydantic, and Requests.

4.  **Run the Application**:
    ```bash
    streamlit run receipt_scanner/app/gui_app.py --server.port 8501 --server.address 0.0.0.0
    ```
    -   `--server.port 8501`: Specifies the port the application will run on. 8501 is the default for Streamlit, but you can change it if needed.
    -   `--server.address 0.0.0.0`: Makes the Streamlit app accessible from other machines on your local network. If you only want to access it on the machine it's running on, you can use `localhost` or `127.0.0.1` (or omit this flag for default behavior).

5.  **Accessing the Application**:
    *   Open your web browser and navigate to `http://<your_server_ip>:8501`.
    *   If running locally, this will typically be `http://localhost:8501`.
    *   If accessing from another device on your network, replace `<your_server_ip>` with the local IP address of the machine running the application (e.g., `http://192.168.1.100:8501`).
    *   **Security Note**: For security, it's highly recommended to access this application through a VPN, Tailnet (e.g., Tailscale), or similar private networking solution if your server might be exposed to the internet or an untrusted network.

6.  **Persistent Data Directories**:
    *   The application stores data in subdirectories within the `receipt_scanner` module folder (relative to where you run the `streamlit run` command, assuming it's from the project root `receipt_scanner_project/`).
    *   Ensure these directories are writable by the application and are backed up regularly:
        *   `receipt_scanner/database/`: Contains the main SQLite database (`receipts.sqlite`).
        *   `receipt_scanner/receipts/`: Stores the uploaded/scanned receipt image files.
        *   `receipt_scanner/exports/`: Default location for exported Excel/CSV files (created by the app).
        *   `receipt_scanner/backups/`: Default location for database backups created via the Settings page.

## Using with Ollama (Live LLM)

This section explains how to configure the application to use a local Ollama instance with a vision-capable model (e.g., LLaVA) for receipt data extraction.

**1. Prerequisites**:
*   Ensure you have Ollama installed and running on your system. Visit [https://ollama.com](https://ollama.com) for installation instructions.
*   Pull a vision-capable model compatible with Ollama. For example, to pull the LLaVA model:
    ```bash
    ollama pull llava:latest
    ```
    You can also use specific versions like `llava:13b-v1.6` or other compatible models like `bakllava`.

**2. Application Configuration**:
*   Open the file `receipt_scanner_project/receipt_scanner/app/gui_app.py` in a text editor.
*   Locate the `# --- Ollama Configuration ---` section near the top of the file (if it's not there, you can add it).
*   To enable the Ollama connector, set:
    ```python
    USE_OLLAMA_LLM = True
    ```
*   Update `OLLAMA_MODEL_NAME` to the exact name of the model you have pulled in Ollama (e.g., `"llava:latest"`, `"llava:13b-v1.6"`).
    ```python
    OLLAMA_MODEL_NAME = "llava:latest" # Or your chosen model
    ```
*   If your Ollama server is not running on the default `http://localhost:11434`, update `OLLAMA_BASE_URL` accordingly:
    ```python
    OLLAMA_BASE_URL = "http://your_ollama_server_ip:11434"
    ```

**3. Running the Application**:
*   Once configured, run the Streamlit application as described in the "Deployment (Self-Hosted)" section.
*   The application will now attempt to connect to your Ollama server for receipt processing.
*   Check the terminal output where you launched Streamlit for connection messages or errors from the `OllamaVisionLLMConnector`. The sidebar in the application will also indicate if it's attempting to use Ollama or has fallen back to the Mock LLM.

**4. Example Prompt for `OllamaVisionLLMConnector`**:
The application uses a detailed prompt to instruct the Ollama model. Here's a template of the prompt used in `receipt_scanner/app/vision_llm.py`:
```python
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
```

**5. Important Notes**:
*   LLM performance and extraction accuracy heavily depend on the specific vision model used (e.g., `llava:7b` vs. `llava:34b`) and the clarity of the receipt images.
*   The prompt within `OllamaVisionLLMConnector` in `receipt_scanner/app/vision_llm.py` can be further tuned for your specific model and desired output detail.
*   Ensure the Ollama server has sufficient resources (RAM, and VRAM if GPU-accelerated) to run the selected vision model effectively. Larger models require more resources.
*   The application requests JSON output directly from Ollama (`format: "json"`). If the model used doesn't strictly adhere to this or adds conversational text, parsing might fail. The connector includes basic error handling for this.
