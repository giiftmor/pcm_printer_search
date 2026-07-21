from flask import Blueprint

bp = Blueprint('user_lookup', __name__)

from modules.user_lookup import routes  # noqa: E402, F401
