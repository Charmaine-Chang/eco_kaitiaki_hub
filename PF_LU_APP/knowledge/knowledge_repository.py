"""Repository layer for knowledge hub queries."""

from PF_LU_APP.db import get_cursor


def check_active_member(user_id, group_id):
    """Check if user is an active member of the group."""
    cursor = get_cursor()
    cursor.execute("""
        SELECT 1 FROM group_membership gm
        JOIN `groups` g ON g.group_id = gm.group_id
        WHERE gm.user_id = %s AND gm.group_id = %s
        AND gm.membership_status = 'active' AND g.status = 'active'
    """, (user_id, group_id))
    row = cursor.fetchone()
    cursor.close()
    return row is not None


def fetch_entry(entry_id, group_id):
    """Fetch a knowledge entry with author info."""
    cursor = get_cursor()
    cursor.execute("""
        SELECT k.*, u.username AS author_username,
               TRIM(CONCAT(COALESCE(u.first_name, ''), ' ', COALESCE(u.last_name, ''))) AS author_display
        FROM knowledge_hub k
        JOIN users u ON u.user_id = k.user_id
        WHERE k.entry_id = %s AND k.group_id = %s
    """, (entry_id, group_id))
    row = cursor.fetchone()
    cursor.close()
    return row


def fetch_group_name(group_id):
    """Get group name."""
    cursor = get_cursor()
    cursor.execute("SELECT group_name FROM `groups` WHERE group_id = %s", (group_id,))
    row = cursor.fetchone()
    cursor.close()
    return row['group_name'] if row else None


# ── Hub List ─────────────────────────────────────────────────────

def fetch_published_entries(group_id):
    """Fetch all published entries for a group."""
    cursor = get_cursor()
    cursor.execute("""
        SELECT k.entry_id, k.category, k.title, k.content, k.is_featured,
               k.is_published, k.created_at, k.updated_at, u.username AS author_username
        FROM knowledge_hub k
        JOIN users u ON u.user_id = k.user_id
        WHERE k.group_id = %s AND k.is_published = TRUE
        ORDER BY k.is_featured DESC, k.updated_at IS NULL, k.updated_at DESC, k.created_at DESC
    """, (group_id,))
    rows = cursor.fetchall()
    cursor.close()
    return rows


def fetch_categories(group_id=None, approved_only=True):
    """Fetch distinct categories."""
    cursor = get_cursor()
    query = "SELECT DISTINCT category FROM knowledge_hub"
    params = []
    conditions = []
    if approved_only:
        conditions.append("status = 'approved'")
    if group_id:
        conditions.append("group_id = %s")
        params.append(group_id)
    if conditions:
        query += " WHERE " + " AND ".join(conditions)
    query += " ORDER BY category ASC"
    cursor.execute(query, tuple(params))
    rows = cursor.fetchall()
    cursor.close()
    return [r['category'] for r in rows]


# ── Entry Detail ─────────────────────────────────────────────────

def fetch_entry_revisions_count(entry_id):
    """Get number of revisions for an entry."""
    cursor = get_cursor()
    cursor.execute("SELECT COUNT(*) AS c FROM knowledge_hub_revision WHERE entry_id = %s", (entry_id,))
    row = cursor.fetchone()
    cursor.close()
    return row['c'] if row else 0


# ── Submit ───────────────────────────────────────────────────────

def create_entry(group_id, user_id, category, title, content, photo_url=None):
    """Create a new knowledge entry."""
    cursor = get_cursor()
    cursor.execute("""
        INSERT INTO knowledge_hub (group_id, user_id, category, title, content, photo_url, is_published, status)
        VALUES (%s, %s, %s, %s, %s, %s, FALSE, 'pending')
    """, (group_id, user_id, category, title, content, photo_url))
    cursor.close()


# ── My Submissions ───────────────────────────────────────────────

def fetch_user_submissions(user_id):
    """Fetch all entries submitted by a user."""
    cursor = get_cursor()
    cursor.execute("""
        SELECT kh.entry_id, kh.title, kh.category, kh.content, kh.status,
               kh.created_at, g.group_name
        FROM knowledge_hub kh
        JOIN `groups` g ON kh.group_id = g.group_id
        WHERE kh.user_id = %s
        ORDER BY kh.created_at DESC
    """, (user_id,))
    rows = cursor.fetchall()
    cursor.close()
    return rows


# ── Review (Admin) ──────────────────────────────────────────────

def fetch_pending_entries():
    """Fetch all pending knowledge entries for review."""
    cursor = get_cursor()
    cursor.execute("""
        SELECT kh.entry_id, kh.title, kh.category, kh.content, kh.status,
               kh.created_at, u.username, u.first_name, u.last_name
        FROM knowledge_hub kh
        JOIN users u ON kh.user_id = u.user_id
        WHERE kh.status = 'pending'
        ORDER BY kh.created_at ASC
    """)
    rows = cursor.fetchall()
    cursor.close()
    return rows


def approve_entry(entry_id):
    """Approve a knowledge entry."""
    cursor = get_cursor()
    cursor.execute(
        "UPDATE knowledge_hub SET is_published = TRUE, status = 'approved' WHERE entry_id = %s",
        (entry_id,),
    )
    cursor.close()


def reject_entry(entry_id):
    """Reject a knowledge entry."""
    cursor = get_cursor()
    cursor.execute(
        "UPDATE knowledge_hub SET is_published = FALSE, status = 'rejected' WHERE entry_id = %s",
        (entry_id,),
    )
    cursor.close()


# ── Edit ─────────────────────────────────────────────────────────

def fetch_approved_entry(entry_id):
    """Fetch an approved entry for editing."""
    cursor = get_cursor()
    cursor.execute(
        "SELECT * FROM knowledge_hub WHERE entry_id = %s AND status = 'approved'",
        (entry_id,),
    )
    row = cursor.fetchone()
    cursor.close()
    return row


def update_entry(entry_id, title, category, content, photo_url):
    """Update a knowledge entry."""
    cursor = get_cursor()
    cursor.execute("""
        UPDATE knowledge_hub SET title=%s, category=%s, content=%s, photo_url=%s, updated_at=CURRENT_TIMESTAMP
        WHERE entry_id=%s
    """, (title, category, content, photo_url, entry_id))
    cursor.close()


def create_revision(entry_id, version_number, category, title, content,
                    photo_url, is_featured, is_published, archived_by_user_id):
    """Create a revision snapshot."""
    cursor = get_cursor()
    cursor.execute("""
        INSERT INTO knowledge_hub_revision
            (entry_id, version_number, category, title, content, photo_url,
             is_featured, is_published, archived_by_user_id)
        VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s)
    """, (entry_id, version_number, category, title, content,
          photo_url, is_featured, is_published, archived_by_user_id))
    cursor.close()


def get_next_version_number(entry_id):
    """Get the next version number for an entry."""
    cursor = get_cursor()
    cursor.execute(
        "SELECT COALESCE(MAX(version_number), 0) + 1 AS next_v FROM knowledge_hub_revision WHERE entry_id = %s",
        (entry_id,),
    )
    row = cursor.fetchone()
    cursor.close()
    return row['next_v'] if row else 1


# ── Toggle Featured ──────────────────────────────────────────────

def fetch_entry_featured_status(entry_id):
    """Get current featured status."""
    cursor = get_cursor()
    cursor.execute("SELECT is_featured FROM knowledge_hub WHERE entry_id = %s", (entry_id,))
    row = cursor.fetchone()
    cursor.close()
    return row['is_featured'] if row else None


def toggle_featured(entry_id, is_featured):
    """Toggle featured status."""
    cursor = get_cursor()
    cursor.execute("UPDATE knowledge_hub SET is_featured = %s WHERE entry_id = %s", (is_featured, entry_id))
    cursor.close()


# ── View Revisions ──────────────────────────────────────────────

def fetch_entry_with_author(entry_id):
    """Fetch entry with author info."""
    cursor = get_cursor()
    cursor.execute("""
        SELECT kh.*, u.username, u.first_name, u.last_name
        FROM knowledge_hub kh
        JOIN users u ON kh.user_id = u.user_id
        WHERE kh.entry_id = %s
    """, (entry_id,))
    row = cursor.fetchone()
    cursor.close()
    return row


def fetch_revisions(entry_id):
    """Fetch all revisions for an entry."""
    cursor = get_cursor()
    cursor.execute("""
        SELECT khr.*, u.username, u.first_name, u.last_name
        FROM knowledge_hub_revision khr
        JOIN users u ON khr.archived_by_user_id = u.user_id
        WHERE khr.entry_id = %s
        ORDER BY khr.version_number DESC
    """, (entry_id,))
    rows = cursor.fetchall()
    cursor.close()
    return rows
