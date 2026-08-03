import os
import glob
import json
import time
from flask import Blueprint, render_template, send_file
from config import Config

pages_bp = Blueprint("pages", __name__)


def _extension_manifest_version():
    manifest_path = os.path.join(
        os.path.dirname(os.path.dirname(__file__)), "browser_extension", "manifest.json"
    )
    try:
        with open(manifest_path) as f:
            return json.load(f).get("version", "0.0.0")
    except (IOError, ValueError):
        return "0.0.0"


@pages_bp.route("/api/status")
def api_status():
    return {
        "name": "PCM Compass",
        "app_version": Config.APP_VERSION,
        "extension_version": _extension_manifest_version(),
    }


@pages_bp.route("/")
def dashboard():
    return render_template("dashboard.html")


@pages_bp.route("/printer-search")
def printer_search():
    return render_template("printer_search.html")


@pages_bp.route("/quick-links")
def quick_links():
    return render_template("quick_links.html")


@pages_bp.route("/user-lookup")
def user_lookup():
    return render_template("user_lookup.html")


@pages_bp.route("/download-extension")
def download_extension():
    dist_dir = os.path.join(os.path.dirname(os.path.dirname(__file__)), "static", "dist")
    zips = sorted(glob.glob(os.path.join(dist_dir, "pcm-compass-v*.zip")), reverse=True)
    version = _extension_manifest_version()
    date = ""
    if zips:
        fname = os.path.basename(zips[0])
        version = fname.replace("pcm-compass-v", "").replace(".zip", "")
        date = time.strftime("%Y-%m-%d", time.localtime(os.path.getmtime(zips[0])))
    return render_template("download_extension.html", version=version, date=date)


@pages_bp.route("/download-extension/zip")
def download_extension_zip():
    dist_dir = os.path.join(os.path.dirname(os.path.dirname(__file__)), "static", "dist")
    zips = sorted(glob.glob(os.path.join(dist_dir, "pcm-compass-v*.zip")), reverse=True)
    if not zips:
        return "No extension package found. Run bin/build-extension.sh first.", 404
    return send_file(zips[0], as_attachment=True)
