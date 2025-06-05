import os
import uuid
import pathlib
import shutil # Added for shutil.copy2

# Directory where uploaded receipts will be stored.
# It's calculated relative to this file's location (app/ingest.py),
# going up two levels to the project root, then into the 'receipts' folder.
RECEIPTS_DIR = pathlib.Path(__file__).parent.parent / "receipts"

# Set of allowed file extensions (case-insensitive).
ALLOWED_EXTENSIONS = {".jpg", ".jpeg", ".png", ".pdf"}

def save_uploaded_file(uploaded_file):
    """
    Saves an uploaded file to the RECEIPTS_DIR with a unique filename.

    Args:
        uploaded_file: An object representing the uploaded file.
                       It must have a 'name' attribute (string) and a
                       'read()' method that returns the file content as bytes.

    Returns:
        pathlib.Path: The path to the saved file if successful.
        None: If the file type is not allowed or if an error occurs during saving.
    """
    # Ensure the receipts directory exists.
    # parents=True creates any necessary parent directories.
    # exist_ok=True means it won't raise an error if the directory already exists.
    RECEIPTS_DIR.mkdir(parents=True, exist_ok=True)

    original_filename = uploaded_file.name
    # Extract the file extension and convert to lowercase for consistent checking.
    file_extension = pathlib.Path(original_filename).suffix.lower()

    # Validate the file extension.
    if file_extension not in ALLOWED_EXTENSIONS:
        print(f"Unsupported file type: {file_extension}. Allowed types are: {ALLOWED_EXTENSIONS}")
        return None

    # Generate a unique filename using UUID version 4 to avoid collisions.
    # The original file extension is preserved.
    unique_filename = f"{uuid.uuid4()}{file_extension}"
    save_path = RECEIPTS_DIR / unique_filename

    try:
        # Read the content (bytes) from the uploaded file object.
        file_content = uploaded_file.read()

        # Write the file content to the designated save path in binary mode ('wb').
        with open(save_path, "wb") as f:
            f.write(file_content)
        print(f"Successfully saved file: {original_filename} as {unique_filename} to {save_path}")
        return save_path
    except Exception as e:
        # Catch any other exceptions during file reading or writing.
        print(f"Error saving file {original_filename} (as {unique_filename}): {e}")
        return None

def scan_folder_for_receipts(source_folder_path_str):
    """
    Scans a source folder for receipt files and copies valid ones to RECEIPTS_DIR
    with unique filenames.

    Args:
        source_folder_path_str (str or pathlib.Path): The path to the folder
                                                      to scan for receipts.

    Returns:
        list[pathlib.Path]: A list of paths to the files that were successfully
                             copied to RECEIPTS_DIR. Returns an empty list if
                             the source folder is invalid or no valid files are found.
    """
    source_folder = pathlib.Path(source_folder_path_str)
    copied_files = []

    # Validate if the source_folder exists and is a directory.
    if not source_folder.is_dir():
        print(f"Error: Source folder '{source_folder}' not found or is not a directory.")
        return copied_files

    # Ensure the target receipts directory exists.
    RECEIPTS_DIR.mkdir(parents=True, exist_ok=True)

    print(f"Scanning folder: {source_folder.resolve()}")
    for item in source_folder.iterdir():
        # Check if the item is a file.
        if item.is_file():
            # Extract file extension and convert to lowercase for consistent checking.
            file_extension = item.suffix.lower()

            # Check if the file extension is in the set of allowed extensions.
            if file_extension in ALLOWED_EXTENSIONS:
                # Generate a unique filename to prevent overwriting and naming conflicts.
                unique_filename = f"{uuid.uuid4()}{file_extension}"
                destination_path = RECEIPTS_DIR / unique_filename

                try:
                    # Copy the file, preserving metadata like timestamps.
                    shutil.copy2(item, destination_path)
                    copied_files.append(destination_path)
                    print(f"Copied '{item.name}' to '{destination_path}'")
                except Exception as e:
                    # Handle potential errors during file copying.
                    print(f"Error copying file {item.name}: {e}")

    return copied_files
