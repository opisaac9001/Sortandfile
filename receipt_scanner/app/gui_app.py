import streamlit as st

st.set_page_config(
    page_title="Receipt Scanner", page_icon="🧾", layout="wide", initial_sidebar_state="expanded"
)

from .ingest import save_uploaded_file, scan_folder_for_receipts, RECEIPTS_DIR, ALLOWED_EXTENSIONS
from .vision_llm import MockVisionLLM, ReceiptData
from . import db
from . import export
import pathlib
import datetime
import json
import math

ITEMS_PER_PAGE = 10

def main(): # ... (main function remains unchanged) ...
    st.title("🧾 Receipt Scanner & Management")
    state_defaults = {
        'search_results': [], 'current_page': 0, 'selected_receipt_id': None,
        'active_page': "Ingest Receipts", 'custom_category_input_active': False,
        'download_file_path': None, 'download_file_name': None, 'download_mime_type': None,
        'backup_download_ready': False, 'backup_file_path_to_download': None,
        'tag_to_rename': None, 'tag_to_delete': None,
        'new_tag_name_input_rename': "",
        'total_pages': 0, 'current_filters': {}, 'search_active': False
    }
    for key, default_value in state_defaults.items():
        if key not in st.session_state: st.session_state[key] = default_value
    with st.spinner("⏳ Initializing database..."): db.initialize_database()
    llm_connector = MockVisionLLM()
    if not RECEIPTS_DIR.exists(): RECEIPTS_DIR.mkdir(parents=True, exist_ok=True)
    st.sidebar.header("Actions")
    page_options = ["Ingest Receipts", "View & Search Receipts", "🏷️ Manage Tags", "⚙️ Settings"]
    def on_page_change():
        st.session_state.update(selected_receipt_id=None, active_page=st.session_state.sidebar_nav, custom_category_input_active=False, download_file_path=None, backup_download_ready=False, backup_file_path_to_download=None,tag_to_rename=None, tag_to_delete=None, new_tag_name_input_rename="")
    st.sidebar.radio("Choose Action", page_options, key="sidebar_nav", on_change=on_page_change)
    if st.session_state.selected_receipt_id is not None: display_receipt_detail_page(st.session_state.selected_receipt_id)
    elif st.session_state.active_page == "Ingest Receipts": ingestion_section(llm_connector)
    elif st.session_state.active_page == "View & Search Receipts": view_search_page()
    elif st.session_state.active_page == "🏷️ Manage Tags": manage_tags_page()
    elif st.session_state.active_page == "⚙️ Settings": settings_page()

def ingestion_section(llm_connector: MockVisionLLM): # ... (ingestion_section remains unchanged) ...
    st.header("Ingest Receipts")
    tab1, tab2 = st.tabs(["⬆️ Upload Files", "📁 Scan Folder"])
    with tab1:
        st.subheader("Upload Receipt Files")
        allowed_types = [ext.lstrip('.') for ext in ALLOWED_EXTENSIONS]
        uploaded_files = st.file_uploader("Choose receipt files", type=allowed_types, accept_multiple_files=True, help=f"Supported file types: {', '.join(allowed_types).upper()}. Each file will be processed individually.")
        if uploaded_files:
            for uploaded_file in uploaded_files:
                with st.expander(f"Processing: {uploaded_file.name}", expanded=True):
                    if not (hasattr(uploaded_file, 'name') and hasattr(uploaded_file, 'read')):
                        st.error("❌ Invalid uploaded file object.", icon="🚫"); continue
                    with st.spinner("💾 Saving file..."): saved_path = save_uploaded_file(uploaded_file)
                    if saved_path:
                        st.success(f"✅ File saved: {saved_path.name}")
                        with st.spinner("🧠 Extracting data with LLM..."): extracted_data = llm_connector.extract_data(saved_path)
                        if extracted_data:
                            st.success(f"🎉 LLM Data extracted.")
                            st.markdown(f"&nbsp;&nbsp;&nbsp;&nbsp;**Vendor:** {extracted_data.vendor if extracted_data.vendor else 'N/A'}")
                            st.markdown(f"&nbsp;&nbsp;&nbsp;&nbsp;**Amount:** {extracted_data.amount if extracted_data.amount is not None else 'N/A'}")
                            status_icon = "🚩" if extracted_data.needs_review else "✔️"
                            st.markdown(f"&nbsp;&nbsp;&nbsp;&nbsp;**Review Needed:** {status_icon} {'Yes' if extracted_data.needs_review else 'No'}")
                            with st.spinner("💾 Saving to database..."): inserted_id = db.save_receipt_data(extracted_data)
                            if inserted_id: st.success(f"✔️ Saved to Database with ID: {inserted_id}")
                            else: st.error(f"❌ Failed to save to Database.")
                        else: st.error(f"❌ LLM data extraction failed for {saved_path.name}. Ensure the image is clear and a valid receipt.", icon="🧠")
                    else: st.error(f"❌ Could not save '{uploaded_file.name}'. File type not supported or write error. Please use JPG, PNG, or PDF files.", icon="🚫")
    with tab2:
        st.subheader("Scan Folder for Receipts")
        folder_path_str = st.text_input("Enter folder path:", key="folder_path_input_scan", placeholder="/path/to/your/receipts_folder", help="Enter the full path to a folder on the server that contains receipt files to scan.")
        if st.button("🔍 Scan Folder", key="scan_folder_button_action"):
            if folder_path_str:
                source_folder = pathlib.Path(folder_path_str.strip())
                if not source_folder.is_dir(): st.error(f"❌ Invalid folder path: '{source_folder}'.")
                else:
                    with st.spinner(f"📁 Scanning folder: {source_folder}..."): copied_files = scan_folder_for_receipts(str(source_folder))
                    total_scanned_files = len(copied_files)
                    if not copied_files: st.info("ℹ️ No new valid files found in the folder, or files are of unsupported types.", icon="🤷"); return
                    st.info(f"ℹ️ Found {total_scanned_files} new file(s) in the folder. Starting processing...", icon="📂")
                    processed_successfully_scan = 0; failed_processing_scan = 0
                    for receipt_file_path in copied_files:
                        with st.expander(f"Processing scanned file: {receipt_file_path.name}", expanded=True):
                            file_processed_ok = True
                            st.success(f"✅ Copied to storage: {receipt_file_path.name}")
                            with st.spinner("🧠 Extracting data with LLM..."): extracted_data = llm_connector.extract_data(receipt_file_path)
                            if extracted_data:
                                st.success(f"🎉 LLM Data extracted.")
                                st.markdown(f"&nbsp;&nbsp;&nbsp;&nbsp;**Vendor:** {extracted_data.vendor if extracted_data.vendor else 'N/A'}")
                                st.markdown(f"&nbsp;&nbsp;&nbsp;&nbsp;**Amount:** {extracted_data.amount if extracted_data.amount is not None else 'N/A'}")
                                status_icon = "🚩" if extracted_data.needs_review else "✔️"
                                st.markdown(f"&nbsp;&nbsp;&nbsp;&nbsp;**Review Needed:** {status_icon} {'Yes' if extracted_data.needs_review else 'No'}")
                                with st.spinner("💾 Saving to database..."): inserted_id = db.save_receipt_data(extracted_data)
                                if inserted_id: st.success(f"✔️ Saved to Database with ID: {inserted_id}")
                                else: st.error(f"❌ Failed to save to Database."); file_processed_ok = False
                            else: st.error(f"❌ LLM data extraction failed for {receipt_file_path.name}. Ensure the image is clear and a valid receipt.", icon="🧠"); file_processed_ok = False
                            if file_processed_ok: processed_successfully_scan += 1
                            else: failed_processing_scan += 1
                    st.markdown("---"); st.subheader("Folder Scan Summary")
                    if processed_successfully_scan > 0: st.success(f"✅ Folder scan complete. Processed {processed_successfully_scan} out of {total_scanned_files} files successfully.", icon="🎉")
                    if failed_processing_scan > 0: st.warning(f"⚠️ {failed_processing_scan} out of {total_scanned_files} files encountered errors during processing. Please check details in the expanders above.", icon="❗")
            else: st.warning("⚠️ Please enter a folder path to scan.")

def view_search_page(): # ... (view_search_page remains unchanged) ...
    st.header("View & Search Receipts")
    _fetch_paginated_search_results()
    with st.expander("🔍 Search Filters", expanded=True):
        search_term = st.text_input("Search Term (vendor, notes, OCR text, tags)", value=st.session_state.get('current_filters', {}).get('search_term', ""), key="vs_search_term", help="Searches across Vendor, Notes, Raw OCR Text, and the text content of Tags.")
        row1_col1, row1_col2 = st.columns(2)
        vendor = row1_col1.text_input("Vendor", value=st.session_state.get('current_filters', {}).get('vendor', ""), key="vs_vendor")
        category = row1_col2.text_input("Category", value=st.session_state.get('current_filters', {}).get('category', ""), key="vs_category")
        row2_col1, row2_col2 = st.columns(2)
        tags_str = row2_col1.text_input("Tags (comma-separated, any match)", value=",".join(st.session_state.get('current_filters', {}).get('tags_include_any', []) or []), key="vs_tags", help="Enter one or more tags, comma-separated. Matches receipts containing ANY of the listed tags.")
        review_options_map = {"All": None, "Yes (Needs Review)": True, "No (Reviewed)": False}
        review_options_keys = list(review_options_map.keys())
        current_review_filter_val = st.session_state.get('current_filters', {}).get('needs_review_filter', None)
        current_review_idx = 0
        if current_review_filter_val is True: current_review_idx = 1
        elif current_review_filter_val is False: current_review_idx = 2
        selected_review_key = row2_col2.selectbox("Needs Review Status:", options=review_options_keys, index=current_review_idx, key="review_filter_select", help="Filter receipts based on their 'Needs Review' status.")
        row3_col1, row3_col2 = st.columns(2)
        amount_min_val = row3_col1.number_input("Min Amount:", value=st.session_state.get('current_filters', {}).get('amount_min', None), placeholder="e.g., 10.00", step=0.01, format="%.2f", key="amount_min_filter", help="Filter by minimum receipt amount.")
        amount_max_val = row3_col2.number_input("Max Amount:", value=st.session_state.get('current_filters', {}).get('amount_max', None), placeholder="e.g., 100.00", step=0.01, format="%.2f", key="amount_max_filter", help="Filter by maximum receipt amount.")
        date_col1, date_col2 = st.columns(2)
        current_date_from = st.session_state.get('current_filters', {}).get('date_from'); current_date_to = st.session_state.get('current_filters', {}).get('date_to')
        date_from_dt = datetime.datetime.fromisoformat(current_date_from) if current_date_from else None; date_to_dt = datetime.datetime.fromisoformat(current_date_to) if current_date_to else None
        date_from = date_col1.date_input("Date From", value=date_from_dt, key="vs_date_from"); date_to = date_col2.date_input("Date To", value=date_to_dt, key="vs_date_to")
        if st.button("Search Receipts 🔎", key="vs_search_button"):
            st.session_state.current_filters = {'search_term': search_term or None, 'vendor': vendor or None, 'category': category or None, 'tags_include_any': [t.strip() for t in tags_str.split(',') if t.strip()] if tags_str else None, 'needs_review_filter': review_options_map[selected_review_key], 'amount_min': amount_min_val, 'amount_max': amount_max_val, 'date_from': date_from.isoformat() if date_from else None, 'date_to': date_to.isoformat() if date_to else None}
            st.session_state.update(current_page=0, selected_receipt_id=None, download_file_path=None, search_active=True); st.rerun()
    st.subheader("Search Results")
    if st.session_state.get('search_active', False) and st.session_state.get('current_filters'):
        active_filter_parts = []
        for key, value in st.session_state.current_filters.items():
            if value is not None and value != '' and value != []:
                readable_key = ' '.join(word.capitalize() for word in key.replace('_filter', '').replace('_val', '').replace('_str', '').replace('_include_any', ' (any)').split('_'))
                val_display = ", ".join(value) if isinstance(value, list) else str(value)
                if val_display: active_filter_parts.append(f"{readable_key}: '{val_display}'")
        if active_filter_parts: st.info(f"ℹ️ Filters applied: {'; '.join(active_filter_parts)}", icon="🔍")
        elif st.session_state.get('search_active'): st.info("ℹ️ Showing all results. Use filters to narrow down your search.", icon="🧾")
    if not st.session_state.get('search_results', []):
        if st.session_state.get('search_active'): st.warning("⚠️ No receipts found matching your current filter criteria. Try adjusting your filters.", icon="🤷")
        else: st.info("ℹ️ No results to display. Please use the filters above and click 'Search Receipts', or receipts will load if available.", icon="🧾")
    else: # ... (results display and export logic remains unchanged) ...
        cols_header = st.columns([0.5, 1.5, 2.5, 1, 1.5, 1, 1]); headers = ["ID", "Date", "Vendor", "Amount", "Category", "Review?", "View"]
        for col, header_text in zip(cols_header, headers): col.markdown(f"**{header_text}**")
        st.markdown("---")
        for r in st.session_state.search_results:
            cols = st.columns([0.5, 1.5, 2.5, 1, 1.5, 1, 1])
            cols[0].text(r.get('id', 'N/A')); cols[1].text(r.get('date', 'N/A')); cols[2].text(r.get('vendor', 'N/A'))
            cols[3].text(f"${r.get('amount', 0.0):.2f}" if r.get('amount') is not None else "N/A"); cols[4].text(r.get('category', 'N/A'))
            review_status_text = "🚩 Yes" if r.get('needs_review', False) else "✔️ No"
            cols[5].markdown(review_status_text, help="Indicates if the receipt is flagged for manual review.")
            if cols[6].button("👁️ View", key=f"view_btn_{r.get('id')}", use_container_width=True): st.session_state.selected_receipt_id = r.get('id'); st.rerun()
            st.markdown("---")
        if st.session_state.total_pages > 0:
            st.write(f"Page {st.session_state.current_page + 1} of {st.session_state.total_pages}")
            pg_col1, pg_col2 = st.columns(2)
            if pg_col1.button("⬅️ Previous Page", key="prev_page_btn", disabled=(st.session_state.current_page == 0), help="Go to the previous page of results."): st.session_state.current_page -= 1; st.session_state.selected_receipt_id = None; st.rerun()
            if pg_col2.button("Next Page ➡️", key="next_page_btn", disabled=(st.session_state.current_page >= st.session_state.total_pages - 1), help="Go to the next page of results."): st.session_state.current_page += 1; st.session_state.selected_receipt_id = None; st.rerun()
        st.markdown("---"); st.subheader("Export Search Results")
        if st.session_state.search_results:
            col_exp1, col_exp2 = st.columns(2); ts = datetime.datetime.now().strftime("%Y%m%d_%H%M%S"); fname = f"receipt_export_{ts}"
            if col_exp1.button("Export to Excel 📗", key="export_excel"):
                with st.spinner("⏳ Generating Excel file..."): excel_p = export.export_to_excel(st.session_state.search_results, f"{fname}.xlsx")
                if excel_p: st.session_state.update(download_file_path=excel_p, download_file_name=pathlib.Path(excel_p).name, download_mime_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")
                else: st.error("❌ Failed to export data to Excel."); st.session_state.download_file_path = None
            if col_exp2.button("Export to CSV 📄", key="export_csv"):
                with st.spinner("⏳ Generating CSV file..."): csv_p = export.export_to_csv(st.session_state.search_results, f"{fname}.csv")
                if csv_p: st.session_state.update(download_file_path=csv_p, download_file_name=pathlib.Path(csv_p).name, download_mime_type="text/csv")
                else: st.error("❌ Failed to export data to CSV."); st.session_state.download_file_path = None
            if st.session_state.get('download_file_path'):
                try:
                    with open(st.session_state.download_file_path, "rb") as fp: st.download_button(f"📥 Download {st.session_state.download_file_name}", fp, st.session_state.download_file_name, st.session_state.download_mime_type, key="dl_btn")
                except FileNotFoundError: st.error("❌ Exported file not found. Please try exporting again."); st.session_state.download_file_path = None
                except Exception as e: st.error(f"❌ An error occurred while preparing download: {e}"); st.session_state.download_file_path = None

def display_receipt_detail_page(receipt_id: int): # ... (function to be refined in next step) ...
    st.header(f"🧾 Receipt Details - ID: {receipt_id}") # Added icon
    if st.button("⬅️ Back to Search Results", key=f"back_btn_detail_{receipt_id}", help="Return to the list of receipts."):
        st.session_state.update(selected_receipt_id=None, custom_category_input_active=False, download_file_path=None); st.rerun()

    receipt_data = db.get_receipt_by_id(receipt_id)
    if not receipt_data: st.error("❌ Receipt not found or could not be loaded."); return

    st.subheader(f"Vendor: {receipt_data.get('vendor', 'N/A')}")

    key_info_col1, key_info_col2, key_info_col3 = st.columns(3)
    amount = receipt_data.get('amount')
    key_info_col1.metric("Amount", f"${amount:.2f}" if amount is not None else "N/A")
    key_info_col2.metric("Date", receipt_data.get('date', 'N/A'))

    current_status = receipt_data.get('needs_review', False)
    status_text = "Needs Review 🚩" if current_status else "Reviewed ✔️"
    status_help_text = "Indicates if this receipt requires manual verification." if current_status else "This receipt has been marked as reviewed."
    if current_status: key_info_col3.warning(status_text, icon="🚩")
    else: key_info_col3.success(status_text, icon="✔️")
    key_info_col3.caption(status_help_text) # Add help text under status for clarity

    st.markdown("---")

    toggle_button_label = "Mark as Reviewed ✔️" if current_status else "Flag for Review 🚩"
    if st.button(toggle_button_label, key=f"toggle_review_btn_{receipt_id}", use_container_width=True, help="Toggle the 'Needs Review' status for this receipt."):
        new_status = not current_status
        if db.update_receipt_review_status(receipt_id, new_status):
            st.success(f"✔️ Review status updated to: {'Needs Review 🚩' if new_status else 'Reviewed ✔️'}.")
            st.rerun()
        else: st.error("❌ Failed to update review status.")

    st.markdown("---")
    st.subheader("📋 Details")
    detail_col1, detail_col2 = st.columns(2)
    with detail_col1:
        st.markdown(f"**Category:** {receipt_data.get('category', 'N/A')}")
        tags_list = receipt_data.get('tags', [])
        if not isinstance(tags_list, list): tags_list = []
        st.markdown(f"**Tags:** {', '.join(tags_list) if tags_list else 'None'}")
    with detail_col2:
        st.markdown(f"**Payment Method:** {receipt_data.get('payment_method', 'N/A')}")
        st.markdown(f"**Location:** {receipt_data.get('location', 'N/A')}")

    st.markdown("---")
    more_details_col1, more_details_col2 = st.columns(2)
    with more_details_col1:
        confidence = receipt_data.get('confidence_score')
        st.markdown(f"**LLM Confidence:** {f'{confidence:.0%}' if confidence is not None else 'N/A'}", help="Confidence score from the data extraction model (0-100%).")
    with more_details_col2:
        st.caption(f"Source File: {receipt_data.get('source_file', 'N/A')}")
        st.caption(f"Database ID: {receipt_data.get('id')} | Created At: {receipt_data.get('created_at')}")

    st.markdown("---")

    col_notes_ocr, col_image = st.columns([1,1])
    with col_notes_ocr:
        with st.expander("📝 Notes & Raw OCR Data", expanded=True):
            st.text_area("Notes:", value=receipt_data.get('notes', 'No notes provided.'), height=100, disabled=True, key=f"notes_display_{receipt_id}")
            st.text_area("Raw Text (OCR):", value=receipt_data.get('raw_text', 'No OCR data available.'), height=200, disabled=True, key=f"raw_text_display_{receipt_id}")
    with col_image:
        st.subheader("🖼️ Receipt Image")
        image_path_str = receipt_data.get('source_file')
        if image_path_str:
            image_path = pathlib.Path(image_path_str)
            if RECEIPTS_DIR.resolve() in image_path.resolve().parents:
                if image_path.exists() and image_path.is_file():
                    try: st.image(str(image_path), caption=f"Scanned Receipt: {image_path.name}", use_column_width=True)
                    except Exception as e: st.error(f"❌ Could not display image: {e}")
                else: st.warning(f"⚠️ Receipt image file not found at: {image_path_str}")
            else: st.error(f"❌ Access to image path is restricted."); st.caption(f"Note: Image must be within: {RECEIPTS_DIR.resolve()}")
        else: st.info("ℹ️ No image path associated with this receipt record.")

    st.markdown("---")
    with st.expander("✏️ Edit Category & Tags", expanded=False):
        all_known_categories = db.get_distinct_categories(); all_known_tags = db.get_distinct_tags()
        st.subheader("Edit Category")
        current_category = receipt_data.get('category', '')
        category_options = [""] + all_known_categories + ["Add new category..."]
        try: current_category_index = category_options.index(current_category)
        except ValueError:
            if current_category: category_options.insert(1, current_category); current_category_index = 1
            else: current_category_index = 0
        new_category_selection = st.selectbox("Category:", options=category_options, index=current_category_index, key=f"category_select_{receipt_id}")

        final_category_to_save = new_category_selection
        if new_category_selection == "Add new category...":
            st.session_state.custom_category_input_active = True
            custom_category_name = st.text_input("Enter new category name:", key=f"custom_category_{receipt_id}")
            if custom_category_name.strip(): final_category_to_save = custom_category_name.strip()
            else: final_category_to_save = ""
            st.caption("Enter your new category above and click 'Update Category'.") # Guidance text
        elif new_category_selection == "": final_category_to_save = ""
        else: st.session_state.custom_category_input_active = False

        if st.button("Update Category", key=f"update_category_btn_{receipt_id}", help="Save changes to the category for this receipt."):
            if new_category_selection == "Add new category..." and not final_category_to_save: st.warning("⚠️ New category field was empty.")
            if db.update_receipt_category(receipt_id, final_category_to_save): st.success("✔️ Category updated!"); st.session_state.custom_category_input_active = False; st.rerun()
            else: st.error("❌ Failed to update category.")

        st.markdown("---"); st.subheader("Edit Tags")
        current_tags = receipt_data.get('tags', []);
        if not isinstance(current_tags, list): current_tags = []
        options_for_multiselect = list(set(all_known_tags + current_tags))
        selected_tags = st.multiselect("Tags:", options=sorted(options_for_multiselect), default=current_tags, key=f"tags_multiselect_{receipt_id}", help="Select from existing tags, or add new ones in the text box below.")
        new_tag_input = st.text_input("Add new tag(s) (comma-separated):", key=f"new_tag_input_{receipt_id}", help="New tags entered here (comma-separated) will be added to this receipt's tag list.")
        st.caption("Selected tags from the list and any newly typed tags will be saved.") # Guidance text

        if st.button("Update Tags", key=f"update_tags_btn_{receipt_id}", help="Save changes to the tags for this receipt."):
            final_tags_to_save = set(selected_tags)
            if new_tag_input.strip():
                for t in [t.strip() for t in new_tag_input.split(',') if t.strip()]: final_tags_to_save.add(t)
            if db.update_receipt_tags(receipt_id, sorted(list(final_tags_to_save))): st.success("✔️ Tags updated!"); st.rerun()
            else: st.error("❌ Failed to update tags.")

def settings_page(): # ... (no changes) ...
    st.header("⚙️ Settings & Maintenance")
    st.markdown("---")
    st.subheader("Database Backup")
    if 'backup_download_ready' not in st.session_state: st.session_state.backup_download_ready = False
    if 'backup_file_path_to_download' not in st.session_state: st.session_state.backup_file_path_to_download = None
    if st.button("Create Database Backup", key="backup_db_btn"):
        with st.spinner("⏳ Creating database backup..."): backup_filepath_str = db.backup_database()
        if backup_filepath_str:
            st.success(f"✔️ Database successfully backed up to server path: {backup_filepath_str}")
            st.session_state.backup_download_ready = True
            st.session_state.backup_file_path_to_download = backup_filepath_str
        else: st.error("❌ Database backup failed."); st.session_state.backup_download_ready = False; st.session_state.backup_file_path_to_download = None
    if st.session_state.backup_download_ready and st.session_state.backup_file_path_to_download:
        backup_path = pathlib.Path(st.session_state.backup_file_path_to_download)
        try:
            with open(backup_path, "rb") as fp:
                st.download_button(label=f"📥 Download Backup ({backup_path.name})", data=fp, file_name=backup_path.name, mime="application/x-sqlite3", key=f"download_backup_{backup_path.name}")
        except FileNotFoundError: st.error(f"❌ Backup file not found at expected path: {backup_path}. Please try creating backup again.")
        except Exception as e: st.error(f"❌ An error occurred while preparing backup for download: {e}")

def manage_tags_page(): # ... (no changes) ...
    st.header("🏷️ Manage Tags")
    st.markdown("---")
    if 'tag_to_rename' not in st.session_state: st.session_state.tag_to_rename = None
    if 'tag_to_delete' not in st.session_state: st.session_state.tag_to_delete = None
    if 'new_tag_name_input_rename' not in st.session_state: st.session_state.new_tag_name_input_rename = ""
    distinct_tags = db.get_distinct_tags()
    if not distinct_tags and not st.session_state.tag_to_rename and not st.session_state.tag_to_delete:
        st.info("ℹ️ No tags found in the database yet. Tags are added when editing receipts.")
        return
    st.subheader("Existing Tags")
    if distinct_tags:
        st.info(f"Found {len(distinct_tags)} unique tags.")
        header_cols = st.columns([3,1,1,1]); header_cols[0].markdown("**Tag Name**"); header_cols[1].markdown("**Usage Count**"); header_cols[2].markdown("**Rename**"); header_cols[3].markdown("**Delete**"); st.markdown("---")
        for tag in distinct_tags:
            count = db.count_receipts_for_tag(tag); cols = st.columns([3,1,1,1]); cols[0].text(tag); cols[1].text(str(count))
            if cols[2].button("✏️ Rename", key=f"rename_tag_btn_{tag}", use_container_width=True): st.session_state.tag_to_rename = tag; st.session_state.new_tag_name_input_rename = tag; st.session_state.tag_to_delete = None; st.rerun()
            if cols[3].button("🗑️ Delete", key=f"delete_tag_btn_{tag}", use_container_width=True): st.session_state.tag_to_delete = tag; st.session_state.tag_to_rename = None; st.rerun()
            st.markdown("---")
    elif not st.session_state.tag_to_rename and not st.session_state.tag_to_delete : st.info("ℹ️ No tags found in the database yet.")
    if st.session_state.get('tag_to_rename'):
        st.markdown("---"); tag_being_renamed = st.session_state.tag_to_rename; st.subheader(f"Rename Tag: '{tag_being_renamed}'")
        st.session_state.new_tag_name_input_rename = st.text_input("New tag name:", value=st.session_state.new_tag_name_input_rename, key="text_input_for_rename_tag_globally" )
        rename_cols = st.columns(2)
        if rename_cols[0].button("✅ Confirm Rename", key="confirm_rename_tag_btn"):
            new_name = st.session_state.new_tag_name_input_rename.strip()
            if new_name and new_name != tag_being_renamed:
                with st.spinner(f"Renaming '{tag_being_renamed}' to '{new_name}'..."): count = db.rename_tag_globally(tag_being_renamed, new_name)
                st.success(f"✔️ Tag '{tag_being_renamed}' successfully renamed to '{new_name}' for {count} receipt(s)."); st.session_state.tag_to_rename = None; st.session_state.new_tag_name_input_rename = ""; st.rerun()
            elif not new_name: st.error("❌ New tag name cannot be empty.")
            else: st.info("ℹ️ The new tag name is the same as the old one. No changes made."); st.session_state.tag_to_rename = None; st.session_state.new_tag_name_input_rename = ""; st.rerun()
        if rename_cols[1].button("❌ Cancel Rename", key="cancel_rename_tag_btn"): st.session_state.tag_to_rename = None; st.session_state.new_tag_name_input_rename = ""; st.rerun()
    if st.session_state.get('tag_to_delete'):
        st.markdown("---"); tag_being_deleted = st.session_state.tag_to_delete; st.subheader(f"Delete Tag: '{tag_being_deleted}'")
        st.warning(f"⚠️ Are you sure you want to delete the tag '{tag_being_deleted}' from ALL receipts? This action cannot be undone.")
        delete_cols = st.columns(2)
        if delete_cols[0].button("🗑️ Confirm Delete", key="confirm_delete_tag_btn"):
            with st.spinner(f"Deleting tag '{tag_being_deleted}'..."): count = db.delete_tag_globally(tag_being_deleted)
            st.success(f"✔️ Tag '{tag_being_deleted}' deleted from {count} receipt(s)."); st.session_state.tag_to_delete = None; st.rerun()
        if delete_cols[1].button("❌ Cancel Delete", key="cancel_delete_tag_btn"): st.session_state.tag_to_delete = None; st.rerun()

if __name__ == "__main__":
    main()
