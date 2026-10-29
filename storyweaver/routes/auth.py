import re

from bson import ObjectId
from datetime import datetime, timezone
from flask import (Blueprint, current_app, flash, g, redirect,
                   render_template, request, session, url_for)

from ..security import hash_password, login_user, logout_user, verify_password
from ..models import Story
from ..queries import with_author

bp = Blueprint("auth", __name__, url_prefix="/auth")

USERNAME_RE = re.compile(r"^[a-zA-Z0-9_]{3,20}$")


def _random_story(db):
    docs = list(db.stories.aggregate(with_author([
        {"$match": {"kind": "opening", "visibility": "public", "status": "active"}},
        {"$sample": {"size": 1}},
    ])))
    return Story(docs[0]) if docs else None


def _safe_next(url):
    """Only allow local redirects (blocks //evil.com and backslash tricks)."""
    if url and url.startswith("/") and not url.startswith("//") and "\\" not in url:
        return url
    return None


@bp.route("/register", methods=["GET", "POST"])
def register():
    if g.user:
        return redirect(url_for("home.index"))

    sidebar_story = _random_story(current_app.db)
    errors = {}
    form_data = {}

    if request.method == "POST":
        username = request.form.get("username", "").strip()
        email = request.form.get("email", "").strip().lower()
        password = request.form.get("password", "")
        confirm = request.form.get("confirm", "")
        form_data = {"username": username, "email": email}

        if not USERNAME_RE.match(username):
            errors["username"] = "3–20 letters, numbers or underscores."
        if not re.match(r"[^@]+@[^@]+\.[^@]+", email):
            errors["email"] = "Enter a valid email address."
        if len(password) < 8:
            errors["password"] = "At least 8 characters."
        elif password != confirm:
            errors["confirm"] = "Passwords don't match."

        if not errors:
            db = current_app.db
            if db.users.find_one({"username": {"$regex": f"^{re.escape(username)}$", "$options": "i"}}):
                errors["username"] = "That username is taken."
            elif db.users.find_one({"email": email}):
                errors["email"] = "An account with that email already exists."

        if not errors:
            now = datetime.now(timezone.utc)
            doc = {
                "username": username,
                "email": email,
                "password_hash": hash_password(password),
                "roles": ["writer"],
                "bio": "",
                "bookmarks": [],
                "following": [],
                "followers": [],
                "default_visibility": "public",
                "created_at": now,
            }
            result = current_app.db.users.insert_one(doc)
            doc["_id"] = result.inserted_id
            login_user(doc)
            flash(f"Welcome, {username}! Start writing your first story.", "success")
            return redirect(url_for("home.index"))

    return render_template("auth/register.html", errors=errors, form_data=form_data,
                           sidebar_story=sidebar_story)


@bp.route("/login", methods=["GET", "POST"])
def login():
    if g.user:
        return redirect(url_for("home.index"))

    sidebar_story = _random_story(current_app.db)
    error = None
    form_data = {}
    next_url = _safe_next(request.values.get("next", ""))

    if request.method == "POST":
        identifier = request.form.get("identifier", "").strip()
        form_data = {"identifier": identifier}
        password = request.form.get("password", "")

        db = current_app.db
        doc = db.users.find_one(
            {"$or": [
                {"username": {"$regex": f"^{re.escape(identifier)}$", "$options": "i"}},
                {"email": identifier.lower()},
            ]}
        )

        if not doc or not verify_password(password, doc.get("password_hash", "")):
            error = "Incorrect username/email or password."
        else:
            login_user(doc)
            return redirect(next_url or url_for("home.index"))

    return render_template("auth/login.html", error=error, form_data=form_data,
                           next_url=next_url, sidebar_story=sidebar_story)


@bp.route("/logout", methods=["POST"])
def logout():
    logout_user()
    flash("You have been logged out.", "info")
    return redirect(url_for("home.index"))
