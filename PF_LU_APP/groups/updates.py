"""Group Updates routes — CRUD for group updates with photos, likes, and comments."""

import os
import uuid
from flask import (
    Blueprint, current_app, flash, jsonify, redirect, render_template,
    request, session, url_for,
)
from werkzeug.utils import secure_filename
from PF_LU_APP.db import get_cursor, get_db
from PF_LU_APP.constants import ROLE_SUPER_ADMIN, ROLE_COORDINATOR
from .group_repository import (
    fetch_group_name, check_coordinator_access, fetch_updates_list,
    fetch_update_images_batch, fetch_user_liked_ids, create_update,
    insert_update_images, fetch_update_by_id, fetch_update_images,
    delete_update_images, get_first_image_url, update_update,
    publish_update, delete_update, toggle_like,
    fetch_update_detail, fetch_update_comments, add_comment, delete_comment,
)

updates_bp = Blueprint("updates", __name__)

ALLOWED_EXTENSIONS = {"png", "jpg", "jpeg", "gif"}
MAX_CONTENT_LENGTH = 5 * 1024 * 1024  # 5MB


def allowed_file(filename):
    return "." in filename and filename.rsplit(".", 1)[1].lower() in ALLOWED_EXTENSIONS


def _handle_photo_uploads(uploaded_files):
    """Validate and save uploaded photos. Returns (saved_urls, error_response)."""
    uploaded_files = [f for f in uploaded_files if f.filename != ""]
    if len(uploaded_files) > 4:
        return None, ("You can upload a maximum of 4 photos.", "danger")

    saved_urls = []
    for file in uploaded_files:
        file.seek(0, os.SEEK_END)
        file_length = file.tell()
        file.seek(0, os.SEEK_SET)

        if file_length > MAX_CONTENT_LENGTH:
            return None, (f"File {file.filename} is too large. Maximum size is 5MB.", "danger")

        if file and allowed_file(file.filename):
            ext = file.filename.rsplit(".", 1)[1].lower()
            unique_filename = f"{uuid.uuid4().hex}.{ext}"
            upload_folder = os.path.join(current_app.root_path, "static", "uploads", "updates")
            os.makedirs(upload_folder, exist_ok=True)
            file.save(os.path.join(upload_folder, unique_filename))
            saved_urls.append(f"/static/uploads/updates/{unique_filename}")
        else:
            return None, ("Unsupported file type. Allowed: png, jpg, jpeg, gif.", "danger")

    return saved_urls, None


# ── Updates List ─────────────────────────────────────────────────


@updates_bp.route("/<int:group_id>/updates")
def updates_list(group_id):
    if "user_id" not in session:
        return redirect(url_for("auth.login"))

    user_id = session["user_id"]
    is_super_admin = session.get("is_super_admin", False)
    is_coordinator = is_super_admin or check_coordinator_access(user_id, group_id, is_super_admin)

    if not is_super_admin:
        from .group_repository import fetch_membership_status
        status = fetch_membership_status(user_id, group_id)
        if status != 'active':
            flash("You do not have access to this group's updates.", "danger")
            return redirect(url_for("main.home"))

    gname = fetch_group_name(group_id)
    if not gname:
        return redirect(url_for("main.home"))

    updates = fetch_updates_list(group_id, include_drafts=is_coordinator)

    images_map = {}
    liked_ids = set()
    if updates:
        update_ids = [u['update_id'] for u in updates]
        images_map = fetch_update_images_batch(update_ids)
        liked_ids = fetch_user_liked_ids(user_id, update_ids)

    for u in updates:
        u['images'] = images_map.get(u['update_id'], [])

    return render_template(
        "groups/updates_list.html",
        updates=updates, group_id=group_id, group_name=gname,
        is_coordinator=is_coordinator, user_liked_ids=liked_ids,
    )


# ── Create Update ────────────────────────────────────────────────


@updates_bp.route("/<int:group_id>/updates/create", methods=["GET", "POST"])
def create(group_id):
    if "user_id" not in session:
        return redirect(url_for("auth.login"))

    user_id = session["user_id"]
    is_super_admin = session.get("is_super_admin", False)
    if not check_coordinator_access(user_id, group_id, is_super_admin):
        flash("Access denied. Only Group Coordinators can create updates.", "danger")
        return redirect(url_for("updates.updates_list", group_id=group_id))

    if request.method == "POST":
        title = request.form.get("update_title")
        content = request.form.get("update_content")
        action = request.form.get("action")

        if not title or not content:
            flash("Title and content are required.", "danger")
            return render_template("groups/update_form.html", group_id=group_id, update=None)

        saved_urls, error = _handle_photo_uploads(request.files.getlist("photos"))
        if error:
            flash(*error)
            return render_template("groups/update_form.html", group_id=group_id, update=None)

        is_published = action == "publish"
        legacy_photo = saved_urls[0] if saved_urls else None
        update_id = create_update(group_id, user_id, title, content, legacy_photo, is_published)
        if saved_urls:
            insert_update_images(update_id, saved_urls)
        get_db().commit()

        flash("Update published successfully." if is_published else "Draft saved successfully.", "success")
        return redirect(url_for("updates.updates_list", group_id=group_id))

    return render_template("groups/update_form.html", group_id=group_id, update=None, update_images=[])


# ── Edit Update ──────────────────────────────────────────────────


@updates_bp.route("/<int:group_id>/updates/<int:update_id>/edit", methods=["GET", "POST"])
def edit_update(group_id, update_id):
    if "user_id" not in session:
        return redirect(url_for("auth.login"))

    user_id = session["user_id"]
    is_super_admin = session.get("is_super_admin", False)
    if not check_coordinator_access(user_id, group_id, is_super_admin):
        flash("Access denied. Only Group Coordinators can edit updates.", "danger")
        return redirect(url_for("updates.updates_list", group_id=group_id))

    update = fetch_update_by_id(update_id, group_id)
    if not update:
        flash("Update not found.", "danger")
        return redirect(url_for("updates.updates_list", group_id=group_id))

    if request.method == "POST":
        title = request.form.get("update_title")
        content = request.form.get("update_content")
        action = request.form.get("action")
        current_images = fetch_update_images(update_id)

        if not title or not content:
            flash("Title and content are required.", "danger")
            return render_template("groups/update_form.html", group_id=group_id, update=update, update_images=current_images)

        delete_image_ids = [int(x) for x in request.form.getlist("delete_images")]
        saved_urls, error = _handle_photo_uploads(request.files.getlist("photos"))
        if error:
            flash(*error)
            return render_template("groups/update_form.html", group_id=group_id, update=update, update_images=current_images)

        new_total = len(current_images) - len(delete_image_ids) + len(saved_urls)
        if new_total > 4:
            flash("An update can have a maximum of 4 photos.", "danger")
            return render_template("groups/update_form.html", group_id=group_id, update=update, update_images=current_images)

        if delete_image_ids:
            delete_update_images(delete_image_ids, update_id)
        if saved_urls:
            insert_update_images(update_id, saved_urls)

        photo_url = get_first_image_url(update_id)
        is_published = action == "publish"
        update_update(update_id, group_id, title, content, photo_url, is_published)
        get_db().commit()

        flash("Update published successfully." if is_published else "Draft saved successfully.", "success")
        return redirect(url_for("updates.updates_list", group_id=group_id))

    update_images = fetch_update_images(update_id)
    return render_template("groups/update_form.html", group_id=group_id, update=update, update_images=update_images)


# ── Manage Updates ───────────────────────────────────────────────


@updates_bp.route("/<int:group_id>/updates/manage")
def manage_updates(group_id):
    if "user_id" not in session:
        return redirect(url_for("auth.login"))

    user_id = session["user_id"]
    is_super_admin = session.get("is_super_admin", False)
    if not check_coordinator_access(user_id, group_id, is_super_admin):
        flash("Access denied. Only Group Coordinators can manage updates.", "danger")
        return redirect(url_for("updates.updates_list", group_id=group_id))

    gname = fetch_group_name(group_id)
    if not gname:
        return redirect(url_for("main.home"))

    updates = fetch_updates_list(group_id, include_drafts=True)
    images_map = {}
    liked_ids = set()
    if updates:
        update_ids = [u['update_id'] for u in updates]
        images_map = fetch_update_images_batch(update_ids)
        liked_ids = fetch_user_liked_ids(user_id, update_ids)

    for u in updates:
        u['images'] = images_map.get(u['update_id'], [])

    return render_template(
        "groups/manage_updates.html",
        updates=updates, group_id=group_id, group_name=gname,
        is_coordinator=True, user_liked_ids=liked_ids,
    )


# ── Publish / Delete ─────────────────────────────────────────────


@updates_bp.route("/<int:group_id>/updates/<int:update_id>/publish", methods=["POST"])
def publish_draft(group_id, update_id):
    if "user_id" not in session:
        return redirect(url_for("auth.login"))
    user_id = session["user_id"]
    is_super_admin = session.get("is_super_admin", False)
    if not check_coordinator_access(user_id, group_id, is_super_admin):
        flash("Access denied. Only Group Coordinators can publish updates.", "danger")
        return redirect(url_for("updates.updates_list", group_id=group_id))

    publish_update(update_id, group_id)
    get_db().commit()
    flash("Update published successfully.", "success")
    return redirect(url_for("updates.manage_updates", group_id=group_id))


@updates_bp.route("/<int:group_id>/updates/<int:update_id>/delete", methods=["POST"])
def delete_update_route(group_id, update_id):
    if "user_id" not in session:
        return redirect(url_for("auth.login"))
    user_id = session["user_id"]
    is_super_admin = session.get("is_super_admin", False)
    if not check_coordinator_access(user_id, group_id, is_super_admin):
        flash("Access denied. Only Group Coordinators can delete updates.", "danger")
        return redirect(url_for("updates.updates_list", group_id=group_id))

    delete_update(update_id, group_id)
    get_db().commit()
    flash("Update deleted successfully.", "success")
    return redirect(url_for("updates.updates_list", group_id=group_id))


# ── Like Toggle ──────────────────────────────────────────────────


@updates_bp.route("/<int:group_id>/updates/<int:update_id>/like", methods=["POST"])
def toggle_like_route(group_id, update_id):
    if "user_id" not in session:
        if request.headers.get("X-Requested-With") == "XMLHttpRequest":
            return jsonify({"error": "Not logged in"}), 401
        return redirect(url_for("auth.login"))

    liked, like_count = toggle_like(update_id, session["user_id"])
    get_db().commit()

    if request.headers.get("X-Requested-With") == "XMLHttpRequest":
        return jsonify({"liked": liked, "like_count": like_count})

    return redirect(url_for("updates.updates_list", group_id=group_id))


# ── Group Update Detail (from groups/routes.py) ──────────────────

@updates_bp.route("/<int:group_id>/updates/<int:update_id>")
def group_update_detail(group_id, update_id):
    if "user_id" not in session:
        return redirect(url_for("auth.login"))

    user_id = session["user_id"]
    entry = fetch_update_detail(update_id, group_id)
    if not entry:
        flash("Update not found.", "danger")
        return redirect(url_for("updates.updates_list", group_id=group_id))

    images = fetch_update_images(update_id)
    user_has_liked = bool(fetch_user_liked_ids(user_id, [update_id]))
    comments = fetch_update_comments(update_id)
    is_super_admin = session.get("is_super_admin", False)
    can_delete_comments = is_super_admin or check_coordinator_access(user_id, group_id, is_super_admin)

    gname = fetch_group_name(group_id) or "Group"
    return render_template(
        "groups/group_update_detail.html",
        update=entry, group_id=group_id, group_name=gname,
        images=images, comments=comments, user_has_liked=user_has_liked,
        can_delete_comments=can_delete_comments,
    )


# ── Add / Delete Comment ─────────────────────────────────────────

@updates_bp.route("/<int:group_id>/updates/<int:update_id>/comment", methods=["POST"])
def add_group_update_comment(group_id, update_id):
    if "user_id" not in session:
        return redirect(url_for("auth.login"))

    if not check_update_exists(update_id, group_id):
        flash("Update not found.", "danger")
        return redirect(url_for("updates.updates_list", group_id=group_id))

    content = request.form.get("comment_content", "").strip()
    if content:
        add_comment(update_id, session["user_id"], content)
        get_db().commit()
        flash("Comment added.", "success")

    return redirect(url_for("updates.group_update_detail", group_id=group_id, update_id=update_id))


@updates_bp.route("/<int:group_id>/updates/<int:update_id>/comment/<int:comment_id>/delete", methods=["POST"])
def delete_group_update_comment(group_id, update_id, comment_id):
    if "user_id" not in session:
        return redirect(url_for("auth.login"))

    deleted = delete_comment(comment_id, update_id, group_id)
    if deleted:
        get_db().commit()
        flash("Comment deleted.", "success")
    else:
        flash("Could not delete comment.", "danger")

    return redirect(url_for("updates.group_update_detail", group_id=group_id, update_id=update_id))


def check_update_exists(update_id, group_id):
    """Check if a published update exists."""
    from .group_repository import check_update_exists as _check
    return _check(update_id, group_id)
