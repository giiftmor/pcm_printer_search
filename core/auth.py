import os
import bcrypt
from functools import wraps
from flask import session, jsonify


def hash_password(password: str) -> bytes:
    return bcrypt.hashpw(password.encode("utf-8"), bcrypt.gensalt())


def check_password(password: str, password_hash: bytes) -> bool:
    return bcrypt.checkpw(password.encode("utf-8"), password_hash)


def init_admin_password(app):
    raw = os.getenv("ADMIN_PASSWORD", "print@NWU")
    app.config["ADMIN_PASSWORD_HASH"] = hash_password(raw)


def admin_required(f):
    @wraps(f)
    def decorated(*args, **kwargs):
        if not session.get("is_admin"):
            return jsonify({"error": "Unauthorized"}), 403
        return f(*args, **kwargs)
    return decorated
