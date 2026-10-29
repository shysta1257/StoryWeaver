"""
JSON API endpoints for likes, saves, follows (no page reload).
"""
from flask import Blueprint, abort, current_app, g, jsonify, url_for
from bson import ObjectId

from ..queries import can_view
from ..security import login_required

bp = Blueprint("api", __name__, url_prefix="/api")


def _viewable(story_id: str):
    try:
        oid = ObjectId(story_id)
    except Exception:
        abort(404)
    doc = current_app.db.stories.find_one({"_id": oid})
    if not doc or not can_view(doc, g.user.doc if g.user else None, g.perms):
        abort(404)
    return doc


@bp.post("/story/<story_id>/like")
@login_required
def like(story_id: str):
    stories = current_app.db.stories
    doc = _viewable(story_id)
    sid, uid = doc["_id"], g.user["_id"]

    res = stories.update_one(
        {"_id": sid, "liked_by": {"$ne": uid}},
        {"$addToSet": {"liked_by": uid}, "$inc": {"stats.likes": 1}}
    )
    liked = True
    if res.modified_count == 0:
        # Already liked — unlike
        stories.update_one(
            {"_id": sid, "liked_by": uid},
            {"$pull": {"liked_by": uid}, "$inc": {"stats.likes": -1}}
        )
        liked = False

    likes = stories.find_one({"_id": sid}, {"stats.likes": 1})["stats"]["likes"]
    return jsonify(liked=liked, likes=likes)


@bp.post("/story/<story_id>/save")
@login_required
def save(story_id: str):
    doc = _viewable(story_id)
    sid, uid = doc["_id"], g.user["_id"]
    db = current_app.db

    user_doc = db.users.find_one({"_id": uid}, {"bookmarks": 1})
    bookmarks = user_doc.get("bookmarks", [])
    if sid in bookmarks:
        db.users.update_one({"_id": uid}, {"$pull": {"bookmarks": sid}})
        saved = False
    else:
        db.users.update_one({"_id": uid}, {"$addToSet": {"bookmarks": sid}})
        saved = True
    return jsonify(saved=saved)


@bp.post("/user/<username>/follow")
@login_required
def follow(username: str):
    if "follow" not in g.perms:
        abort(403)
    db = current_app.db
    target = db.users.find_one({"username": username}, {"_id": 1, "followers": 1})
    if not target or target["_id"] == g.user["_id"]:
        abort(400)

    uid, tid = g.user["_id"], target["_id"]
    user_doc = db.users.find_one({"_id": uid}, {"following": 1})
    following = tid in user_doc.get("following", [])

    if following:
        db.users.update_one({"_id": uid}, {"$pull": {"following": tid}})
        db.users.update_one({"_id": tid}, {"$pull": {"followers": uid}})
    else:
        db.users.update_one({"_id": uid}, {"$addToSet": {"following": tid}})
        db.users.update_one({"_id": tid}, {"$addToSet": {"followers": uid}})

    count = db.users.find_one({"_id": tid}, {"followers": 1}).get("followers", [])
    return jsonify(following=not following, followers=len(count))


@bp.get("/story/<story_id>/tree.json")
def tree_json(story_id: str):
    """Return the story tree as JSON for the SVG map."""
    from ..queries import build_tree
    db = current_app.db
    viewer = g.user.doc if g.user else None
    perms = g.perms

    try:
        oid = ObjectId(story_id)
    except Exception:
        abort(404)
    node = db.stories.find_one({"_id": oid})
    if not node or not can_view(node, viewer, perms):
        abort(404)

    root_id = node.get("root_id", node["_id"])
    by_id = build_tree(db, root_id, viewer, perms)

    nodes_data = []
    for s in by_id.values():
        nodes_data.append({
            "id": s.id,
            "url": url_for("stories.view", story_id=s.id),
            "parent_id": str(s.doc.get("parent_id")) if s.doc.get("parent_id") else None,
            "depth": s.doc.get("depth", 0),
            "kind": s.doc.get("kind"),
            "author": s.author_name,
            "excerpt": s.excerpt[:80],
            "likes": s.like_count,
        })

    return jsonify({"root_id": str(root_id), "current_id": story_id, "nodes": nodes_data})
