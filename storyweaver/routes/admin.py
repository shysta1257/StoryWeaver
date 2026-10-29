"""
Admin panel: hide/unhide stories, manage user roles, view reports.
"""
from flask import (Blueprint, abort, current_app, flash, g, redirect,
                   render_template, request, url_for)
from bson import ObjectId
from datetime import datetime, timezone

from ..security import permission_required

bp = Blueprint("admin", __name__, url_prefix="/admin")


def utcnow():
    return datetime.now(timezone.utc)


@bp.route("/")
@permission_required("moderate_stories")
def index():
    db = current_app.db
    reported = list(db.stories.aggregate([
        {"$match": {"reported_by": {"$exists": True}, "$expr": {"$gt": [{"$size": "$reported_by"}, 0]}}},
        {"$sort": {"created_at": -1}},
        {"$lookup": {"from": "users", "localField": "author_id",
                     "foreignField": "_id", "as": "author"}},
        {"$unwind": {"path": "$author", "preserveNullAndEmptyArrays": True}},
        {"$addFields": {"author_name": "$author.username"}},
        {"$project": {"author": 0}},
    ]))
    hidden = list(db.stories.aggregate([
        {"$match": {"status": "hidden"}},
        {"$sort": {"updated_at": -1}},
        {"$limit": 50},
        {"$lookup": {"from": "users", "localField": "author_id",
                     "foreignField": "_id", "as": "author"}},
        {"$unwind": {"path": "$author", "preserveNullAndEmptyArrays": True}},
        {"$addFields": {"author_name": "$author.username"}},
        {"$project": {"author": 0}},
    ]))
    return render_template("admin/index.html", reported=reported, hidden=hidden)


@bp.route("/story/<story_id>/hide", methods=["POST"])
@permission_required("moderate_stories")
def hide_story(story_id: str):
    try:
        oid = ObjectId(story_id)
    except Exception:
        abort(404)
    current_app.db.stories.update_one(
        {"_id": oid},
        {"$set": {"status": "hidden", "updated_at": utcnow()}}
    )
    flash("Passage hidden.", "info")
    return redirect(request.referrer or url_for("admin.index"))


@bp.route("/story/<story_id>/unhide", methods=["POST"])
@permission_required("moderate_stories")
def unhide_story(story_id: str):
    try:
        oid = ObjectId(story_id)
    except Exception:
        abort(404)
    current_app.db.stories.update_one(
        {"_id": oid},
        {"$set": {"status": "active", "reported_by": [], "updated_at": utcnow()}}
    )
    flash("Passage restored.", "success")
    return redirect(request.referrer or url_for("admin.index"))


@bp.route("/users")
@permission_required("manage_users")
def users():
    db = current_app.db
    all_users = list(db.users.find({}, {"password_hash": 0, "email": 0}).sort("created_at", -1))
    from ..schema import ROLE_NAMES
    return render_template("admin/users.html", users=all_users, role_names=ROLE_NAMES)


@bp.route("/user/<user_id>/role", methods=["POST"])
@permission_required("manage_users")
def set_role(user_id: str):
    try:
        uid = ObjectId(user_id)
    except Exception:
        abort(404)
    # Prevent admin from demoting themselves
    if uid == g.user["_id"]:
        flash("You cannot change your own role.", "error")
        return redirect(url_for("admin.users"))
    role = request.form.get("role")
    from ..schema import ROLE_NAMES
    if role not in ROLE_NAMES:
        flash("Invalid role.", "error")
        return redirect(url_for("admin.users"))
    current_app.db.users.update_one({"_id": uid}, {"$set": {"roles": [role]}})
    flash(f"Role updated to {role}.", "success")
    return redirect(url_for("admin.users"))
