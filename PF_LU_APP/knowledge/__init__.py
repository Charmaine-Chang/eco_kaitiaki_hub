from flask import Blueprint

knowledge_bp = Blueprint("knowledge", __name__, url_prefix="/knowledge")

from . import knowledge_routes  # noqa: E402, F401
