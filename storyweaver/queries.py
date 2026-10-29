"""
Reusable aggregation pipeline helpers.
"""
from pymongo import DESCENDING

from .models import Story


# ── Visibility helpers ────────────────────────────────────────────────────────

def visible_filter(user=None, perms=frozenset()):
    """Return a $match-compatible filter for what a viewer is allowed to see.

    Everyone: public + active passages.
    Logged in: also their own passages (private or hidden).
    Moderators: also hidden public passages.
    """
    public = {"visibility": "public", "status": "active"}
    if user is None:
        return public
    ors = [public, {"author_id": user["_id"]}]
    if "moderate_stories" in perms:
        ors.append({"visibility": "public", "status": "hidden"})
    return {"$or": ors}


def can_view(doc, user=None, perms=frozenset()) -> bool:
    if doc is None:
        return False
    if user is not None and doc.get("author_id") == user["_id"]:
        return True
    if doc.get("visibility") != "public":
        return False
    return doc.get("status") == "active" or "moderate_stories" in perms


# ── $lookup helpers ───────────────────────────────────────────────────────────

def with_author(pipeline):
    """Append $lookup+$unwind+$addFields to join author username."""
    return pipeline + [
        {"$lookup": {"from": "users", "localField": "author_id",
                     "foreignField": "_id", "as": "author"}},
        {"$unwind": {"path": "$author", "preserveNullAndEmptyArrays": True}},
        {"$addFields": {"author_name": "$author.username"}},
        {"$project": {"author": 0}},
    ]


def stories_with_authors(db, match_filter, sort=None):
    """Run a find-with-author aggregation and return Story objects."""
    pipeline = [{"$match": match_filter}]
    if sort:
        pipeline.append({"$sort": dict(sort)})
    docs = list(db.stories.aggregate(with_author(pipeline)))
    return [Story(d) for d in docs]


# ── Tree helpers ──────────────────────────────────────────────────────────────

def story_counts_by_root(db, root_ids):
    """Return passage/ending/writer counts keyed by root_id."""
    rows = db.stories.aggregate([
        {"$match": {"root_id": {"$in": list(root_ids)}, "depth": {"$gt": 0},
                    "visibility": "public", "status": "active"}},
        {"$group": {"_id": "$root_id",
                    "passages": {"$sum": 1},
                    "endings": {"$sum": {"$cond": [{"$eq": ["$kind", "ending"]}, 1, 0]}},
                    "writers": {"$addToSet": "$author_id"}}},
    ])
    return {r["_id"]: {"passages": r["passages"], "endings": r["endings"],
                       "writers": len(r["writers"])} for r in rows}


def build_tree(db, root_id, viewer=None, perms=frozenset()):
    """Return every passage in a tree as a list of Story objects, filtered for viewer."""
    filt = dict(visible_filter(viewer, perms))
    filt["root_id"] = root_id
    docs = list(db.stories.aggregate(with_author([{"$match": filt}])))
    # Build a dict by _id for fast lookup
    by_id = {d["_id"]: Story(d) for d in docs}
    return by_id
