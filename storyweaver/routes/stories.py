import re
from datetime import datetime, timezone

from bson import ObjectId
from flask import (Blueprint, abort, current_app, flash, g, redirect,
                   render_template, request, url_for)

from ..models import Story, count_words
from ..queries import (build_tree, can_view, stories_with_authors,
                       visible_filter, with_author)
from ..schema import GENRES, TEXT_MAX, TEXT_MIN
from ..security import login_required, permission_required

bp = Blueprint("stories", __name__, url_prefix="/stories")



def utcnow():
    return datetime.now(timezone.utc)


def _validate_text(text: str):
    if len(text) < TEXT_MIN:
        return f"Too short — at least {TEXT_MIN} characters."
    if len(text) > TEXT_MAX:
        return f"Too long — at most {TEXT_MAX:,} characters."
    return None


def _get_viewable(story_id: str):
    try:
        oid = ObjectId(story_id)
    except Exception:
        abort(404)
    doc = current_app.db.stories.find_one({"_id": oid})
    if not doc or not can_view(doc, _viewer(), g.perms):
        abort(404)
    return doc


def _viewer():
    return g.user.doc if g.user else None


# ── Explore ───────────────────────────────────────────────────────────────────

@bp.route("/explore")
def explore():
    db = current_app.db
    viewer, perms = _viewer(), g.perms

    q = request.args.get("q", "").strip()
    kind_filter = request.args.get("kind", "opening")
    genre_filter = request.args.get("genre", "")
    sort_by = request.args.get("sort", "newest")
    not_continued = request.args.get("not_continued") == "1"

    match = dict(visible_filter(viewer, perms))
    if kind_filter in ("opening", "continuation", "ending"):
        match["kind"] = kind_filter
    else:
        kind_filter = "all"
    if genre_filter and genre_filter in GENRES:
        match["genre"] = genre_filter
    if not_continued:
        match["stats.continuations"] = 0
    if q:
        escaped = re.escape(q)
        search = {"$or": [
            {"title": {"$regex": escaped, "$options": "i"}},
            {"text": {"$regex": escaped, "$options": "i"}},
            {"tags": {"$regex": escaped, "$options": "i"}},
        ]}
        # visible_filter may already use $or for logged-in viewers, so combine with $and
        match = {"$and": [match, search]}

    sort_map = {
        "newest": [("created_at", -1)],
        "popular": [("stats.likes", -1), ("created_at", -1)],
        "most_branched": [("stats.continuations", -1), ("created_at", -1)],
        "most_read": [("stats.views", -1), ("created_at", -1)],
    }
    if sort_by not in sort_map:
        sort_by = "newest"
    sort = sort_map[sort_by]

    stories = stories_with_authors(db, match, sort)

    return render_template("stories/explore.html",
                           stories=stories, genres=GENRES,
                           q=q, kind_filter=kind_filter, genre_filter=genre_filter,
                           sort_by=sort_by, not_continued=not_continued)


# ── Random opening ────────────────────────────────────────────────────────────

@bp.route("/random")
def random_opening():
    db = current_app.db
    genre = request.args.get("genre", "")
    match = {"kind": "opening", "visibility": "public", "status": "active"}
    if genre and genre in GENRES:
        match["genre"] = genre
    docs = list(db.stories.aggregate([{"$match": match}, {"$sample": {"size": 1}}]))
    if not docs:
        flash("No openings yet. Be the first to write one!", "info")
        return redirect(url_for("stories.write"))
    return redirect(url_for("stories.view", story_id=str(docs[0]["_id"])))


# ── View a passage ────────────────────────────────────────────────────────────

@bp.route("/<story_id>")
def view(story_id: str):
    db = current_app.db
    viewer, perms = _viewer(), g.perms

    node = _get_viewable(story_id)

    # Count a view (not for own passage)
    if not viewer or viewer["_id"] != node["author_id"]:
        db.stories.update_one({"_id": node["_id"]}, {"$inc": {"stats.views": 1}})
        node["stats"]["views"] = node["stats"].get("views", 0) + 1

    # Ancestor path
    path_docs = {d["_id"]: d for d in db.stories.aggregate(with_author(
        [{"$match": {"_id": {"$in": node.get("ancestors", [])}}}]
    ))}
    ancestors = [Story(path_docs[aid]) for aid in node.get("ancestors", [])
                 if aid in path_docs and can_view(path_docs[aid], viewer, perms)]

    # Current passage with author
    node_full_list = list(db.stories.aggregate(with_author([{"$match": {"_id": node["_id"]}}])))
    current = Story(node_full_list[0]) if node_full_list else Story(node)

    # Branches (direct children)
    branch_match = {"$and": [visible_filter(viewer, perms), {"parent_id": node["_id"]}]}
    branches = stories_with_authors(db, branch_match, [("stats.likes", -1), ("created_at", 1)])

    has_any_children = db.stories.count_documents({"parent_id": node["_id"]}) > 0
    siblings = []
    if node.get("parent_id"):
        siblings = stories_with_authors(
            db, {"$and": [visible_filter(viewer, perms),
                          {"parent_id": node["parent_id"], "_id": {"$ne": node["_id"]}}]},
            [("stats.likes", -1), ("created_at", 1)])

    state = {"liked": False, "bookmarked": False, "reported": False}
    if viewer:
        state["liked"] = viewer["_id"] in node.get("liked_by", [])
        state["bookmarked"] = node["_id"] in viewer.get("bookmarks", [])
        state["reported"] = viewer["_id"] in node.get("reported_by", [])

    is_author = bool(viewer and viewer["_id"] == node["author_id"])
    can_continue = "write_stories" in perms and current.can_be_continued

    return render_template("stories/view.html",
                           ancestors=ancestors, story=current,
                           branches=branches, siblings=siblings,
                           liked=state["liked"], saved=state["bookmarked"],
                           reported=state["reported"], can_continue=can_continue,
                           can_moderate="moderate_stories" in perms,
                           is_author=is_author, locked=has_any_children)


# ── Story tree map ────────────────────────────────────────────────────────────

@bp.route("/<story_id>/tree")
def tree(story_id: str):
    db = current_app.db
    viewer, perms = _viewer(), g.perms
    node = _get_viewable(story_id)
    root_id = node.get("root_id", node["_id"])

    by_id = build_tree(db, root_id, viewer, perms)

    root = by_id.get(root_id) or Story(db.stories.find_one({"_id": root_id}) or node)

    return render_template("stories/tree.html",
                           root=root,
                           node_count=len(by_id),
                           current_id=str(node["_id"]))


# ── Write opening ─────────────────────────────────────────────────────────────

@bp.route("/write", methods=["GET", "POST"])
@permission_required("write_stories")
def write():
    db = current_app.db
    form = {"title": "", "text": "", "genre": GENRES[0],
            "tags": "", "visibility": g.user.default_visibility}
    errors = {}

    if request.method == "POST":
        form["title"] = request.form.get("title", "").strip()
        form["text"] = request.form.get("text", "").strip()
        form["genre"] = request.form.get("genre", GENRES[0])
        form["tags"] = request.form.get("tags", "").strip()
        form["visibility"] = request.form.get("visibility", "public")

        if len(form["title"]) < 3:
            errors["title"] = "Title must be at least 3 characters."
        elif len(form["title"]) > 120:
            errors["title"] = "Title must be 120 characters or less."
        if form["genre"] not in GENRES:
            errors["genre"] = "Choose a valid genre."

        text_err = _validate_text(form["text"])
        if text_err:
            errors["text"] = text_err

        if not errors:
            tags = [t.strip()[:30] for t in re.split(r"[,\s]+", form["tags"]) if t.strip()][:8]
            now = utcnow()
            sid = ObjectId()
            db.stories.insert_one({
                "_id": sid,
                "title": form["title"],
                "text": form["text"],
                "kind": "opening",
                "parent_id": None,
                "root_id": sid,
                "ancestors": [],
                "depth": 0,
                "author_id": g.user["_id"],
                "genre": form["genre"],
                "tags": tags,
                "visibility": form["visibility"] if form["visibility"] in ("public", "private") else "public",
                "status": "active",
                "stats": {"continuations": 0, "likes": 0, "views": 0},
                "liked_by": [],
                "reported_by": [],
                "comments": [],
                "word_count": count_words(form["text"]),
                "created_at": now,
                "updated_at": now,
            })
            flash("Your opening is woven in.", "success")
            return redirect(url_for("stories.view", story_id=str(sid)))

    prompts = list(db.prompts.aggregate([{"$sample": {"size": 3}}]))
    return render_template("stories/write.html", form_data=form, errors=errors,
                           genres=GENRES, prompts=prompts)


# ── Continue a story ──────────────────────────────────────────────────────────

@bp.route("/<story_id>/continue", methods=["GET", "POST"])
@permission_required("write_stories")
def continue_story(story_id: str):
    db = current_app.db
    parent = _get_viewable(story_id)

    if parent["kind"] == "ending":
        flash("That branch has an ending. Pick an earlier passage to branch from.", "info")
        return redirect(url_for("stories.view", story_id=story_id))
    if parent["status"] != "active":
        abort(404)

    parent_is_private = parent["visibility"] == "private"
    form = {"text": "", "kind": "continuation",
            "visibility": "private" if parent_is_private else g.user.default_visibility}
    errors = {}

    if request.method == "POST":
        form["text"] = request.form.get("text", "").strip()
        form["kind"] = request.form.get("kind", "continuation")
        form["visibility"] = request.form.get("visibility", "public")

        if form["kind"] not in ("continuation", "ending"):
            form["kind"] = "continuation"
        if form["visibility"] not in ("public", "private") or parent_is_private:
            form["visibility"] = "private" if parent_is_private else "public"

        err = _validate_text(form["text"])
        if err:
            errors["text"] = err
        else:
            sid, now = ObjectId(), utcnow()
            db.stories.insert_one({
                "_id": sid,
                "title": parent["title"],
                "text": form["text"],
                "kind": form["kind"],
                "parent_id": parent["_id"],
                "root_id": parent["root_id"],
                "ancestors": parent["ancestors"] + [parent["_id"]],
                "depth": parent["depth"] + 1,
                "author_id": g.user["_id"],
                "genre": parent["genre"],
                "tags": parent.get("tags", []),
                "visibility": form["visibility"],
                "status": "active",
                "stats": {"continuations": 0, "likes": 0, "views": 0},
                "liked_by": [],
                "reported_by": [],
                "comments": [],
                "word_count": count_words(form["text"]),
                "created_at": now,
                "updated_at": now,
            })
            if form["visibility"] == "public":
                db.stories.update_one(
                    {"_id": parent["_id"]},
                    {"$inc": {"stats.continuations": 1}}
                )
            flash(
                "Ending written. That's one finished version of this story."
                if form["kind"] == "ending"
                else "Your passage is woven in.",
                "success"
            )
            return redirect(url_for("stories.view", story_id=str(sid)))

    # Path above the passage being continued
    path = stories_with_authors(db, {"_id": {"$in": parent["ancestors"] + [parent["_id"]]}},
                                [("depth", 1)])
    path = [s for s in path if can_view(s.doc, _viewer(), g.perms)]
    parent_story = path.pop() if path and path[-1].doc["_id"] == parent["_id"] else Story(parent)

    return render_template("stories/continue.html",
                           parent=parent_story, ancestors=path, form_data=form,
                           errors=errors, parent_is_private=parent_is_private)


# ── Edit a passage ────────────────────────────────────────────────────────────

@bp.route("/<story_id>/edit", methods=["GET", "POST"])
@permission_required("edit_own")
def edit(story_id: str):
    db = current_app.db
    doc = _get_viewable(story_id)

    if doc["author_id"] != g.user["_id"] and "moderate_stories" not in g.perms:
        abort(403)

    # Locked once continued
    has_children = db.stories.count_documents({"parent_id": doc["_id"]}) > 0
    if has_children and "moderate_stories" not in g.perms:
        flash("This passage has been continued by others and cannot be edited.", "error")
        return redirect(url_for("stories.view", story_id=story_id))

    tags_str = ", ".join(doc.get("tags", []))
    form = {"title": doc.get("title", ""), "text": doc.get("text", ""),
            "genre": doc.get("genre", ""), "tags": tags_str,
            "visibility": doc.get("visibility", "public")}
    errors = {}

    if request.method == "POST":
        form["text"] = request.form.get("text", "").strip()
        form["visibility"] = request.form.get("visibility", "public")

        if doc["kind"] == "opening":
            form["title"] = request.form.get("title", "").strip()
            form["genre"] = request.form.get("genre", "")
            form["tags"] = request.form.get("tags", "").strip()
            if not 3 <= len(form["title"]) <= 120:
                errors["title"] = "Title must be 3–120 characters."

        err = _validate_text(form["text"])
        if err:
            errors["text"] = err

        if not errors:
            update = {
                "text": form["text"],
                "word_count": count_words(form["text"]),
                "updated_at": utcnow(),
            }
            if doc["kind"] == "opening":
                tags = [t.strip()[:30] for t in re.split(r"[,\s]+", form["tags"]) if t.strip()][:8]
                update.update({
                    "title": form["title"],
                    "genre": form["genre"] if form["genre"] in GENRES else doc["genre"],
                    "tags": tags,
                })
            old_vis = doc["visibility"]
            new_vis = form["visibility"] if form["visibility"] in ("public", "private") else old_vis
            update["visibility"] = new_vis

            if old_vis != new_vis:
                # Adjust parent continuations counter
                if doc.get("parent_id"):
                    delta = 1 if new_vis == "public" else -1
                    db.stories.update_one({"_id": doc["parent_id"]},
                                          {"$inc": {"stats.continuations": delta}})
                # Force children of a private passage to be private
                if new_vis == "private":
                    db.stories.update_many(
                        {"ancestors": doc["_id"]},
                        {"$set": {"visibility": "private", "stats.continuations": 0,
                                  "updated_at": utcnow()}}
                    )
                    update["stats.continuations"] = 0

            db.stories.update_one({"_id": doc["_id"]}, {"$set": update})
            flash("Passage updated.", "success")
            return redirect(url_for("stories.view", story_id=story_id))

    return render_template("stories/edit.html", story=Story(doc), form_data=form,
                           errors=errors, genres=GENRES, locked=has_children)


# ── Delete ────────────────────────────────────────────────────────────────────

@bp.route("/<story_id>/delete", methods=["POST"])
@permission_required("edit_own")
def delete(story_id: str):
    db = current_app.db
    doc = _get_viewable(story_id)
    if doc["author_id"] != g.user["_id"] and "moderate_stories" not in g.perms:
        abort(403)
    if db.stories.count_documents({"parent_id": doc["_id"]}) > 0:
        flash("Cannot delete a passage that has been continued.", "error")
        return redirect(url_for("stories.view", story_id=story_id))
    if doc.get("parent_id") and doc["visibility"] == "public":
        db.stories.update_one({"_id": doc["parent_id"]},
                              {"$inc": {"stats.continuations": -1}})
    db.stories.delete_one({"_id": doc["_id"]})
    flash("Passage deleted.", "info")
    parent_id = doc.get("parent_id")
    if parent_id:
        return redirect(url_for("stories.view", story_id=str(parent_id)))
    return redirect(url_for("stories.explore"))


# ── Comment ───────────────────────────────────────────────────────────────────

@bp.route("/<story_id>/comment", methods=["POST"])
@permission_required("comment")
def comment(story_id: str):
    doc = _get_viewable(story_id)
    text = request.form.get("text", "").strip()
    if not 1 <= len(text) <= 1000:
        flash("Comments must be 1–1000 characters.", "error")
    else:
        current_app.db.stories.update_one(
            {"_id": doc["_id"]},
            {"$push": {"comments": {
                "_id": ObjectId(),
                "author_id": g.user["_id"],
                "username": g.user["username"],
                "text": text,
                "created_at": utcnow(),
            }}}
        )
    return redirect(url_for("stories.view", story_id=story_id) + "#comments")


# ── Report ────────────────────────────────────────────────────────────────────

@bp.route("/<story_id>/report", methods=["POST"])
@login_required
def report(story_id: str):
    doc = _get_viewable(story_id)
    uid = g.user["_id"]
    if uid not in doc.get("reported_by", []):
        current_app.db.stories.update_one(
            {"_id": doc["_id"]},
            {"$addToSet": {"reported_by": uid}}
        )
        flash("Thank you for your report. A moderator will review it.", "info")
    else:
        flash("You have already reported this passage.", "info")
    return redirect(url_for("stories.view", story_id=story_id))
