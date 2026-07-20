from flask import Blueprint, request, jsonify
from modules.idm_lookup.engine import build_idm_url, validate_user_id

idm_bp = Blueprint("idm_lookup", __name__)


@idm_bp.route("/api/idm/lookup", methods=["POST"])
def lookup():
    user_id = request.form.get("user_id", "").strip()
    if not validate_user_id(user_id):
        return jsonify({"error": "Please enter a user ID."})
    url = build_idm_url(user_id)
    return jsonify({"url": url})
