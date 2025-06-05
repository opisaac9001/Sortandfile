# Placeholder for db.py
# This module will handle all database interactions for the receipt scanner.

import sqlite3
import pathlib
import json
from typing import Optional, List, Dict, Set
import shutil
import datetime

from .vision_llm import ReceiptData

DATABASE_DIR = pathlib.Path(__file__).resolve().parent.parent / "database"
DATABASE_PATH = DATABASE_DIR / "receipts.sqlite"
BACKUPS_DIR = DATABASE_PATH.parent.parent / "backups"


def initialize_database():
    conn = None
    try:
        DATABASE_DIR.mkdir(parents=True, exist_ok=True)
        conn = sqlite3.connect(DATABASE_PATH)
        cursor = conn.cursor()
        create_table_sql = """
        CREATE TABLE IF NOT EXISTS receipts (
            id INTEGER PRIMARY KEY AUTOINCREMENT, vendor TEXT, date TEXT, amount REAL, category TEXT,
            tags TEXT, payment_method TEXT, notes TEXT, location TEXT, source_file TEXT NOT NULL,
            confidence_score REAL, raw_text TEXT, created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            needs_review INTEGER DEFAULT 0
        );"""
        cursor.execute(create_table_sql)
        conn.commit()
        cursor.execute("PRAGMA table_info(receipts);")
        columns = [info[1] for info in cursor.fetchall()]
        if 'needs_review' not in columns:
            print("Attempting to add 'needs_review' column.")
            cursor.execute("ALTER TABLE receipts ADD COLUMN needs_review INTEGER DEFAULT 0;")
            conn.commit()
            print("'needs_review' column added successfully.")
        print(f"Database initialized successfully at {DATABASE_PATH}")
    except sqlite3.Error as e: print(f"SQLite error during database initialization: {e}")
    except Exception as e: print(f"An unexpected error during database initialization: {e}")
    finally:
        if conn: conn.close()

def save_receipt_data(receipt: ReceiptData) -> Optional[int]:
    db_conn = None
    try:
        db_conn = sqlite3.connect(DATABASE_PATH)
        cursor = db_conn.cursor()
        tags_json = json.dumps(sorted(list(set(receipt.tags))))
        sql = """INSERT INTO receipts (
                    vendor, date, amount, category, tags, payment_method, notes, location,
                    source_file, confidence_score, raw_text, needs_review
                 ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)"""
        values = (
            receipt.vendor, receipt.date, receipt.amount, receipt.category, tags_json,
            receipt.payment_method, receipt.notes, receipt.location, receipt.source_file,
            receipt.confidence_score, receipt.raw_text, int(receipt.needs_review)
        )
        cursor.execute(sql, values)
        db_conn.commit()
        inserted_id = cursor.lastrowid
        if inserted_id is not None: print(f"Receipt data for '{receipt.source_file}' saved with ID: {inserted_id} (Needs Review: {receipt.needs_review}).")
        return inserted_id
    except sqlite3.Error as e: print(f"SQLite error saving receipt '{receipt.source_file}': {e}"); return None
    except json.JSONDecodeError as e: print(f"JSON error for tags for '{receipt.source_file}': {e}"); return None
    except Exception as e: print(f"Unexpected error saving receipt '{receipt.source_file}': {e}"); return None
    finally:
        if db_conn: db_conn.close()

def _db_row_to_dict(cursor: sqlite3.Cursor, row: sqlite3.Row) -> Optional[Dict]:
    if row is None: return None
    d = {col[0]: row[idx] for idx, col in enumerate(cursor.description)}
    if 'tags' in d and d['tags'] is not None:
        try: d['tags'] = json.loads(d['tags'])
        except json.JSONDecodeError: print(f"Warning: Could not decode tags for ID {d.get('id')}: {d['tags']}"); d['tags'] = []
    elif 'tags' in d: d['tags'] = []
    if 'needs_review' in d and d['needs_review'] is not None: d['needs_review'] = bool(d['needs_review'])
    else: d['needs_review'] = False
    return d

def get_receipt_by_id(receipt_id: int) -> Optional[Dict]:
    conn = None
    try:
        conn = sqlite3.connect(DATABASE_PATH)
        cursor = conn.cursor()
        cursor.execute("SELECT * FROM receipts WHERE id = ?", (receipt_id,))
        return _db_row_to_dict(cursor, cursor.fetchone())
    except sqlite3.Error as e: print(f"DB error fetching ID {receipt_id}: {e}"); return None
    finally:
        if conn: conn.close()

def get_all_receipts(limit: int = 20, offset: int = 0) -> List[Dict]:
    conn = None; receipts_list = []
    try:
        conn = sqlite3.connect(DATABASE_PATH)
        cursor = conn.cursor()
        cursor.execute("SELECT * FROM receipts ORDER BY created_at DESC, id DESC LIMIT ? OFFSET ?", (limit, offset))
        for row in cursor.fetchall():
            if dict_row := _db_row_to_dict(cursor, row): receipts_list.append(dict_row)
        return receipts_list
    except sqlite3.Error as e: print(f"DB error fetching all receipts: {e}"); return []
    finally:
        if conn: conn.close()

def search_receipts(
    search_term: Optional[str] = None, vendor: Optional[str] = None, category: Optional[str] = None,
    date_from: Optional[str] = None, date_to: Optional[str] = None,
    tags_include_any: Optional[List[str]] = None, needs_review_filter: Optional[bool] = None,
    amount_min: Optional[float] = None, amount_max: Optional[float] = None,
    limit: int = 20, offset: int = 0
) -> List[Dict]:
    conn = None; results_list = []; where_clauses = []; params = []
    base_query = "SELECT * FROM receipts"
    if search_term:
        st_like = f"%{search_term}%"
        where_clauses.append("(vendor LIKE ? OR notes LIKE ? OR raw_text LIKE ? OR tags LIKE ?)")
        params.extend([st_like, st_like, st_like, st_like])
    if vendor: where_clauses.append("vendor LIKE ?"); params.append(f"%{vendor}%")
    if category: where_clauses.append("category LIKE ?"); params.append(f"%{category}%")
    if date_from: where_clauses.append("date >= ?"); params.append(date_from)
    if date_to: where_clauses.append("date <= ?"); params.append(date_to)
    if tags_include_any and isinstance(tags_include_any, list):
        tag_clauses_group = [f"tags LIKE ?" for tag in tags_include_any if tag and tag.strip()]
        if tag_clauses_group:
            where_clauses.append("(" + " OR ".join(tag_clauses_group) + ")")
            params.extend([f'%"{tag.strip()}"%' for tag in tags_include_any if tag and tag.strip()])
    if needs_review_filter is not None: where_clauses.append("needs_review = ?"); params.append(int(needs_review_filter))
    if amount_min is not None: where_clauses.append("amount >= ?"); params.append(amount_min)
    if amount_max is not None: where_clauses.append("amount <= ?"); params.append(amount_max)
    full_query = base_query
    if where_clauses: full_query += " WHERE " + " AND ".join(where_clauses)
    full_query += " ORDER BY created_at DESC, id DESC LIMIT ? OFFSET ?"
    params.extend([limit, offset])
    try:
        conn = sqlite3.connect(DATABASE_PATH)
        cursor = conn.cursor()
        cursor.execute(full_query, params)
        for row in cursor.fetchall():
            if dict_row := _db_row_to_dict(cursor, row): results_list.append(dict_row)
        return results_list
    except sqlite3.Error as e: print(f"DB error during search: {e}. Query: {full_query}, Params: {params}"); return []
    finally:
        if conn: conn.close()

def update_receipt_tags(receipt_id: int, new_tags: List[str]) -> bool:
    conn = None
    try:
        conn = sqlite3.connect(DATABASE_PATH)
        cursor = conn.cursor()
        tags_json = json.dumps(sorted(list(set(new_tags))))
        cursor.execute("UPDATE receipts SET tags = ? WHERE id = ?", (tags_json, receipt_id))
        conn.commit()
        if cursor.rowcount > 0: print(f"Tags updated for receipt ID {receipt_id}."); return True
        print(f"No update for tags on ID {receipt_id} (no change or not found)."); return False
    except Exception as e: print(f"Error updating tags for ID {receipt_id}: {e}"); return False
    finally:
        if conn: conn.close()

def update_receipt_category(receipt_id: int, new_category: str) -> bool:
    conn = None
    try:
        conn = sqlite3.connect(DATABASE_PATH)
        cursor = conn.cursor()
        cursor.execute("UPDATE receipts SET category = ? WHERE id = ?", (new_category, receipt_id))
        conn.commit()
        if cursor.rowcount > 0: print(f"Category updated for receipt ID {receipt_id}."); return True
        print(f"No update for category on ID {receipt_id} (no change or not found)."); return False
    except Exception as e: print(f"Error updating category for ID {receipt_id}: {e}"); return False
    finally:
        if conn: conn.close()

def get_distinct_categories() -> List[str]:
    conn = None
    try:
        conn = sqlite3.connect(DATABASE_PATH)
        cursor = conn.cursor()
        cursor.execute("SELECT DISTINCT category FROM receipts WHERE category IS NOT NULL AND category != '' ORDER BY category ASC")
        return [row[0] for row in cursor.fetchall()]
    except sqlite3.Error as e: print(f"DB error fetching distinct categories: {e}"); return []
    finally:
        if conn: conn.close()

def get_distinct_tags() -> List[str]:
    conn = None; distinct_tags_set: Set[str] = set()
    try:
        conn = sqlite3.connect(DATABASE_PATH)
        cursor = conn.cursor()
        cursor.execute("SELECT tags FROM receipts WHERE tags IS NOT NULL AND tags != '[]' AND tags != ''")
        for row in cursor.fetchall():
            if not row[0]: continue
            try:
                tags_list = json.loads(row[0])
                if isinstance(tags_list, list):
                    for tag in tags_list:
                        if isinstance(tag, str) and tag.strip(): distinct_tags_set.add(tag.strip())
            except json.JSONDecodeError: print(f"Warning: Could not decode JSON tags: {row[0]}"); continue
        return sorted(list(distinct_tags_set))
    except sqlite3.Error as e: print(f"DB error fetching distinct tags: {e}"); return []
    finally:
        if conn: conn.close()

def update_receipt_review_status(receipt_id: int, status: bool) -> bool:
    conn = None
    try:
        conn = sqlite3.connect(DATABASE_PATH)
        cursor = conn.cursor()
        cursor.execute("UPDATE receipts SET needs_review = ? WHERE id = ?", (int(status), receipt_id))
        conn.commit()
        if cursor.rowcount > 0: print(f"Review status updated for ID {receipt_id} to {status}."); return True
        print(f"No update for review status on ID {receipt_id} (no change or not found)."); return False
    except Exception as e: print(f"Error updating review status for ID {receipt_id}: {e}"); return False
    finally:
        if conn: conn.close()

def backup_database(backup_file_prefix: str = "receipt_scanner_backup") -> Optional[str]:
    if not DATABASE_PATH.exists(): print(f"Error: DB file not found at {DATABASE_PATH}."); return None
    try:
        BACKUPS_DIR.mkdir(parents=True, exist_ok=True)
        timestamp = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
        backup_filename = f"{backup_file_prefix}_{timestamp}.sqlite"
        backup_filepath = BACKUPS_DIR / backup_filename
        shutil.copy2(DATABASE_PATH, backup_filepath)
        abs_backup_filepath = str(backup_filepath.resolve())
        print(f"Database backed up to: {abs_backup_filepath}")
        return abs_backup_filepath
    except Exception as e: print(f"Error during database backup: {e}"); return None

def count_receipts_for_tag(tag_name: str) -> int:
    conn = None
    try:
        conn = sqlite3.connect(DATABASE_PATH)
        cursor = conn.cursor()
        search_pattern = f'%"{tag_name}"%'
        cursor.execute("SELECT COUNT(*) FROM receipts WHERE tags LIKE ?", (search_pattern,))
        count_result = cursor.fetchone()
        return count_result[0] if count_result else 0
    except sqlite3.Error as e: print(f"Database error counting tag '{tag_name}': {e}"); return 0
    except Exception as e: print(f"Unexpected error counting tag '{tag_name}': {e}"); return 0
    finally:
        if conn: conn.close()

def rename_tag_globally(old_tag_name: str, new_tag_name: str) -> int:
    if not old_tag_name.strip() or not new_tag_name.strip() or old_tag_name == new_tag_name:
        print("Info: Old/new tag names same or empty. No rename."); return 0
    conn = None; updated_count = 0
    try:
        conn = sqlite3.connect(DATABASE_PATH); conn.isolation_level = None; cursor = conn.cursor(); cursor.execute('BEGIN')
        search_pattern = f'%"{old_tag_name}"%'
        cursor.execute("SELECT id, tags FROM receipts WHERE tags LIKE ?", (search_pattern,))
        for receipt_id, tags_json_string in cursor.fetchall():
            try:
                current_tags = json.loads(tags_json_string)
                if isinstance(current_tags, list) and old_tag_name in current_tags:
                    current_tags.remove(old_tag_name)
                    if new_tag_name not in current_tags: current_tags.append(new_tag_name)
                    new_tags_json = json.dumps(sorted(list(set(current_tags)))) # Ensure unique and sorted
                    update_cursor = conn.cursor()
                    update_cursor.execute("UPDATE receipts SET tags = ? WHERE id = ?", (new_tags_json, receipt_id))
                    if update_cursor.rowcount > 0: updated_count += 1
            except json.JSONDecodeError: print(f"Warning: JSON decode error for ID {receipt_id} during tag rename."); continue
        cursor.execute('COMMIT'); print(f"Tag '{old_tag_name}' renamed to '{new_tag_name}' for {updated_count} receipts.")
        return updated_count
    except Exception as e:
        if conn: conn.cursor().execute('ROLLBACK')
        print(f"Error renaming tag '{old_tag_name}' globally: {e}"); return 0
    finally:
        if conn: conn.close()

def delete_tag_globally(tag_name_to_delete: str) -> int:
    if not tag_name_to_delete.strip(): print("Info: Tag to delete is empty."); return 0
    conn = None; updated_count = 0
    try:
        conn = sqlite3.connect(DATABASE_PATH); conn.isolation_level = None; cursor = conn.cursor(); cursor.execute('BEGIN')
        search_pattern = f'%"{tag_name_to_delete}"%'
        cursor.execute("SELECT id, tags FROM receipts WHERE tags LIKE ?", (search_pattern,))
        for receipt_id, tags_json_string in cursor.fetchall():
            try:
                current_tags = json.loads(tags_json_string)
                if isinstance(current_tags, list) and tag_name_to_delete in current_tags:
                    current_tags.remove(tag_name_to_delete)
                    new_tags_json = json.dumps(sorted(list(set(current_tags)))) # Ensure unique and sorted
                    update_cursor = conn.cursor()
                    update_cursor.execute("UPDATE receipts SET tags = ? WHERE id = ?", (new_tags_json, receipt_id))
                    if update_cursor.rowcount > 0: updated_count += 1
            except json.JSONDecodeError: print(f"Warning: JSON decode error for ID {receipt_id} during tag delete."); continue
        cursor.execute('COMMIT'); print(f"Tag '{tag_name_to_delete}' deleted from {updated_count} receipts.")
        return updated_count
    except Exception as e:
        if conn: conn.cursor().execute('ROLLBACK')
        print(f"Error deleting tag '{tag_name_to_delete}' globally: {e}"); return 0
    finally:
        if conn: conn.close()

def count_search_results(
    search_term: Optional[str] = None, vendor: Optional[str] = None, category: Optional[str] = None,
    date_from: Optional[str] = None, date_to: Optional[str] = None,
    tags_include_any: Optional[List[str]] = None, needs_review_filter: Optional[bool] = None,
    amount_min: Optional[float] = None, amount_max: Optional[float] = None
) -> int:
    """Counts search results based on the same criteria as search_receipts."""
    where_clauses = []
    params = []

    if search_term:
        st_like = f"%{search_term}%"
        where_clauses.append("(vendor LIKE ? OR notes LIKE ? OR raw_text LIKE ? OR tags LIKE ?)")
        params.extend([st_like, st_like, st_like, st_like])
    if vendor: where_clauses.append("vendor LIKE ?"); params.append(f"%{vendor}%")
    if category: where_clauses.append("category LIKE ?"); params.append(f"%{category}%")
    if date_from: where_clauses.append("date >= ?"); params.append(date_from)
    if date_to: where_clauses.append("date <= ?"); params.append(date_to)
    if tags_include_any and isinstance(tags_include_any, list):
        tag_clauses_group = [f"tags LIKE ?" for tag in tags_include_any if tag and tag.strip()]
        if tag_clauses_group:
            where_clauses.append("(" + " OR ".join(tag_clauses_group) + ")")
            params.extend([f'%"{tag.strip()}"%' for tag in tags_include_any if tag and tag.strip()])
    if needs_review_filter is not None: where_clauses.append("needs_review = ?"); params.append(int(needs_review_filter))
    if amount_min is not None: where_clauses.append("amount >= ?"); params.append(amount_min)
    if amount_max is not None: where_clauses.append("amount <= ?"); params.append(amount_max)

    sql_query = "SELECT COUNT(*) FROM receipts"
    if where_clauses:
        sql_query += " WHERE " + " AND ".join(where_clauses)

    conn = None
    try:
        conn = sqlite3.connect(DATABASE_PATH)
        cursor = conn.cursor()
        cursor.execute(sql_query, params)
        count_result = cursor.fetchone()
        return count_result[0] if count_result else 0
    except sqlite3.Error as e:
        print(f"Database error in count_search_results: {e}. Query: {sql_query}, Params: {params}")
        return 0
    except Exception as e:
        print(f"Unexpected error in count_search_results: {e}")
        return 0
    finally:
        if conn:
            conn.close()
