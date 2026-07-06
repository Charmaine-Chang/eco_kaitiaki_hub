from flask import Blueprint

observer_bp = Blueprint('observer', __name__, url_prefix='/observer')

from PF_LU_APP.dashboard import dashboard_observer_routes
from PF_LU_APP.traps import line_observer_routes
from PF_LU_APP.catches import catch_observer_routes, analytics_observer_routes
