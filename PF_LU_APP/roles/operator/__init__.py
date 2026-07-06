from flask import Blueprint

operator_bp = Blueprint('operator', __name__, url_prefix='/operator')

from PF_LU_APP.traps import bait_station_operator_routes, equipment_map_routes
from PF_LU_APP.catches import catch_operator_routes, analytics_operator_routes
from PF_LU_APP.inventory import inventory_operator_routes, equipment_operator_routes
from PF_LU_APP.dashboard import dashboard_operator_routes
from PF_LU_APP.observations import observation_operator_routes
