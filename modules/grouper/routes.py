from flask import Blueprint, request, jsonify
from modules.grouper.engine import build_grouper_url, validate_user_id

grouper_bp = Blueprint("grouper", __name__)


@grouper_bp.route("/api/grouper/lookup", methods=["POST"])
def lookup():
    user_id = request.form.get("user_id", "").strip()
    if not validate_user_id(user_id):
        return jsonify({"error": "Please enter a user ID."})
    url = build_grouper_url(user_id)
    return jsonify({"url": url})
