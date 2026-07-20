from flask import Blueprint, request, jsonify
from modules.quick_links.engine import get_links, add_link, remove_link
from core.auth import admin_required

links_bp = Blueprint("links", __name__)


@links_bp.route("/api/links")
def list_links():
    return jsonify(get_links())


@links_bp.route("/api/links", methods=["POST"])
@admin_required
def create_link():
    data = request.get_json()
    name = data.get("name", "").strip()
    url = data.get("url", "").strip()
    icon = data.get("icon", "🔗").strip()
    if not name or not url:
        return jsonify({"error": "Name and URL required"}), 400
    return jsonify(add_link(name, url, icon)), 201


@links_bp.route("/api/links/<link_id>", methods=["DELETE"])
@admin_required
def delete_link(link_id):
    remove_link(link_id)
    return jsonify({"success": True})
