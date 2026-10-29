"""
Analytics: linear regression (opening length → continuations) and k-means clustering of writers.
"""
import math

from flask import Blueprint, current_app, render_template

from ..schema import GENRES

bp = Blueprint("insights", __name__)

PUBLIC = {"visibility": "public", "status": "active"}


def linear_regression(db):
    """Least squares y = m*x + c, sums computed by MongoDB."""
    per_root = [
        {"$match": PUBLIC},
        {"$group": {
            "_id": "$root_id",
            "x": {"$max": {"$cond": [{"$eq": ["$depth", 0]}, "$word_count", 0]}},
            "y": {"$sum": {"$cond": [{"$gt": ["$depth", 0]}, 1, 0]}},
        }},
        {"$match": {"x": {"$gt": 0}}},
    ]
    sums = list(db.stories.aggregate(per_root + [
        {"$group": {
            "_id": None,
            "n": {"$sum": 1},
            "sum_x": {"$sum": "$x"},
            "sum_y": {"$sum": "$y"},
            "sum_xy": {"$sum": {"$multiply": ["$x", "$y"]}},
            "sum_xx": {"$sum": {"$multiply": ["$x", "$x"]}},
            "sum_yy": {"$sum": {"$multiply": ["$y", "$y"]}},
        }},
    ]))
    if not sums or sums[0]["n"] < 3:
        return None
    s = sums[0]
    n = s["n"]
    denom = n * s["sum_xx"] - s["sum_x"] ** 2
    if denom == 0:
        return None
    slope = (n * s["sum_xy"] - s["sum_x"] * s["sum_y"]) / denom
    intercept = (s["sum_y"] - slope * s["sum_x"]) / n
    r_den = math.sqrt(denom * (n * s["sum_yy"] - s["sum_y"] ** 2))
    r = (n * s["sum_xy"] - s["sum_x"] * s["sum_y"]) / r_den if r_den else 0
    points = [(d["x"], d["y"]) for d in db.stories.aggregate(per_root)]
    return {
        "n": n, "slope": slope, "intercept": intercept,
        "r": r, "r2": r * r,
        "x_mean": s["sum_x"] / n, "y_mean": s["sum_y"] / n,
        "chart": _regression_chart(points, slope, intercept),
    }


def _regression_chart(points, slope, intercept):
    """Map data to SVG coordinates: plot area x 50–460, y 20–220."""
    x_max = max(p[0] for p in points) or 1
    y_max = max(max(p[1] for p in points), slope * x_max + intercept, 1)

    def sx(x):
        return 50 + 410 * x / x_max

    def sy(y):
        return 220 - 200 * max(0, min(y, y_max)) / y_max

    return {
        "x_max": x_max, "y_max": y_max,
        "dots": [{"cx": sx(x), "cy": sy(y), "x": x, "y": y} for x, y in points],
        "line": {"x1": sx(0), "y1": sy(intercept),
                 "x2": sx(x_max), "y2": sy(slope * x_max + intercept)},
    }


def writer_clusters(db, k=3, iterations=20):
    """k-means on (openings written, continuations written) per writer."""
    rows = list(db.stories.aggregate([
        {"$match": PUBLIC},
        {"$group": {
            "_id": "$author_id",
            "openings": {"$sum": {"$cond": [{"$eq": ["$kind", "opening"]}, 1, 0]}},
            "continues": {"$sum": {"$cond": [{"$gt": ["$depth", 0]}, 1, 0]}},
        }},
        {"$lookup": {"from": "users", "localField": "_id",
                     "foreignField": "_id", "as": "user"}},
        {"$unwind": "$user"},
        {"$project": {"username": "$user.username", "openings": 1, "continues": 1}},
    ]))
    if len(rows) < k:
        return None

    points = [(r["openings"], r["continues"]) for r in rows]
    ordered = sorted(points, key=lambda p: p[0] + p[1])
    centroids = [ordered[round(i * (len(ordered) - 1) / (k - 1))] for i in range(k)]
    centroids = [tuple(map(float, c)) for c in centroids]

    labels = [0] * len(points)
    for _ in range(iterations):
        labels = [min(range(k),
                      key=lambda c: (points[i][0] - centroids[c][0]) ** 2
                                   + (points[i][1] - centroids[c][1]) ** 2)
                  for i in range(len(points))]
        new = []
        for c in range(k):
            members = [p for p, lab in zip(points, labels) if lab == c]
            new.append((
                sum(p[0] for p in members) / len(members) if members else centroids[c][0],
                sum(p[1] for p in members) / len(members) if members else centroids[c][1],
            ))
        if new == centroids:
            break
        centroids = new

    groups = []
    for c in range(k):
        cx, cy = centroids[c]
        if cx >= cy:
            name, blurb = "Spark-starters", "Write more openings than continuations"
        elif cx < 0.5:
            name, blurb = "Weavers", "Mostly carry other people's stories forward"
        else:
            name, blurb = "All-rounders", "Start stories and continue them"
        members = [rows[i]["username"] for i, lab in enumerate(labels) if lab == c]
        groups.append({"name": name, "blurb": blurb,
                       "centroid": (cx, cy), "members": members})

    # Merge clusters that ended up with the same name
    merged = {}
    for gr in groups:
        if gr["members"]:
            m = merged.setdefault(gr["name"], {**gr, "members": []})
            m["members"] += gr["members"]

    # Scale to SVG plot area: x 40–280, y 20–220
    x_max = max(p[0] for p in points) or 1
    y_max = max(p[1] for p in points) or 1
    return {
        "groups": list(merged.values()),
        "x_max": x_max, "y_max": y_max,
        "points": [{"u": rows[i]["username"], "x": rows[i]["openings"],
                    "y": rows[i]["continues"], "c": labels[i],
                    "cx": 40 + 240 * rows[i]["openings"] / x_max,
                    "cy": 220 - 200 * rows[i]["continues"] / y_max}
                   for i in range(len(rows))],
    }


@bp.route("/insights")
def insights():
    db = current_app.db
    reg = linear_regression(db)
    clusters = writer_clusters(db)

    # Genre breakdown
    genre_counts = list(db.stories.aggregate([
        {"$match": {**PUBLIC, "kind": "opening"}},
        {"$group": {"_id": "$genre", "count": {"$sum": 1}}},
        {"$sort": {"count": -1}},
    ]))

    # Top writers by likes
    top_writers = list(db.stories.aggregate([
        {"$match": PUBLIC},
        {"$group": {"_id": "$author_id",
                    "total_likes": {"$sum": "$stats.likes"},
                    "passages": {"$sum": 1}}},
        {"$sort": {"total_likes": -1}},
        {"$limit": 10},
        {"$lookup": {"from": "users", "localField": "_id",
                     "foreignField": "_id", "as": "user"}},
        {"$unwind": "$user"},
        {"$project": {"username": "$user.username",
                      "total_likes": 1, "passages": 1}},
    ]))

    return render_template("insights/insights.html",
                           regression=reg,
                           clusters=clusters,
                           genre_counts=genre_counts,
                           top_writers=top_writers)
