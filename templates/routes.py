from flask import Blueprint, render_template

pages_bp = Blueprint("pages", __name__)


@pages_bp.route("/")
def dashboard():
    return render_template("dashboard.html")


@pages_bp.route("/printer-search")
def printer_search():
    return render_template("printer_search.html")


@pages_bp.route("/idm-lookup")
def idm_lookup():
    return render_template("idm_lookup.html")


@pages_bp.route("/grouper")
def grouper():
    return render_template("grouper.html")


@pages_bp.route("/quick-links")
def quick_links():
    return render_template("quick_links.html")


@pages_bp.route("/user-lookup")
def user_lookup():
    return render_template("user_lookup.html")
