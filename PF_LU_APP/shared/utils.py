"""Shared utility functions used across the application."""

import json
from datetime import datetime, timedelta, date
from decimal import Decimal


def safe_json_dumps(data, **kwargs):
    """JSON dumps that handles PyMySQL-specific types (Decimal, date, datetime)."""

    class _Encoder(json.JSONEncoder):
        def default(self, obj):
            if isinstance(obj, Decimal):
                return float(obj) if '.' in str(obj) else int(obj)
            if isinstance(obj, (date, datetime)):
                return obj.isoformat()
            if isinstance(obj, bytes):
                return obj.decode('utf-8', errors='replace')
            return super().default(obj)

    return json.dumps(data, cls=_Encoder, **kwargs)


def resolve_date_preset(preset, today=None):
    """Convert a preset string (7d, 30d, this_month) to (start_date, end_date).

    Returns:
        (start_date_str, end_date_str) or (None, None) if preset is unknown.
    """
    if today is None:
        today = datetime.today()
    if preset == '7d':
        return (today - timedelta(days=7)).strftime('%Y-%m-%d'), today.strftime('%Y-%m-%d')
    elif preset == '30d':
        return (today - timedelta(days=30)).strftime('%Y-%m-%d'), today.strftime('%Y-%m-%d')
    elif preset == 'this_month':
        return today.replace(day=1).strftime('%Y-%m-%d'), today.strftime('%Y-%m-%d')
    return None, None


def build_role_scoped_where(session, table_alias='l'):
    """Build a WHERE clause fragment that scopes results by the user's role.

    Super admins see everything. Coordinators/operators/observers see their group.
    Others see only their assigned lines.

    Returns:
        (where_str, params) — e.g. ("l.group_id = %s", [group_id])
    """
    from PF_LU_APP.constants import ROLE_COORDINATOR, ROLE_OPERATOR, ROLE_OBSERVER

    where_parts = []
    params = []

    is_super_admin = session.get('is_super_admin')
    role_id = session.get('role_id')
    current_group_id = session.get('current_group_id')

    if is_super_admin:
        pass
    elif role_id in (ROLE_COORDINATOR, ROLE_OPERATOR, ROLE_OBSERVER):
        where_parts.append(f'{table_alias}.group_id = %s')
        params.append(current_group_id)
    else:
        where_parts.append('t.line_id IN (SELECT line_id FROM operator_lines WHERE user_id = %s)')
        params.append(session.get('user_id'))

    return ' AND '.join(where_parts), tuple(params)
