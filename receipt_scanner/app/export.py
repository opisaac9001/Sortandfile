# export.py
# This module handles exporting receipt data to various file formats.

import pandas as pd
import pathlib
from typing import List, Dict, Optional

# Define the directory where exported files will be saved.
# Assumes export.py is in receipt_scanner/app/
EXPORTS_DIR = pathlib.Path(__file__).resolve().parent.parent / "exports"

# Define a preferred order of columns for exported files.
# 'needs_review' is a placeholder for a potential future column.
PREFERRED_EXPORT_COLUMNS = [
    'id', 'date', 'vendor', 'amount', 'category', 'tags',
    'payment_method', 'notes', 'location', 'source_file',
    'confidence_score', 'raw_text', 'needs_review', 'created_at'
]

def _prepare_dataframe(receipt_list: List[Dict]) -> Optional[pd.DataFrame]:
    """
    Converts a list of receipt dictionaries into a pandas DataFrame,
    preparing it for export. Handles tag conversion and column ordering.

    Args:
        receipt_list: A list of dictionaries, where each dictionary represents a receipt.

    Returns:
        A pandas DataFrame ready for export, or None if the input list is empty.
    """
    if not receipt_list:
        print("Warning: Receipt list is empty. No DataFrame to prepare.")
        return None

    try:
        df = pd.DataFrame(receipt_list)
    except Exception as e:
        print(f"Error creating DataFrame from receipt list: {e}")
        return None

    # Convert 'tags' column: if it contains lists, join them into a comma-separated string.
    if 'tags' in df.columns:
        df['tags'] = df['tags'].apply(
            lambda tags_data: ', '.join(tags_data) if isinstance(tags_data, list)
            else (tags_data if isinstance(tags_data, str) else "")
            # Ensure original strings are kept, otherwise default to empty string.
        )

    # Reorder columns based on PREFERRED_EXPORT_COLUMNS.
    # Only include preferred columns that actually exist in the DataFrame.
    existing_cols_in_preference_order = [col for col in PREFERRED_EXPORT_COLUMNS if col in df.columns]

    # Include any other columns from the DataFrame that are not in the preferred list, placing them at the end.
    other_columns = [col for col in df.columns if col not in existing_cols_in_preference_order]

    final_column_order = existing_cols_in_preference_order + other_columns

    df = df.reindex(columns=final_column_order)

    return df

def export_to_excel(receipt_list: List[Dict], filename: str) -> Optional[str]:
    """
    Exports a list of receipt data to an Excel file.

    Args:
        receipt_list: A list of receipt dictionaries.
        filename: The desired name for the Excel file (without .xlsx extension).

    Returns:
        The absolute path (as a string) to the saved Excel file on success,
        or None if an error occurs or if there's no data.
    """
    try:
        EXPORTS_DIR.mkdir(parents=True, exist_ok=True)
    except Exception as e:
        print(f"Error creating exports directory {EXPORTS_DIR}: {e}")
        return None

    df = _prepare_dataframe(receipt_list)
    if df is None or df.empty:
        # _prepare_dataframe already prints a warning if list is empty.
        # Adding a specific message for export context.
        print("Info: DataFrame is empty, skipping Excel export.")
        return None

    if not filename.endswith(".xlsx"):
        filename += ".xlsx"

    filepath = EXPORTS_DIR / filename

    try:
        df.to_excel(filepath, index=False, engine='openpyxl')
        print(f"Data successfully exported to Excel: {filepath.resolve()}")
        return str(filepath.resolve())
    except Exception as e:
        print(f"Error exporting data to Excel file {filepath}: {e}")
        return None

def export_to_csv(receipt_list: List[Dict], filename: str) -> Optional[str]:
    """
    Exports a list of receipt data to a CSV file.

    Args:
        receipt_list: A list of receipt dictionaries.
        filename: The desired name for the CSV file (without .csv extension).

    Returns:
        The absolute path (as a string) to the saved CSV file on success,
        or None if an error occurs or if there's no data.
    """
    try:
        EXPORTS_DIR.mkdir(parents=True, exist_ok=True)
    except Exception as e:
        print(f"Error creating exports directory {EXPORTS_DIR}: {e}")
        return None

    df = _prepare_dataframe(receipt_list)
    if df is None or df.empty:
        print("Info: DataFrame is empty, skipping CSV export.")
        return None

    if not filename.endswith(".csv"):
        filename += ".csv"

    filepath = EXPORTS_DIR / filename

    try:
        df.to_csv(filepath, index=False)
        print(f"Data successfully exported to CSV: {filepath.resolve()}")
        return str(filepath.resolve())
    except Exception as e:
        print(f"Error exporting data to CSV file {filepath}: {e}")
        return None

# Note: The if __name__ == '__main__': block for example usage is excluded as per instructions.
