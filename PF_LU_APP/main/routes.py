import logging
from flask import Blueprint, render_template, request, redirect, url_for, session, flash
from PF_LU_APP.db import get_cursor
from PF_LU_APP.constants import ROLE_COORDINATOR

main_bp = Blueprint('main', __name__)

@main_bp.route('/')
def home():
    try:
        cursor = get_cursor()
        # Active groups with geographic info
        cursor.execute("""
            SELECT group_id, group_name, description, geographic_area, visibility
            FROM groups
            WHERE status = 'active' AND group_name != 'System Management'
            ORDER BY group_name ASC
        """)
        groups = cursor.fetchall()

        # Current user's group memberships for joining logic
        user_group_ids = set()
        if session.get('user_id'):
            cursor.execute("""
                SELECT group_id FROM group_membership
                WHERE user_id = %s AND membership_status = 'active'
            """, (session['user_id'],))
            user_group_ids = {row['group_id'] for row in cursor.fetchall()}
            
        cursor.close()
    except Exception as e:
        logging.exception(f"Error fetching data for home page: {e}")
        groups = []
        user_group_ids = set()
        
    return render_template('home.html', groups=groups, user_group_ids=user_group_ids)


@main_bp.route('/find_group')
def find_group():
    try:
        cursor = get_cursor()
        cursor.execute("""
            SELECT group_id, group_name, description, geographic_area, visibility
            FROM groups
            WHERE status = 'active' AND group_name != 'System Management'
            ORDER BY group_name ASC
        """)
        groups = cursor.fetchall()

        user_group_ids = set()
        if session.get('user_id'):
            cursor.execute("""
                SELECT group_id FROM group_membership
                WHERE user_id = %s AND membership_status = 'active'
            """, (session['user_id'],))
            user_group_ids = {row['group_id'] for row in cursor.fetchall()}

        cursor.close()
    except Exception as e:
        logging.exception(f"Error fetching groups: {e}")
        groups = []
        user_group_ids = set()

    return render_template('groups/find.html', groups=groups, user_group_ids=user_group_ids)

@main_bp.route('/search')
def search():
    query = request.args.get('q', '').strip()
    if not query:
        return redirect(request.referrer or url_for('main.home'))
        
    try:
        cursor = get_cursor()
        search_pattern = f"%{query}%"
        
        # Search lines
        cursor.execute("SELECT * FROM lines WHERE line_name ILIKE %s ORDER BY line_name", (search_pattern,))
        found_lines = cursor.fetchall()
        
        # Search traps
        cursor.execute("""
            SELECT t.trap_code, tt.trap_type_name, l.line_id, l.line_name, t.latitude, t.longitude 
            FROM traps t 
            JOIN trap_type tt ON t.trap_type_id = tt.trap_type_id
            JOIN lines l ON t.line_id = l.line_id
            WHERE t.trap_code ILIKE %s OR tt.trap_type_name ILIKE %s
            ORDER BY t.trap_code
        """, (search_pattern, search_pattern))
        found_traps = cursor.fetchall()
        
        cursor.close()
    except Exception as e:
        logging.exception(f"Search error: {e}")
        found_lines = []
        found_traps = []

    return render_template('search_results.html', query=query, lines=found_lines, traps=found_traps)

@main_bp.route('/exit_group')
def exit_group():
    # Clear all group-context variables
    session.pop('current_group_id', None)
    session.pop('current_group_name', None)
    session.pop('current_group_color', None)
    session.pop('role_id', None)
    
    flash("Exited group context.", "info")
    return redirect(url_for('main.home'))

@main_bp.route('/knowledge')
def knowledge_hub():
    query = request.args.get('q', '').strip()
    selected_category = request.args.get('category', '').strip()
    
    try:
        cursor = get_cursor()
        
        # Fetch unique categories for the filter UI
        cursor.execute("SELECT DISTINCT category FROM knowledge_hub WHERE is_published = TRUE ORDER BY category ASC")
        categories = [row['category'] for row in cursor.fetchall()]

        # Build query
        base_sql = """
            SELECT kh.*, u.username 
            FROM knowledge_hub kh
            JOIN users u ON kh.user_id = u.user_id
            WHERE kh.is_published = TRUE
        """
        params = []
        
        if query:
            base_sql += " AND (kh.title ILIKE %s OR kh.content ILIKE %s OR kh.category ILIKE %s)"
            search_pattern = f"%{query}%"
            params.extend([search_pattern, search_pattern, search_pattern])
            
        if selected_category:
            base_sql += " AND kh.category = %s"
            params.append(selected_category)

        featured_sql = base_sql + " AND kh.is_featured = TRUE ORDER BY kh.created_at DESC"
        cursor.execute(featured_sql, tuple(params))
        featured_entries = cursor.fetchall()

        entries_sql = base_sql + " AND kh.is_featured = FALSE ORDER BY kh.created_at DESC"
        cursor.execute(entries_sql, tuple(params))
        entries = cursor.fetchall()
        cursor.close()
    except Exception as e:
        logging.exception(f"Knowledge Hub error: {e}")
        entries = []
        featured_entries = []
        categories = []
        
    return render_template('knowledge/list.html', 
                           entries=entries,
                           featured_entries=featured_entries,
                           query=query, 
                           categories=categories,
                           selected_category=selected_category,
                           active_page='knowledge',
                           is_coordinator=session.get('user_id') and session.get('role_id') == ROLE_COORDINATOR)
