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
    This will install Streamlit, Pandas, OpenpyXL, and Pydantic.

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
