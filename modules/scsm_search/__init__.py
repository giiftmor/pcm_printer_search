from flask import Blueprint

bp = Blueprint("scsm_search", __name__, url_prefix="/api/scsm")

from modules.scsm_search import routes  # noqa: E402, F401
