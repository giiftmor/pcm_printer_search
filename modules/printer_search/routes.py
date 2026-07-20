from flask import Blueprint, request, jsonify, session, current_app
import modules.printer_search.engine as engine
from core.auth import admin_required, check_password
import logging

logger = logging.getLogger(__name__)
printer_bp = Blueprint("printer", __name__)

engine.init()


@printer_bp.route("/api/printer/search", methods=["POST"])
def search():
    search_term = request.form.get("search_term", "").strip()
    if not search_term:
        return jsonify({"error": "Please enter a search term."})
    logger.info(f"Search: '{search_term}'")
    return jsonify(engine.search_all_sheets(search_term))


@printer_bp.route("/api/printer/last-update")
def last_update():
    return jsonify({
        "last_update": engine.last_update_time.isoformat() if engine.last_update_time else None,
        "timestamp": engine.last_update_time.strftime("%Y-%m-%d %H:%M:%S") if engine.last_update_time else "Never"
    })


@printer_bp.route("/api/admin/status")
def admin_status():
    return jsonify({"is_admin": session.get("is_admin", False)})


@printer_bp.route("/api/admin/login", methods=["POST"])
def admin_login():
    password = request.form.get("password", "").strip()
    if current_app.config.get("ADMIN_PASSWORD_HASH") and check_password(password, current_app.config["ADMIN_PASSWORD_HASH"]):
        session["is_admin"] = True
        return jsonify({"success": True, "message": "Login successful"})
    return jsonify({"success": False, "message": "Invalid password"})


@printer_bp.route("/api/admin/logout", methods=["POST"])
def admin_logout():
    session.pop("is_admin", None)
    return jsonify({"success": True, "message": "Logout successful"})


@printer_bp.route("/api/admin/get_url")
@admin_required
def admin_get_url():
    return jsonify({"url": engine.get_saved_url()})


@printer_bp.route("/api/admin/update_url", methods=["POST"])
@admin_required
def admin_update_url():
    new_url = request.form.get("url", "").strip()
    if not new_url:
        return jsonify({"success": False, "message": "URL cannot be empty"})
    if engine.save_url(new_url):
        with engine.data_load_lock:
            engine.df_all_sheets = engine.load_excel_from_url()
        return jsonify({"success": True, "message": "URL updated and data reloaded"})
    return jsonify({"success": False, "message": "Failed to save URL"})


@printer_bp.route("/api/admin/reload_data")
@admin_required
def admin_reload_data():
    with engine.data_load_lock:
        engine.df_all_sheets = engine.load_excel_from_url()
    if engine.df_all_sheets is not None:
        return jsonify({"success": True, "message": "Data reloaded"})
    return jsonify({"success": False, "message": "Failed to reload"})
