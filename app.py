from flask import Flask, render_template, request, jsonify, send_from_directory, session
import pandas as pd
import requests
from io import BytesIO
import socket
import os
import json
import threading
import time
import logging
import traceback
from datetime import datetime
from dotenv import load_dotenv

load_dotenv()

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

app = Flask(__name__)
app.secret_key = os.getenv('FLASK_SECRET_KEY', 'dev-secret-key-do-not-use-in-production')

# Function to get the local IP address
def get_local_ip():
    try:
        # Connect to a remote address to determine the local IP
        s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        s.connect(("8.8.8.8", 80))
        ip = s.getsockname()[0]
        s.close()
        return ip
    except:
        return "127.0.0.1"  # Fallback to localhost

# Default URL from environment or fallback
DEFAULT_URL = os.getenv('WORKBOOK_URL', 'https://nextcloud.nwu.ac.za/index.php/s/4RdDP4qX3mMoXc7')
URL_STORAGE_FILE = "workbook_url.txt"

def get_saved_url():
    """Get the saved URL from file, or return default if file doesn't exist"""
    try:
        if os.path.exists(URL_STORAGE_FILE):
            with open(URL_STORAGE_FILE, 'r') as f:
                return f.read().strip()
    except Exception as e:
        logger.error(f"Error reading saved URL: {e}")
    return DEFAULT_URL

def save_url(url):
    """Save the URL to file"""
    try:
        with open(URL_STORAGE_FILE, 'w') as f:
            f.write(url.strip())
        return True
    except Exception as e:
        logger.error(f"Error saving URL: {e}")
        return False

# Global variables for data and last update time
df_all_sheets = None
last_update_time = None
data_load_lock = threading.Lock()

def load_excel_from_url():
    global last_update_time
    try:
        base_url = get_saved_url()

        if not base_url.endswith('/download'):
            url = base_url + '/download'
        else:
            url = base_url

        logger.info(f"Downloading Excel file from URL: {url}")
        response = requests.get(url, stream=True)
        response.raise_for_status()

        excel_file = BytesIO(response.content)
        df_all_sheets = pd.read_excel(excel_file, sheet_name=None)

        last_update_time = datetime.now()
        logger.info(f"Excel file loaded successfully from URL at {last_update_time}. Sheets: {list(df_all_sheets.keys())}")
        if df_all_sheets:
            first_sheet = list(df_all_sheets.keys())[0]
            logger.debug(f"First sheet preview:\n{df_all_sheets[first_sheet].head()}")

        return df_all_sheets
    except Exception as e:
        logger.error(f"Error loading Excel file from URL: {e}")
        logger.error(traceback.format_exc())
        return None

def auto_reload_data():
    """Background thread to automatically reload data every 60 seconds"""
    while True:
        time.sleep(60)
        try:
            with data_load_lock:
                global df_all_sheets
                logger.info("Auto-reloading data...")
                new_data = load_excel_from_url()
                if new_data is not None:
                    df_all_sheets = new_data
                    logger.info("Data auto-reload completed successfully")
                else:
                    logger.warning("Data auto-reload failed")
        except Exception as e:
            logger.error(f"Error in auto-reload thread: {e}")
            logger.error(traceback.format_exc())

# Load the Excel file at startup
df_all_sheets = load_excel_from_url()

# Start the auto-reload thread
auto_reload_thread = threading.Thread(target=auto_reload_data, daemon=True)
auto_reload_thread.start()

# Admin password from environment
ADMIN_PASSWORD = os.getenv('ADMIN_PASSWORD', 'print@NWU')

@app.route('/')
def index():
    search_term = request.args.get('q', '')
    return render_template('index.html', search_term=search_term)

# Route to serve favicon
@app.route('/favicon.ico')
def favicon():
    return send_from_directory(app.root_path, 'favicon.ico', mimetype='image/vnd.microsoft.icon')

@app.route('/search', methods=['POST'])
def search():
    search_term = request.form.get('search_term', '').strip()
    logger.info(f"Search term received: '{search_term}'")

    with data_load_lock:
        if df_all_sheets is None or not df_all_sheets:
            logger.error("Data not loaded or no sheets found.")
            return jsonify({"error": "Failed to load data from URL. Check if the Excel file is accessible."})

        try:
            all_results = []

            for sheet_name, df in df_all_sheets.items():
                logger.debug(f"Searching sheet: {sheet_name}, columns: {list(df.columns)}")
                results = df[df.apply(lambda row: row.astype(str).str.contains(search_term, case=False, na=False).any(), axis=1)]

                if not results.empty:
                    results_cleaned = results.fillna('')
                    results_cleaned['Sheet Name'] = sheet_name
                    all_results.append(results_cleaned)
                    logger.debug(f"Found {len(results)} results in sheet '{sheet_name}'")

            if all_results:
                results_df = pd.concat(all_results, ignore_index=True)
                logger.info(f"Total results found: {len(results_df)}")

                results_df_cleaned = results_df.map(str)
                results_df_cleaned = results_df_cleaned.replace('nan', '')

                results_dict = results_df_cleaned.to_dict(orient='records')
                logger.debug(f"Returning {len(results_dict)} records")

                return jsonify(results_dict)
            else:
                logger.info("No results found across all sheets.")
                return jsonify({"error": "No results found."})

        except Exception as e:
            logger.error(f"Error during search: {e}")
            logger.error(traceback.format_exc())
            return jsonify({"error": f"An error occurred during the search: {str(e)}"})

# Admin routes
@app.route('/admin/login', methods=['POST'])
def admin_login():
    password = request.form.get('password', '').strip()
    if password == ADMIN_PASSWORD:
        session['is_admin'] = True
        return jsonify({"success": True, "message": "Login successful"})
    else:
        return jsonify({"success": False, "message": "Invalid password"})

@app.route('/admin/logout', methods=['POST'])
def admin_logout():
    session.pop('is_admin', None)
    return jsonify({"success": True, "message": "Logout successful"})

@app.route('/admin/status')
def admin_status():
    return jsonify({"is_admin": session.get('is_admin', False)})

@app.route('/admin/get_url')
def admin_get_url():
    if not session.get('is_admin'):
        return jsonify({"error": "Unauthorized"}), 403
    return jsonify({"url": get_saved_url()})

@app.route('/admin/update_url', methods=['POST'])
def admin_update_url():
    if not session.get('is_admin'):
        return jsonify({"error": "Unauthorized"}), 403
    
    new_url = request.form.get('url', '').strip()
    if not new_url:
        return jsonify({"success": False, "message": "URL cannot be empty"})
    
    # Save the new URL
    if save_url(new_url):
        # Reload the data with the new URL
        with data_load_lock:
            global df_all_sheets
            df_all_sheets = load_excel_from_url()
        return jsonify({"success": True, "message": "URL updated successfully and data reloaded"})
    else:
        return jsonify({"success": False, "message": "Failed to save URL"})

@app.route('/admin/reload_data')
def admin_reload_data():
    if not session.get('is_admin'):
        return jsonify({"error": "Unauthorized"}), 403
    
    # Reload the data
    with data_load_lock:
        global df_all_sheets
        df_all_sheets = load_excel_from_url()
    
    if df_all_sheets is not None:
        return jsonify({"success": True, "message": "Data reloaded successfully"})
    else:
        return jsonify({"success": False, "message": "Failed to reload data"})

@app.route('/admin/get_sheets')
def admin_get_sheets():
    if not session.get('is_admin'):
        return jsonify({"error": "Unauthorized"}), 403
    
    with data_load_lock:
        if df_all_sheets is not None:
            sheets = list(df_all_sheets.keys())
            return jsonify({"sheets": sheets})
        else:
            return jsonify({"error": "No data loaded"})

@app.route('/admin/update_record', methods=['POST'])
def admin_update_record():
    if not session.get('is_admin'):
        return jsonify({"error": "Unauthorized"}), 403
    
    try:
        data = request.get_json()
        search_term = data.get('search_term', '').strip()
        sheet_name = data.get('sheet_name', '').strip()
        updated_data = data.get('updated_data', {})
        
        if not search_term or not sheet_name:
            return jsonify({"success": False, "error": "Search term and sheet name are required"})
        
        with data_load_lock:
            if df_all_sheets is None or sheet_name not in df_all_sheets:
                return jsonify({"success": False, "error": f"Sheet '{sheet_name}' not found"})
            
            # Find the record to update
            df = df_all_sheets[sheet_name]
            mask = df.apply(lambda row: row.astype(str).str.contains(search_term, case=False, na=False).any(), axis=1)
            
            if not mask.any():
                return jsonify({"success": False, "error": "Record not found"})
            
            # Update the record
            for idx in df[mask].index:
                for column, value in updated_data.items():
                    if column in df.columns:
                        df.at[idx, column] = value
            
            return jsonify({"success": True, "message": "Record updated successfully"})
            
    except Exception as e:
        logger.error(f"Error updating record: {e}")
        logger.error(traceback.format_exc())
        return jsonify({"success": False, "error": f"Error updating record: {str(e)}"})

@app.route('/admin/add_record', methods=['POST'])
def admin_add_record():
    if not session.get('is_admin'):
        return jsonify({"error": "Unauthorized"}), 403
    
    try:
        data = request.get_json()
        sheet_name = data.get('sheet_name', '').strip()
        new_data = data.get('new_data', {})
        
        if not sheet_name:
            return jsonify({"success": False, "error": "Sheet name is required"})
        
        with data_load_lock:
            if df_all_sheets is None or sheet_name not in df_all_sheets:
                return jsonify({"success": False, "error": f"Sheet '{sheet_name}' not found"})
            
            # Create new row
            df = df_all_sheets[sheet_name]
            new_row = {}
            
            # Set values for all columns
            for column in df.columns:
                new_row[column] = new_data.get(column, '')
            
            # Add the new row
            df.loc[len(df)] = new_row
            
            return jsonify({"success": True, "message": "Record added successfully"})
            
    except Exception as e:
        logger.error(f"Error adding record: {e}")
        logger.error(traceback.format_exc())
        return jsonify({"success": False, "error": f"Error adding record: {str(e)}"})

@app.route('/last_update')
def last_update():
    """Get the last data update time"""
    return jsonify({
        "last_update": last_update_time.isoformat() if last_update_time else None,
        "timestamp": last_update_time.strftime("%Y-%m-%d %H:%M:%S") if last_update_time else "Never"
    })

if __name__ == '__main__':
    local_ip = get_local_ip()
    logger.info(f"Server starting... Access the application at: http://{local_ip}:5000")
    logger.info(f"Current workbook URL: {get_saved_url()}")
    logger.info("Auto-reload thread started - data will refresh every 60 seconds")
    app.run(debug=True, host='0.0.0.0', port=5000)