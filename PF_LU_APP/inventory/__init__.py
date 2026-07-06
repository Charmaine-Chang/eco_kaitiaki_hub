from flask import Blueprint

inventory_bp = Blueprint('inventory', __name__, url_prefix='/inventory')

from . import inventory_routes  # noqa: E402, F401
