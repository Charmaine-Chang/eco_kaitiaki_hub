from flask import Blueprint

admin_bp = Blueprint('admin', __name__)

# Import routes to register them with the blueprint
from PF_LU_APP.traps import trap_admin_routes, line_admin_routes, bait_station_admin_routes, assignment_admin_routes
from PF_LU_APP.catches import catch_admin_routes, analytics_admin_routes, export_admin_routes
from PF_LU_APP.inventory import inventory_admin_routes, equipment_admin_routes, storage_admin_routes
from PF_LU_APP.dashboard import dashboard_admin_routes
from PF_LU_APP.users import user_routes
from PF_LU_APP.groups import group_admin_routes
from PF_LU_APP.metadata import metadata_admin_routes
