import os
from dotenv import load_dotenv

load_dotenv()


class Config:
    SECRET_KEY = os.getenv("FLASK_SECRET_KEY", "dev-secret-key-do-not-use-in-production")
    ADMIN_PASSWORD_HASH = None  # Set at startup from env
    WORKBOOK_URL = os.getenv("WORKBOOK_URL", "https://nextcloud.nwu.ac.za/index.php/s/4RdDP4qX3mMoXc7")
    DATA_REFRESH_INTERVAL = int(os.getenv("DATA_REFRESH_INTERVAL", "60"))
    QUICK_LINKS_FILE = os.getenv("QUICK_LINKS_FILE", "quick_links.json")
