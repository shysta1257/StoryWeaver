from flask import (Blueprint, abort, current_app, flash, g, redirect,
                   render_template, request, url_for)
from bson import ObjectId

from ..models import Story
from ..queries import can_view, stories_with_authors, visible_filter
from ..security import login_required

bp = Blueprint("users", __name__)


@bp.route("/user/<username>")
def profile(username: str):
    db = current_app.db
    user_doc = db.users.find_one({"username": username}, {"password_hash": 0, "email": 0})
    if not user_doc:
        abort(404)

    viewer = g.user.doc if g.user else None
    perms = g.perms

    # Their public stories
    match = {"$and": [visible_filter(viewer, perms), {"author_id": user_doc["_id"]}]}
    stories = stories_with_authors(db, match, [("created_at", -1)])

    # Follow state
    is_following = bool(viewer and user_doc["_id"] in viewer.get("following", []))
    is_self = bool(viewer and viewer["_id"] == user_doc["_id"])

    # Writing stats
    writing_stats = list(db.stories.aggregate([
        {"$match": {"author_id": user_doc["_id"], "visibility": "public", "status": "active"}},
        {"$group": {
            "_id": None,
            "total_passages": {"$sum": 1},
            "total_likes": {"$sum": "$stats.likes"},
            "total_views": {"$sum": "$stats.views"},
            "openings": {"$sum": {"$cond": [{"$eq": ["$kind", "opening"]}, 1, 0]}},
            "continuations": {"$sum": {"$cond": [{"$eq": ["$kind", "continuation"]}, 1, 0]}},
            "endings": {"$sum": {"$cond": [{"$eq": ["$kind", "ending"]}, 1, 0]}},
        }},
    ]))
    stats = {"openings": 0, "continuations": 0, "endings": 0, "total_likes": 0}
    if writing_stats:
        stats.update({k: writing_stats[0][k] for k in stats})
    stats["followers"] = len(user_doc.get("followers", []))
    stats["following"] = len(user_doc.get("following", []))

    return render_template("users/profile.html",
                           profile_user=user_doc,
                           stories=stories,
                           is_following=is_following,
                           is_self=is_self,
                           stats=stats)


@bp.route("/user/<username>/follow", methods=["POST"])
@login_required
def follow(username: str):
    if "follow" not in g.perms:
        abort(403)
    db = current_app.db
    target = db.users.find_one({"username": username}, {"_id": 1})
    if not target:
        abort(404)
    if target["_id"] == g.user["_id"]:
        flash("You can't follow yourself.", "error")
        return redirect(url_for("users.profile", username=username))

    uid = g.user["_id"]
    tid = target["_id"]
    already = tid in g.user.doc.get("following", [])
    if already:
        db.users.update_one({"_id": uid}, {"$pull": {"following": tid}})
        db.users.update_one({"_id": tid}, {"$pull": {"followers": uid}})
    else:
        db.users.update_one({"_id": uid}, {"$addToSet": {"following": tid}})
        db.users.update_one({"_id": tid}, {"$addToSet": {"followers": uid}})
    return redirect(url_for("users.profile", username=username))


@bp.route("/dashboard")
@login_required
def dashboard():
    db = current_app.db
    user = g.user

    # Own stories
    my_stories = stories_with_authors(
        db, {"author_id": user["_id"]}, [("created_at", -1)]
    )

    # Bookmarks
    bookmarks = []
    if user.doc.get("bookmarks"):
        bookmark_docs = list(db.stories.aggregate([
            {"$match": {"_id": {"$in": user.doc["bookmarks"]}}},
            {"$lookup": {"from": "users", "localField": "author_id",
                         "foreignField": "_id", "as": "author"}},
            {"$unwind": {"path": "$author", "preserveNullAndEmptyArrays": True}},
            {"$addFields": {"author_name": "$author.username"}},
            {"$project": {"author": 0}},
        ]))
        bookmarks = [Story(d) for d in bookmark_docs if can_view(d, user.doc, g.perms)]

    # Activity: recently continued by people I follow
    following_ids = user.doc.get("following", [])
    feed = []
    if following_ids:
        feed_docs = list(db.stories.aggregate([
            {"$match": {"author_id": {"$in": following_ids},
                        "visibility": "public", "status": "active",
                        "depth": {"$gt": 0}}},
            {"$sort": {"created_at": -1}},
            {"$limit": 10},
            {"$lookup": {"from": "users", "localField": "author_id",
                         "foreignField": "_id", "as": "author"}},
            {"$unwind": {"path": "$author", "preserveNullAndEmptyArrays": True}},
            {"$addFields": {"author_name": "$author.username"}},
            {"$project": {"author": 0}},
        ]))
        feed = [Story(d) for d in feed_docs]

    # Waiting for continuation — my openings with 0 continuations
    waiting = [s for s in my_stories
               if s.branch_count == 0 and s.is_public and s.can_be_continued]

    tab = request.args.get("tab", "mine")
    if tab not in ("mine", "bookmarks", "feed", "waiting"):
        tab = "mine"

    return render_template("users/dashboard.html",
                           tab=tab,
                           my_stories=my_stories,
                           bookmarks=bookmarks,
                           feed=feed,
                           waiting=waiting)


@bp.route("/settings", methods=["GET", "POST"])
@login_required
def settings():
    db = current_app.db
    user = g.user
    errors = {}
    form = {
        "bio": user.doc.get("bio", ""),
        "default_visibility": user.doc.get("default_visibility", "public"),
    }

    if request.method == "POST":
        form["bio"] = request.form.get("bio", "").strip()[:300]
        form["default_visibility"] = request.form.get("default_visibility", "public")
        if form["default_visibility"] not in ("public", "private"):
            form["default_visibility"] = "public"

        if not errors:
            db.users.update_one(
                {"_id": user["_id"]},
                {"$set": {"bio": form["bio"], "default_visibility": form["default_visibility"]}}
            )
            flash("Settings saved.", "success")
            return redirect(url_for("users.settings"))

    return render_template("users/settings.html", form=form, errors=errors)
