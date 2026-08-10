import os
from dotenv import load_dotenv

load_dotenv()


def _read_app_version():
    try:
        with open(os.path.join(os.path.dirname(os.path.abspath(__file__)), "VERSION")) as f:
            return f.read().strip() or "0.0.0"
    except FileNotFoundError:
        return "0.0.0"


class Config:
    APP_VERSION = _read_app_version()
    SECRET_KEY = os.getenv("FLASK_SECRET_KEY", "dev-secret-key-do-not-use-in-production")
    ADMIN_PASSWORD_HASH = None  # Set at startup from env
    WORKBOOK_URL = os.getenv("WORKBOOK_URL", "https://nextcloud.nwu.ac.za/index.php/s/4RdDP4qX3mMoXc7")
    DATA_REFRESH_INTERVAL = int(os.getenv("DATA_REFRESH_INTERVAL", "60"))
    QUICK_LINKS_FILE = os.getenv("QUICK_LINKS_FILE", "quick_links.json")
    SCSM_API_URL = os.getenv("SCSM_API_URL", "http://scsm-search:3000")
    SCSM_API_KEY = os.getenv("SCSM_API_KEY", "")
    SCSM_PORTAL_BASE = os.getenv("SCSM_PORTAL_BASE", "https://support.nwu.ac.za")
