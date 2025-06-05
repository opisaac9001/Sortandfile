# Receipt Scanner Project

This project is designed to ingest, parse, and manage scanned receipts using a vision-capable LLM.

## Features (Planned)
- Image upload and folder scanning
- LLM-based data extraction (vendor, date, amount, etc.)
- Tax categorization and custom tagging
- Searchable receipt archive
- Excel/CSV export

## Folder Structure
- `app/`: Python source code
- `receipts/`: Stored receipt images
- `parsed/`: Structured JSON output from LLM (optional)
- `exports/`: Exported Excel/CSV files
- `database/`: SQLite database (`receipts.sqlite`)
- `tests/`: Unit and integration tests
