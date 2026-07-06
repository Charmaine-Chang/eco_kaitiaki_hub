import logging
"""Knowledge Hub routes — submit, review, edit, and view knowledge entries."""

import os
import uuid
from flask import render_template, request, redirect, url_for, flash, session, current_app
from werkzeug.utils import secure_filename
from PF_LU_APP.db import get_db, get_cursor
from PF_LU_APP.shared.decorators import roles_required
from PF_LU_APP.constants import ROLE_SUPER_ADMIN, ROLE_COORDINATOR, ROLE_OPERATOR, ROLE_OBSERVER
from . import knowledge_bp
from .knowledge_repository import (
    check_active_member, fetch_entry, fetch_group_name, fetch_published_entries,
    fetch_entry_revisions_count, create_entry, fetch_user_submissions,
    fetch_pending_entries, approve_entry, reject_entry, fetch_approved_entry,
    fetch_categories, get_next_version_number, create_revision, update_entry,
    fetch_entry_featured_status, toggle_featured, fetch_entry_with_author,
    fetch_revisions,
)

ALLOWED_IMAGE_EXTENSIONS = {"png", "jpg", "jpeg", "gif", "webp"}


def _allowed_image_file(filename):
    return "." in filename and filename.rsplit(".", 1)[1].lower() in ALLOWED_IMAGE_EXTENSIONS


def _save_knowledge_image(file_storage):
    if not file_storage or file_storage.filename == "":
        return None
    if not _allowed_image_file(file_storage.filename):
        return None
    original_name = secure_filename(file_storage.filename)
    ext = original_name.rsplit(".", 1)[1].lower()
    unique_name = f"{uuid.uuid4().hex}.{ext}"
    upload_dir = os.path.join(current_app.static_folder, "uploads", "knowledge")
    os.makedirs(upload_dir, exist_ok=True)
    file_storage.save(os.path.join(upload_dir, unique_name))
    return f"uploads/knowledge/{unique_name}"


def _is_group_member():
    return "user_id" in session and session.get("role_id") in (ROLE_COORDINATOR, ROLE_OPERATOR, ROLE_OBSERVER)


def _is_coordinator():
    return "user_id" in session and (
        session.get("role_id") == ROLE_COORDINATOR or session.get("is_super_admin", False)
    )


def _require_group_context():
    if "user_id" not in session:
        flash("Please log in to access the Knowledge Hub.", "warning")
        return None, redirect(url_for("auth.login"))
    gid = session.get("current_group_id")
    if not gid:
        flash("Select a group from My Groups or your dashboard first.", "info")
        return None, redirect(url_for("auth.my_groups"))
    if session.get("is_super_admin"):
        return int(gid), None
    if not check_active_member(session["user_id"], gid):
        flash("You do not have access to this group's Knowledge Hub.", "danger")
        return None, redirect(url_for("main.home"))
    return int(gid), None


# ── Hub List ─────────────────────────────────────────────────────


@knowledge_bp.route("/")
def hub_list():
    gid, redir = _require_group_context()
    if redir:
        return redir
    entries = fetch_published_entries(gid)
    gname = fetch_group_name(gid) or "Group"
    return render_template(
        "knowledge/hub_list.html",
        group_id=gid, group_name=gname, entries=entries, can_edit=_is_coordinator(),
    )


@knowledge_bp.route("/<int:entry_id>")
def entry_detail(entry_id):
    gid, redir = _require_group_context()
    if redir:
        return redir
    entry = fetch_entry(entry_id, gid)
    gname = fetch_group_name(gid) or "Group"
    if not entry:
        flash("Knowledge entry not found.", "danger")
        return redirect(url_for("knowledge.hub_list"))
    if not entry["is_published"] and not _is_coordinator():
        flash("This entry is not published.", "warning")
        return redirect(url_for("knowledge.hub_list"))
    revision_count = fetch_entry_revisions_count(entry_id)
    return render_template(
        "knowledge/entry_detail.html",
        group_id=gid, group_name=gname, entry=entry,
        can_edit=_is_coordinator(), revision_count=revision_count,
    )


@knowledge_bp.route("/<int:entry_id>/edit", methods=["GET", "POST"])
@roles_required(ROLE_SUPER_ADMIN, ROLE_COORDINATOR)
def entry_edit(entry_id):
    gid, redir = _require_group_context()
    if redir:
        return redir

    entry = fetch_entry(entry_id, gid)
    if not entry:
        flash("Knowledge entry not found.", "danger")
        return redirect(url_for("knowledge.hub_list"))
    gname = fetch_group_name(gid) or "Group"

    if request.method == "POST":
        title = (request.form.get("title") or "").strip()
        category = (request.form.get("category") or "").strip()
        content = (request.form.get("content") or "").strip()
        photo_url = (request.form.get("photo_url") or "").strip() or None
        is_featured = bool(request.form.get("is_featured"))
        is_published = bool(request.form.get("is_published"))

        if not title or len(title) > 100:
            flash("Title is required (max 100 characters).", "danger")
        elif not category or len(category) > 20:
            flash("Category is required (max 20 characters).", "danger")
        else:
            try:
                next_v = get_next_version_number(entry_id)
                create_revision(
                    entry_id, next_v, entry["category"], entry["title"], entry["content"],
                    entry["photo_url"], entry["is_featured"], entry["is_published"], session["user_id"],
                )
                update_entry(entry_id, title, category, content, photo_url)
                get_db().commit()
                flash("Knowledge entry updated. Earlier content was saved to version history.", "success")
                return redirect(url_for("knowledge.entry_detail", entry_id=entry_id))
            except Exception as e:
                get_db().rollback()
                flash(f"Could not save changes: {e}", "danger")

    return render_template("knowledge/entry_edit.html", group_id=gid, group_name=gname, entry=entry)


@knowledge_bp.route("/<int:entry_id>/history")
@roles_required(ROLE_SUPER_ADMIN, ROLE_COORDINATOR)
def entry_history(entry_id):
    gid, redir = _require_group_context()
    if redir:
        return redir
    entry = fetch_entry(entry_id, gid)
    if not entry:
        flash("Knowledge entry not found.", "danger")
        return redirect(url_for("knowledge.hub_list"))
    revisions = fetch_revisions(entry_id)
    gname = fetch_group_name(gid) or "Group"
    return render_template(
        "knowledge/entry_history.html",
        group_id=gid, group_name=gname, entry=entry, revisions=revisions,
    )


# ── Submit (any group member) ────────────────────────────────────


@knowledge_bp.route("/submit", methods=["GET", "POST"])
def submit_knowledge():
    if not _is_group_member():
        flash("You must be logged in as a group member to submit knowledge entries.", "danger")
        return redirect(url_for("main.knowledge_hub"))

    categories = fetch_categories()

    if request.method == "POST":
        title = request.form.get("title", "").strip()
        category = request.form.get("category", "").strip()
        if category == "__other__":
            category = request.form.get("category_other", "").strip()
        content = request.form.get("content", "").strip()
        photo_file = request.files.get("photo")

        errors = []
        if not title:
            errors.append("Title is required.")
        if not category:
            errors.append("Category is required.")
        if not content:
            errors.append("Content is required.")
        if photo_file and photo_file.filename and not _allowed_image_file(photo_file.filename):
            errors.append("Image must be PNG, JPG, JPEG, GIF, or WEBP.")

        if errors:
            for err in errors:
                flash(err, "danger")
            return render_template("knowledge/submit_knowledge.html", title=title, category=category, content=content, categories=categories)

        group_id = session.get("current_group_id")
        if not group_id:
            flash("No active group selected. Please select a group first.", "warning")
            return redirect(url_for("main.home"))
        photo_url = _save_knowledge_image(photo_file)
        create_entry(group_id, session["user_id"], category, title, content, photo_url)
        get_db().commit()
        flash("Your knowledge entry has been submitted and is awaiting coordinator approval.", "success")
        return redirect(url_for("main.knowledge_hub"))

    return render_template("knowledge/submit_knowledge.html", categories=categories)


# ── My Submissions ───────────────────────────────────────────────


@knowledge_bp.route("/my-submissions")
def my_submissions():
    if "user_id" not in session:
        flash("Please log in to view your submissions.", "warning")
        return redirect(url_for("auth.login"))
    submissions = fetch_user_submissions(session["user_id"])
    return render_template("knowledge/my_submissions.html", submissions=submissions)


# ── Review Queue (coordinator only) ──────────────────────────────


@knowledge_bp.route("/review")
def review_knowledge():
    if "user_id" not in session:
        flash("Please log in to access knowledge moderation.", "warning")
        return redirect(url_for("auth.login"))
    if not _is_coordinator():
        flash("Access denied. Only Group Coordinators can review knowledge entries.", "danger")
        return redirect(url_for("main.knowledge_hub"))
    entries = fetch_pending_entries()
    return render_template("knowledge/review_knowledge.html", entries=entries)


@knowledge_bp.route("/approve/<int:entry_id>", methods=["POST"])
def approve_knowledge(entry_id):
    if not _is_coordinator():
        flash("Access denied. Only Group Coordinators can approve knowledge entries.", "danger")
        return redirect(url_for("main.knowledge_hub"))
    approve_entry(entry_id)
    get_db().commit()
    flash("Knowledge entry approved and published to the Knowledge Hub.", "success")
    return redirect(url_for("knowledge.review_knowledge"))


@knowledge_bp.route("/reject/<int:entry_id>", methods=["POST"])
def reject_knowledge(entry_id):
    if not _is_coordinator():
        flash("Access denied. Only Group Coordinators can reject knowledge entries.", "danger")
        return redirect(url_for("main.knowledge_hub"))
    reject_entry(entry_id)
    get_db().commit()
    flash("Knowledge entry rejected and will not be published.", "warning")
    return redirect(url_for("knowledge.review_knowledge"))


# ── Edit Knowledge (coordinator only) ────────────────────────────


@knowledge_bp.route("/edit/<int:entry_id>", methods=["GET", "POST"])
def edit_knowledge(entry_id):
    if not _is_coordinator():
        flash("Access denied. Only Group Coordinators can edit knowledge entries.", "danger")
        return redirect(url_for("main.knowledge_hub"))

    entry = fetch_approved_entry(entry_id)
    if not entry:
        flash("Knowledge entry not found or not published.", "danger")
        return redirect(url_for("main.knowledge_hub"))
    categories = fetch_categories()

    if request.method == "POST":
        title = request.form.get("title", "").strip()
        category = request.form.get("category", "").strip()
        if category == "__other__":
            category = request.form.get("category_other", "").strip()
        content = request.form.get("content", "").strip()
        photo_file = request.files.get("photo")

        errors = []
        if not title:
            errors.append("Title is required.")
        if not category:
            errors.append("Category is required.")
        if not content:
            errors.append("Content is required.")
        if photo_file and photo_file.filename and not _allowed_image_file(photo_file.filename):
            errors.append("Image must be PNG, JPG, JPEG, GIF, or WEBP.")

        if errors:
            for err in errors:
                flash(err, "danger")
            return render_template("knowledge/edit_knowledge.html", entry=entry, categories=categories)

        try:
            next_v = get_next_version_number(entry_id)
            create_revision(
                entry_id, next_v, entry["category"], entry["title"], entry["content"],
                entry["photo_url"], entry["is_featured"], entry["is_published"], session["user_id"],
            )
            photo_url = entry["photo_url"]
            if photo_file and photo_file.filename:
                saved_path = _save_knowledge_image(photo_file)
                if saved_path:
                    photo_url = saved_path
            update_entry(entry_id, title, category, content, photo_url)
            get_db().commit()
            flash(f"Knowledge entry updated successfully (Version {next_v + 1} is now live).", "success")
            return redirect(url_for("main.knowledge_hub"))
        except Exception as e:
            logging.exception(f"Error updating knowledge entry: {e}")
            flash("An error occurred while updating the entry.", "danger")
            return render_template("knowledge/edit_knowledge.html", entry=entry, categories=categories)

    return render_template("knowledge/edit_knowledge.html", entry=entry, categories=categories)


# ── Feature Toggle ───────────────────────────────────────────────


@knowledge_bp.route("/feature/<int:entry_id>", methods=["POST"])
def toggle_featured_knowledge(entry_id):
    if not _is_coordinator():
        flash("Access denied. Only Group Coordinators can feature knowledge entries.", "danger")
        return redirect(request.referrer or url_for("main.knowledge_hub"))
    current = fetch_entry_featured_status(entry_id)
    if current is None:
        flash("Knowledge entry not found.", "danger")
        return redirect(request.referrer or url_for("main.knowledge_hub"))
    new_state = not bool(current)
    toggle_featured(entry_id, new_state)
    get_db().commit()
    flash(
        "Knowledge entry marked as featured." if new_state else "Knowledge entry removed from featured section.",
        "success" if new_state else "info",
    )
    return redirect(request.referrer or url_for("main.knowledge_hub"))


# ── Version History ──────────────────────────────────────────────


@knowledge_bp.route("/history/<int:entry_id>")
def view_revisions(entry_id):
    if not _is_group_member():
        flash("You must be a group member to view version history.", "warning")
        return redirect(url_for("main.knowledge_hub"))
    current = fetch_entry_with_author(entry_id)
    if not current:
        flash("Entry not found.", "danger")
        return redirect(url_for("main.knowledge_hub"))
    revisions = fetch_revisions(entry_id)
    return render_template("knowledge/history.html", current=current, revisions=revisions)
