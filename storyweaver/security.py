"""
Security helpers: CSRF, session management, RBAC, login_required.
"""
import secrets
from functools import wraps

from flask import (abort, current_app, g, redirect, request,
                   session, url_for)
from werkzeug.security import check_password_hash, generate_password_hash

from .models import User
from .schema import PUBLIC_PERMISSIONS


# ── Password helpers ──────────────────────────────────────────────────────────

def hash_password(plain: str) -> str:
    return generate_password_hash(plain)


def verify_password(plain: str, hashed: str) -> bool:
    return check_password_hash(hashed, plain)


# ── CSRF ──────────────────────────────────────────────────────────────────────

def csrf_token() -> str:
    if "csrf" not in session:
        session["csrf"] = secrets.token_urlsafe(32)
    return session["csrf"]


# ── Session helpers ───────────────────────────────────────────────────────────

def login_user(user_doc):
    session.clear()
    session["uid"] = str(user_doc["_id"])
    session.permanent = True


def logout_user():
    session.clear()


# ── RBAC aggregation pipeline ─────────────────────────────────────────────────

def permissions_pipeline(user_id):
    return [
        {"$match": {"_id": user_id}},
        {"$lookup": {"from": "roles", "localField": "roles",
                     "foreignField": "name", "as": "userRoles"}},
        {"$unwind": "$userRoles"},
        {"$unwind": "$userRoles.permissions"},
        {"$group": {"_id": "$_id",
                    "permissions": {"$addToSet": "$userRoles.permissions"}}},
    ]


def load_permissions(db, user_id) -> set:
    result = list(db.users.aggregate(permissions_pipeline(user_id)))
    return set(result[0]["permissions"]) if result else set()


# ── Decorators ────────────────────────────────────────────────────────────────

def login_required(view):
    @wraps(view)
    def wrapped(*args, **kwargs):
        if g.user is None:
            return redirect(url_for("auth.login", next=request.path))
        return view(*args, **kwargs)
    return wrapped


def permission_required(permission):
    def decorator(view):
        @wraps(view)
        @login_required
        def wrapped(*args, **kwargs):
            if permission not in g.perms:
                abort(403)
            return view(*args, **kwargs)
        return wrapped
    return decorator


def wants_json() -> bool:
    return request.is_json or request.headers.get("Accept", "").startswith("application/json")


# ── App wiring ────────────────────────────────────────────────────────────────

def init_security(app):
    @app.before_request
    def load_user():
        from bson import ObjectId
        g.user = None
        g.perms = set(PUBLIC_PERMISSIONS)
        uid = session.get("uid")
        if uid:
            try:
                oid = ObjectId(uid)
            except Exception:
                session.clear()
                return
            doc = current_app.db.users.find_one({"_id": oid}, {"password_hash": 0})
            if doc:
                g.user = User(doc)
                g.perms = load_permissions(current_app.db, doc["_id"]) | PUBLIC_PERMISSIONS
            else:
                session.clear()

    @app.before_request
    def check_csrf():
        if not current_app.config.get("WTF_CSRF_ENABLED", True):
            return
        if request.method in ("POST", "PUT", "PATCH", "DELETE"):
            sent = (request.form.get("csrf_token")
                    or request.headers.get("X-CSRF-Token"))
            if not sent or not secrets.compare_digest(sent, csrf_token()):
                abort(400, "Invalid or missing CSRF token. Reload the page and try again.")

    @app.context_processor
    def inject():
        return {
            "current_user": g.get("user"),
            "perms": g.get("perms", set()),
            "user_perms": g.get("perms", set()),
            "csrf_token": csrf_token,
        }

    # Make session cookies secure-ish
    app.config.setdefault("SESSION_COOKIE_HTTPONLY", True)
    app.config.setdefault("SESSION_COOKIE_SAMESITE", "Lax")
