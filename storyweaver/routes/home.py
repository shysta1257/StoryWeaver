from flask import Blueprint, current_app, g, render_template

from ..models import Story
from ..queries import with_author

bp = Blueprint("home", __name__)

PUBLIC = {"visibility": "public", "status": "active"}


@bp.route("/")
def index():
    db = current_app.db

    # Random opening for the hero panel
    hero_docs = list(db.stories.aggregate(with_author([
        {"$match": {"kind": "opening", **PUBLIC}},
        {"$sample": {"size": 1}},
    ])))
    hero = Story(hero_docs[0]) if hero_docs else None

    # Hero continuations sample
    hero_continuations = []
    hero_branch_total = 0
    if hero:
        branch_match = {"parent_id": hero.doc["_id"], **PUBLIC}
        hero_branch_total = db.stories.count_documents(branch_match)
        hero_continuations = [Story(d) for d in db.stories.aggregate(with_author([
            {"$match": branch_match},
            {"$sample": {"size": 3}},
        ]))]

    # Recently continued
    recent = [Story(d) for d in db.stories.aggregate(with_author([
        {"$match": {"depth": {"$gt": 0}, **PUBLIC}},
        {"$sort": {"created_at": -1}},
        {"$limit": 8},
    ]))]

    # Stats
    stats = {
        "openings": db.stories.count_documents({"kind": "opening", **PUBLIC}),
        "passages": db.stories.count_documents(PUBLIC),
        "writers": len(db.stories.distinct("author_id", PUBLIC)),
    }

    waiting_count = 0
    if g.user:
        waiting_count = db.stories.count_documents({
            "author_id": g.user["_id"], "kind": "opening",
            "stats.continuations": 0, **PUBLIC,
        })

    return render_template("home/index.html", hero=hero,
                           hero_continuations=hero_continuations,
                           hero_branch_total=hero_branch_total,
                           recent=recent, stats=stats,
                           waiting_count=waiting_count)
