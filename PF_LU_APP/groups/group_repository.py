"""Repository layer for group management and membership queries."""

from PF_LU_APP.db import get_cursor
from PF_LU_APP.constants import ROLE_OBSERVER, ROLE_COORDINATOR


def fetch_membership_role(user_id, group_id):
    """Get user's active role in a group."""
    cursor = get_cursor()
    cursor.execute(
        "SELECT role_id FROM group_membership WHERE user_id = %s AND group_id = %s AND membership_status = 'active'",
        (user_id, group_id),
    )
    row = cursor.fetchone()
    cursor.close()
    return row['role_id'] if row else None


def check_group_name_exists(group_name):
    """Check if a group name already exists."""
    cursor = get_cursor()
    cursor.execute("SELECT 1 FROM `groups` WHERE LOWER(group_name) = LOWER(%s)", (group_name,))
    row = cursor.fetchone()
    cursor.close()
    return row is not None


def create_group(group_name, description, geographic_area, visibility, created_by, branding_image=None):
    """Create a new group application."""
    cursor = get_cursor()
    cursor.execute("""
        INSERT INTO `groups` (group_name, description, geographic_area, visibility, created_by, status, branding_image)
        VALUES (%s, %s, %s, %s, %s, 'pending', %s)
    """, (group_name, description, geographic_area, visibility, created_by, branding_image))
    cursor.close()


def fetch_group_visibility(group_id):
    """Get group visibility."""
    cursor = get_cursor()
    cursor.execute("SELECT visibility FROM `groups` WHERE group_id = %s", (group_id,))
    row = cursor.fetchone()
    cursor.close()
    return row['visibility'] if row else None


def fetch_membership_status(user_id, group_id):
    """Check membership status."""
    cursor = get_cursor()
    cursor.execute(
        "SELECT membership_status FROM group_membership WHERE user_id = %s AND group_id = %s",
        (user_id, group_id),
    )
    row = cursor.fetchone()
    cursor.close()
    return row['membership_status'] if row else None


def update_membership_status(user_id, group_id, status, role_id):
    """Update membership status and role."""
    cursor = get_cursor()
    cursor.execute(
        "UPDATE group_membership SET membership_status = %s, role_id = %s WHERE user_id = %s AND group_id = %s",
        (status, role_id, user_id, group_id),
    )
    cursor.close()


def create_membership(user_id, group_id, role_id, status):
    """Create a new membership."""
    cursor = get_cursor()
    cursor.execute(
        "INSERT INTO group_membership (user_id, group_id, role_id, membership_status) VALUES (%s, %s, %s, %s)",
        (user_id, group_id, role_id, status),
    )
    cursor.close()


# ── Group Updates ────────────────────────────────────────────────

def fetch_update_detail(update_id, group_id):
    """Fetch a published group update with author and like count."""
    cursor = get_cursor()
    cursor.execute("""
        SELECT gu.update_id, gu.group_id, gu.update_title, gu.update_content,
               gu.created_at, u.username,
               COALESCE(NULLIF(TRIM(CONCAT(u.first_name, ' ', u.last_name)), ''), u.username) AS author_display,
               COALESCE(lc.like_count, 0) AS like_count
        FROM group_updates gu
        JOIN users u ON gu.user_id = u.user_id
        LEFT JOIN (SELECT update_id, COUNT(*) AS like_count FROM update_likes GROUP BY update_id) lc ON lc.update_id = gu.update_id
        WHERE gu.update_id = %s AND gu.group_id = %s AND gu.is_published = TRUE
    """, (update_id, group_id))
    row = cursor.fetchone()
    cursor.close()
    return row


def check_user_liked_update(update_id, user_id):
    """Check if user liked an update."""
    cursor = get_cursor()
    cursor.execute("SELECT like_id FROM update_likes WHERE update_id = %s AND user_id = %s", (update_id, user_id))
    row = cursor.fetchone()
    cursor.close()
    return row is not None


def fetch_update_comments(update_id):
    """Fetch comments for an update."""
    cursor = get_cursor()
    cursor.execute("""
        SELECT c.comment_id, c.comment_content, c.created_at, c.user_id, u.username,
               COALESCE(NULLIF(TRIM(CONCAT(u.first_name, ' ', u.last_name)), ''), u.username) AS author_display
        FROM update_comments c
        JOIN users u ON c.user_id = u.user_id
        WHERE c.update_id = %s
        ORDER BY c.created_at ASC, c.comment_id ASC
    """, (update_id,))
    rows = cursor.fetchall()
    cursor.close()
    return rows


def fetch_update_images(update_id):
    """Fetch images for an update."""
    cursor = get_cursor()
    cursor.execute(
        "SELECT * FROM group_update_images WHERE update_id = %s ORDER BY image_id ASC",
        (update_id,),
    )
    rows = cursor.fetchall()
    cursor.close()
    return rows


def check_update_exists(update_id, group_id):
    """Check if a published update exists."""
    cursor = get_cursor()
    cursor.execute(
        "SELECT 1 FROM group_updates WHERE update_id = %s AND group_id = %s AND is_published = TRUE",
        (update_id, group_id),
    )
    row = cursor.fetchone()
    cursor.close()
    return row is not None


def add_comment(update_id, user_id, content):
    """Add a comment to an update."""
    cursor = get_cursor()
    cursor.execute(
        "INSERT INTO update_comments (update_id, user_id, comment_content) VALUES (%s, %s, %s)",
        (update_id, user_id, content),
    )
    cursor.close()


def delete_comment(comment_id, update_id, group_id):
    """Delete a comment (only own comments)."""
    cursor = get_cursor()
    cursor.execute("""
        DELETE c FROM update_comments c
        JOIN group_updates gu ON gu.update_id = c.update_id
        WHERE c.comment_id = %s AND c.update_id = %s AND gu.group_id = %s
    """, (comment_id, update_id, group_id))
    row = cursor.rowcount
    cursor.close()
    return row > 0


# ── Group Updates CRUD ───────────────────────────────────────────

def fetch_group_name(group_id):
    """Get group name."""
    cursor = get_cursor()
    cursor.execute("SELECT group_name FROM `groups` WHERE group_id = %s", (group_id,))
    row = cursor.fetchone()
    cursor.close()
    return row['group_name'] if row else None


def check_coordinator_access(user_id, group_id, is_super_admin=False):
    """Check if user is a coordinator or super admin for the group."""
    if is_super_admin:
        return True
    cursor = get_cursor()
    cursor.execute(
        "SELECT role_id, membership_status FROM group_membership WHERE user_id = %s AND group_id = %s",
        (user_id, group_id),
    )
    membership = cursor.fetchone()
    cursor.close()
    if not membership or membership['membership_status'] != 'active':
        return False
    return membership['role_id'] == ROLE_COORDINATOR


def fetch_updates_list(group_id, include_drafts=False):
    """Fetch updates with author info and engagement counts."""
    cursor = get_cursor()
    query = """
        SELECT u.*, us.first_name, us.last_name,
               COALESCE(NULLIF(TRIM(CONCAT(us.first_name, ' ', us.last_name)), ''), us.username) AS author_display,
               COALESCE(lc.like_count, 0) AS like_count,
               COALESCE(cc.comment_count, 0) AS comment_count
        FROM group_updates u
        JOIN users us ON u.user_id = us.user_id
        LEFT JOIN (SELECT update_id, COUNT(*) AS like_count FROM update_likes GROUP BY update_id) lc ON lc.update_id = u.update_id
        LEFT JOIN (SELECT update_id, COUNT(*) AS comment_count FROM update_comments GROUP BY update_id) cc ON cc.update_id = u.update_id
        WHERE u.group_id = %s
    """
    if not include_drafts:
        query += " AND u.is_published = TRUE"
    query += " ORDER BY u.created_at DESC"
    cursor.execute(query, (group_id,))
    rows = cursor.fetchall()
    cursor.close()
    return rows


def fetch_update_images_batch(update_ids):
    """Fetch images for multiple updates."""
    if not update_ids:
        return {}
    cursor = get_cursor()
    placeholders = ', '.join(['%s'] * len(update_ids))
    cursor.execute(
        f"SELECT * FROM group_update_images WHERE update_id IN ({placeholders}) ORDER BY image_id ASC",
        tuple(update_ids),
    )
    rows = cursor.fetchall()
    cursor.close()
    images_map = {}
    for img in rows:
        images_map.setdefault(img['update_id'], []).append(img)
    return images_map


def fetch_user_liked_ids(user_id, update_ids):
    """Fetch which updates a user has liked."""
    if not update_ids:
        return set()
    cursor = get_cursor()
    placeholders = ', '.join(['%s'] * len(update_ids))
    cursor.execute(
        f"SELECT update_id FROM update_likes WHERE user_id = %s AND update_id IN ({placeholders})",
        [user_id] + list(update_ids),
    )
    ids = {r['update_id'] for r in cursor.fetchall()}
    cursor.close()
    return ids


def create_update(group_id, user_id, title, content, photo_url=None, is_published=False):
    """Create a new group update."""
    cursor = get_cursor()
    cursor.execute(
        """INSERT INTO group_updates (group_id, user_id, update_title, update_content, photo_url, is_published)
           VALUES (%s, %s, %s, %s, %s, %s)""",
        (group_id, user_id, title, content, photo_url, is_published),
    )
    update_id = cursor.lastrowid
    cursor.close()
    return update_id


def insert_update_images(update_id, photo_urls):
    """Insert images for an update."""
    cursor = get_cursor()
    for url in photo_urls:
        cursor.execute(
            "INSERT INTO group_update_images (update_id, photo_url) VALUES (%s, %s)",
            (update_id, url),
        )
    cursor.close()


def fetch_update_by_id(update_id, group_id):
    """Fetch a single update by ID and group."""
    cursor = get_cursor()
    cursor.execute(
        "SELECT * FROM group_updates WHERE update_id = %s AND group_id = %s",
        (update_id, group_id),
    )
    row = cursor.fetchone()
    cursor.close()
    return row


def delete_update_images(image_ids, update_id):
    """Delete specific images from an update."""
    if not image_ids:
        return
    cursor = get_cursor()
    placeholders = ', '.join(['%s'] * len(image_ids))
    cursor.execute(
        f"DELETE FROM group_update_images WHERE image_id IN ({placeholders}) AND update_id = %s",
        list(image_ids) + [update_id],
    )
    cursor.close()


def get_first_image_url(update_id):
    """Get the first image URL for an update."""
    cursor = get_cursor()
    cursor.execute(
        "SELECT photo_url FROM group_update_images WHERE update_id = %s ORDER BY image_id ASC LIMIT 1",
        (update_id,),
    )
    row = cursor.fetchone()
    cursor.close()
    return row['photo_url'] if row else None


def update_update(update_id, group_id, title, content, photo_url=None, is_published=False):
    """Update a group update."""
    cursor = get_cursor()
    cursor.execute(
        """UPDATE group_updates
           SET update_title = %s, update_content = %s, photo_url = %s, is_published = %s, updated_at = CURRENT_TIMESTAMP
           WHERE update_id = %s AND group_id = %s""",
        (title, content, photo_url, is_published, update_id, group_id),
    )
    cursor.close()


def publish_update(update_id, group_id):
    """Publish a draft update."""
    cursor = get_cursor()
    cursor.execute(
        "UPDATE group_updates SET is_published = TRUE, updated_at = CURRENT_TIMESTAMP WHERE update_id = %s AND group_id = %s",
        (update_id, group_id),
    )
    cursor.close()


def delete_update(update_id, group_id):
    """Delete a group update."""
    cursor = get_cursor()
    cursor.execute(
        "DELETE FROM group_updates WHERE update_id = %s AND group_id = %s",
        (update_id, group_id),
    )
    cursor.close()


def toggle_like(update_id, user_id):
    """Toggle like on an update. Returns (liked: bool, like_count: int)."""
    cursor = get_cursor()
    cursor.execute(
        "SELECT like_id FROM update_likes WHERE update_id = %s AND user_id = %s",
        (update_id, user_id),
    )
    existing = cursor.fetchone()
    if existing:
        cursor.execute(
            "DELETE FROM update_likes WHERE update_id = %s AND user_id = %s",
            (update_id, user_id),
        )
        liked = False
    else:
        cursor.execute(
            "INSERT INTO update_likes (update_id, user_id) VALUES (%s, %s)",
            (update_id, user_id),
        )
        liked = True
    cursor.execute(
        "SELECT COUNT(*) AS count FROM update_likes WHERE update_id = %s",
        (update_id,),
    )
    like_count = cursor.fetchone()['count']
    cursor.close()
    return liked, like_count
