from flask import Blueprint, request, jsonify
from modules.quick_links.engine import (
    get_categories,
    add_category,
    remove_category,
    add_link,
    remove_link,
)
from core.auth import admin_required

links_bp = Blueprint("links", __name__)


@links_bp.route("/api/links")
def list_links():
    return jsonify({"categories": get_categories()})


@links_bp.route("/api/links", methods=["POST"])
@admin_required
def create_link():
    data = request.get_json(silent=True) or {}
    category_id = (data.get("category_id") or "").strip()
    name = (data.get("name") or "").strip()
    url = (data.get("url") or "").strip()
    icon = (data.get("icon") or "🔗").strip()
    if not category_id or not name or not url:
        return jsonify({"error": "Category, name, and URL required"}), 400
    try:
        return jsonify(add_link(category_id, name, url, icon)), 201
    except KeyError:
        return jsonify({"error": "Unknown category"}), 400


@links_bp.route("/api/links/<link_id>", methods=["DELETE"])
@admin_required
def delete_link(link_id):
    remove_link(link_id)
    return jsonify({"success": True})


@links_bp.route("/api/links/categories", methods=["POST"])
@admin_required
def create_category():
    data = request.get_json(silent=True) or {}
    name = (data.get("name") or "").strip()
    if not name:
        return jsonify({"error": "Name required"}), 400
    return jsonify(add_category(name)), 201


@links_bp.route("/api/links/categories/<category_id>", methods=["DELETE"])
@admin_required
def delete_category(category_id):
    try:
        removed = remove_category(category_id)
    except ValueError:
        return jsonify({"error": "Category is not empty"}), 409
    if not removed:
        return jsonify({"error": "Category not found"}), 404
    return jsonify({"success": True})
