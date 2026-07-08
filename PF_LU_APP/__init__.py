import logging
import os 
from flask import Flask, render_template, request, redirect, url_for, session, flash

from flask_bcrypt import Bcrypt
from PF_LU_APP.constants import ROLE_SUPER_ADMIN, ROLE_COORDINATOR, ROLE_OPERATOR, ROLE_OBSERVER

bcrypt = Bcrypt()   

def create_app(test_config=None):
    app = Flask(__name__, instance_relative_config=True)

    # Configure the app with default values
    # These values can be overridden by a config.py file in the instance folder or environment variables
    app.config.from_mapping(
        SECRET_KEY=os.environ.get('SECRET_KEY', os.urandom(24).hex()),
        SESSION_PERMANENT=False,
        MAX_CONTENT_LENGTH=16 * 1024 * 1024, # 16 MB max upload size
    )

    if test_config is None:
        app.config.from_pyfile('config.py', silent=True)
    else:
        app.config.from_mapping(test_config)

    try:
        os.makedirs(app.instance_path)
    except OSError:
        pass

    
    bcrypt.init_app(app)

    # Database - Using relative imports within the factory
    from . import db
    db.init_app(app)

    # Blueprints - Using relative imports to avoid package-level conflicts
    from .auth import auth_bp
    app.register_blueprint(auth_bp, url_prefix='/auth')

    from .roles.observer import observer_bp
    app.register_blueprint(observer_bp, url_prefix='/observer')

    from .roles.operator import operator_bp
    app.register_blueprint(operator_bp, url_prefix='/operator')

    from .roles.admin import admin_bp
    app.register_blueprint(admin_bp, url_prefix='/manage')

    from .groups import groups_bp
    app.register_blueprint(groups_bp, url_prefix='/groups')

    from .groups.updates import updates_bp
    app.register_blueprint(updates_bp, url_prefix='/groups')

    from .main import main_bp
    app.register_blueprint(main_bp)

    from .knowledge import knowledge_bp
    app.register_blueprint(knowledge_bp)

    from .inventory import inventory_bp
    app.register_blueprint(inventory_bp)

    # ── Context processor: inject user's groups for navbar group switcher ──
    @app.context_processor
    def inject_user_groups():
        if 'user_id' in session:
            from .db import get_cursor, get_db
            try:
                get_db().rollback()
            except Exception:
                pass
            cur = get_cursor()
            try:
                cur.execute("""
                    SELECT gm.group_id, g.group_name, g.primary_color, gm.role_id, r.role_name
                    FROM group_membership gm
                    JOIN `groups` g ON gm.group_id = g.group_id
                    JOIN roles r ON gm.role_id = r.role_id
                    WHERE gm.user_id = %s AND gm.membership_status = 'active' AND g.status = 'active'
                    ORDER BY g.group_name ASC
                """, (session['user_id'],))
                groups = cur.fetchall()
            except Exception:
                try:
                    get_db().rollback()
                except Exception:
                    pass
                groups = []
            finally:
                cur.close()
            # Resolve current_group_name from session or by looking up current_group_id
            current_group_name = session.get('current_group_name')
            if not current_group_name and session.get('current_group_id'):
                for g in groups:
                    if str(g['group_id']) == str(session['current_group_id']):
                        current_group_name = g['group_name']
                        break
            return dict(user_groups=groups, current_group_name=current_group_name)
        return dict(user_groups=[], current_group_name=None)

    # ── Context processor: inject role constants into all templates ──
    @app.context_processor
    def inject_role_constants():
        return dict(
            ROLE_SUPER_ADMIN=ROLE_SUPER_ADMIN,
            ROLE_COORDINATOR=ROLE_COORDINATOR,
            ROLE_OPERATOR=ROLE_OPERATOR,
            ROLE_OBSERVER=ROLE_OBSERVER,
        )

    # ── Context processor: inject active group boundary geojson ──
    @app.context_processor
    def inject_group_boundary():
        boundary_geojson = None
        if 'current_group_id' in session:
            from .db import get_cursor, get_db
            try:
                get_db().rollback()
            except Exception:
                pass
            cur = get_cursor()
            try:
                cur.execute("SELECT boundary_geojson FROM `groups` WHERE group_id = %s", (session['current_group_id'],))
                row = cur.fetchone()
                if row:
                    boundary_geojson = row.get('boundary_geojson')
            except Exception as e:
                # Column may not exist in older DB schemas; treat as no boundary
                logging.exception(f"Warning: could not read group boundary_geojson: {e}")
                try:
                    get_db().rollback()
                except Exception:
                    pass
            finally:
                try:
                    cur.close()
                except Exception:
                    pass
        return dict(current_group_boundary_geojson=boundary_geojson)

    # ── Before request: re-verify session permissions ──
    @app.before_request
    def refresh_session_permissions():
        if 'user_id' not in session or app.config.get('TESTING'):
            return

        from flask import request as req
        if req.endpoint in ('auth.login', 'auth.register', 'static', None):
            return

        from .db import get_cursor
        try:
            cur = get_cursor()

            if session.get('is_super_admin'):
                cur.execute(f"""
                    SELECT 1 FROM group_membership
                    WHERE user_id = %s AND role_id = {ROLE_SUPER_ADMIN} AND membership_status = 'active'
                """, (session['user_id'],))
                if not cur.fetchone():
                    session['is_super_admin'] = False
                    session.pop('role_id', None)
                    flash("Your admin privileges have been updated. Please re-authenticate if needed.", "info")

            if session.get('current_group_id'):
                cur.execute("""
                    SELECT role_id, membership_status FROM group_membership
                    WHERE user_id = %s AND group_id = %s
                """, (session['user_id'], session['current_group_id']))
                row = cur.fetchone()
                if not row or row['membership_status'] != 'active':
                    session.pop('current_group_id', None)
                    session.pop('current_group_name', None)
                    session.pop('current_group_color', None)
                    session.pop('role_id', None)
                    flash("Your group access has changed. Please select a group.", "warning")

            cur.close()
        except Exception as e:
            logging.exception(f"Session refresh error: {e}")

    # ── Custom Jinja filters ──
    @app.template_filter('date_nz')
    def date_nz(value):
        if not value: return ''
        if isinstance(value, str): return value # in case it's already a string
        return value.strftime('%d/%m/%Y %H:%M')

    @app.template_filter('photo_src')
    def photo_src(value):
        """Return the correct image src for a photo_url field.
        Handles both full URLs (http/https) and relative static paths."""
        if not value:
            return ''
        if value.startswith('http://') or value.startswith('https://'):
            return value
        # Local static file path — build URL via url_for
        from flask import url_for
        return url_for('static', filename=value)

    # ── Context processor: inject species colours ──
    @app.context_processor
    def inject_species_colors():
        from .species_colors import get_species_colors, species_badge_style
        return dict(
            species_colors=get_species_colors(),
            species_badge_style=species_badge_style,
        )

    return app