import pandas as pd
import requests
from io import BytesIO
import os
import threading
import time
import logging
from datetime import datetime
from config import Config
from modules.printer_search.svcp import enrich_row_with_svcp

logger = logging.getLogger(__name__)

URL_STORAGE_FILE = "workbook_url.txt"

df_all_sheets = None
last_update_time = None
data_load_lock = threading.Lock()


def get_saved_url():
    try:
        if os.path.exists(URL_STORAGE_FILE):
            with open(URL_STORAGE_FILE, "r") as f:
                return f.read().strip()
    except Exception as e:
        logger.error(f"Error reading saved URL: {e}")
    return Config.WORKBOOK_URL


def save_url(url):
    try:
        with open(URL_STORAGE_FILE, "w") as f:
            f.write(url.strip())
        return True
    except Exception as e:
        logger.error(f"Error saving URL: {e}")
        return False


def load_excel_from_url():
    global last_update_time
    try:
        base_url = get_saved_url()
        if not base_url.endswith("/download"):
            url = base_url + "/download"
        else:
            url = base_url

        logger.info(f"Downloading Excel from: {url}")
        response = requests.get(url, stream=True, timeout=30)
        response.raise_for_status()

        excel_file = BytesIO(response.content)
        new_data = pd.read_excel(excel_file, sheet_name=None)
        last_update_time = datetime.now()
        logger.info(f"Excel loaded. Sheets: {list(new_data.keys())}")
        return new_data
    except Exception as e:
        logger.error(f"Error loading Excel: {e}")
        return None


def search_all_sheets(search_term):
    with data_load_lock:
        if df_all_sheets is None or not df_all_sheets:
            return {"error": "Data not loaded."}

        all_results = []
        for sheet_name, df in df_all_sheets.items():
            results = df[df.apply(
                lambda row: row.astype(str).str.contains(search_term, case=False, na=False).any(),
                axis=1
            )]
            if not results.empty:
                results_cleaned = results.fillna("")
                results_cleaned["Sheet Name"] = sheet_name
                all_results.append(results_cleaned)

        if not all_results:
            return {"error": "No results found."}

        results_df = pd.concat(all_results, ignore_index=True)
        results_df = results_df.map(str).replace("nan", "")
        records = results_df.to_dict(orient="records")
        return [enrich_row_with_svcp(r) for r in records]


def auto_reload_data():
    while True:
        time.sleep(Config.DATA_REFRESH_INTERVAL)
        try:
            with data_load_lock:
                global df_all_sheets
                new_data = load_excel_from_url()
                if new_data is not None:
                    df_all_sheets = new_data
        except Exception as e:
            logger.error(f"Auto-reload error: {e}")


def init():
    global df_all_sheets
    df_all_sheets = load_excel_from_url()
    thread = threading.Thread(target=auto_reload_data, daemon=True)
    thread.start()
