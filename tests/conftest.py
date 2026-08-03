import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

os.environ.setdefault("ADMIN_PASSWORD", "test-password")
os.environ.setdefault("FLASK_SECRET_KEY", "test-secret")
