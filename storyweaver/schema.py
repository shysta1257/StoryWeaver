"""
$jsonSchema validators for all five collections, plus RBAC seed data and index creation.
"""

TEXT_MIN = 20
TEXT_MAX = 5000

GENRES = ["Fantasy", "Sci-Fi", "Mystery", "Romance", "Horror",
          "Adventure", "Slice of Life", "Comedy", "Thriller", "Other"]

COMMENT_SCHEMA = {
    "bsonType": "object",
    "required": ["_id", "author_id", "username", "text", "created_at"],
    "properties": {
        "_id": {"bsonType": "objectId"},
        "author_id": {"bsonType": "objectId"},
        "username": {"bsonType": "string"},
        "text": {"bsonType": "string", "minLength": 1, "maxLength": 1000},
        "created_at": {"bsonType": "date"},
    },
}

STORY_SCHEMA = {
    "$jsonSchema": {
        "bsonType": "object",
        "required": [
            "title", "text", "kind", "parent_id", "root_id", "ancestors",
            "depth", "author_id", "genre", "tags", "visibility", "status",
            "stats", "liked_by", "reported_by", "comments", "word_count",
            "created_at", "updated_at",
        ],
        "properties": {
            "title": {"bsonType": "string", "minLength": 3, "maxLength": 120},
            "text": {"bsonType": "string", "minLength": TEXT_MIN, "maxLength": TEXT_MAX},
            "kind": {"enum": ["opening", "continuation", "ending"]},
            "parent_id": {"bsonType": ["objectId", "null"]},
            "root_id": {"bsonType": "objectId"},
            "ancestors": {"bsonType": "array", "items": {"bsonType": "objectId"}},
            "depth": {"bsonType": "int", "minimum": 0},
            "author_id": {"bsonType": "objectId"},
            "genre": {"enum": GENRES},
            "tags": {"bsonType": "array", "maxItems": 8, "items": {"bsonType": "string", "maxLength": 30}},
            "visibility": {"enum": ["public", "private"]},
            "status": {"enum": ["active", "hidden"]},
            "stats": {
                "bsonType": "object",
                "required": ["continuations", "likes", "views"],
                "properties": {
                    "continuations": {"bsonType": "int", "minimum": 0},
                    "likes": {"bsonType": "int", "minimum": 0},
                    "views": {"bsonType": "int", "minimum": 0},
                },
            },
            "liked_by": {"bsonType": "array", "items": {"bsonType": "objectId"}},
            "reported_by": {"bsonType": "array", "items": {"bsonType": "objectId"}},
            "comments": {"bsonType": "array", "items": COMMENT_SCHEMA},
            "word_count": {"bsonType": "int", "minimum": 1},
            "created_at": {"bsonType": "date"},
            "updated_at": {"bsonType": "date"},
        },
    }
}

USER_SCHEMA = {
    "$jsonSchema": {
        "bsonType": "object",
        "required": ["username", "email", "password_hash", "roles", "bio",
                     "bookmarks", "following", "followers", "created_at"],
        "properties": {
            "username": {"bsonType": "string", "minLength": 3, "maxLength": 20,
                         "pattern": "^[a-zA-Z0-9_]+$"},
            "email": {"bsonType": "string"},
            "password_hash": {"bsonType": "string"},
            "roles": {"bsonType": "array", "items": {"bsonType": "string"}},
            "bio": {"bsonType": "string", "maxLength": 300},
            "bookmarks": {"bsonType": "array", "items": {"bsonType": "objectId"}},
            "following": {"bsonType": "array", "items": {"bsonType": "objectId"}},
            "followers": {"bsonType": "array", "items": {"bsonType": "objectId"}},
            "created_at": {"bsonType": "date"},
            "default_visibility": {"bsonType": "string", "enum": ["public", "private"]},
        },
    }
}

ROLE_SCHEMA = {
    "$jsonSchema": {
        "bsonType": "object",
        "required": ["name", "permissions"],
        "properties": {
            "name": {"bsonType": "string"},
            "permissions": {"bsonType": "array", "items": {"bsonType": "string"}},
        },
    }
}

PERMISSION_SCHEMA = {
    "$jsonSchema": {
        "bsonType": "object",
        "required": ["name", "description"],
        "properties": {
            "name": {"bsonType": "string"},
            "description": {"bsonType": "string"},
        },
    }
}

PROMPT_SCHEMA = {
    "$jsonSchema": {
        "bsonType": "object",
        "required": ["text", "genre", "created_at"],
        "properties": {
            "text": {"bsonType": "string", "minLength": 5, "maxLength": 500},
            "genre": {"enum": GENRES},
            "created_at": {"bsonType": "date"},
        },
    }
}

VALIDATORS = {
    "stories": STORY_SCHEMA,
    "users": USER_SCHEMA,
    "roles": ROLE_SCHEMA,
    "permissions": PERMISSION_SCHEMA,
    "prompts": PROMPT_SCHEMA,
}

# ── RBAC seed data ───────────────────────────────────────────────────────────

PERMISSIONS = [
    {"name": "read_stories",      "description": "View public stories"},
    {"name": "write_stories",     "description": "Create openings and continuations"},
    {"name": "comment",           "description": "Post comments"},
    {"name": "like_save",         "description": "Like and bookmark passages"},
    {"name": "follow",            "description": "Follow other writers"},
    {"name": "edit_own",          "description": "Edit or delete own passages"},
    {"name": "moderate_stories",  "description": "Hide/unhide any passage"},
    {"name": "manage_users",      "description": "Change roles, ban users"},
    {"name": "manage_prompts",    "description": "Create and delete writing prompts"},
]

ROLE_NAMES = ["reader", "writer", "moderator", "admin"]

ROLES = [
    {"name": "reader",    "permissions": ["read_stories"]},
    {"name": "writer",    "permissions": ["read_stories", "write_stories", "comment",
                                          "like_save", "follow", "edit_own"]},
    {"name": "moderator", "permissions": ["read_stories", "write_stories", "comment",
                                          "like_save", "follow", "edit_own",
                                          "moderate_stories", "manage_prompts"]},
    {"name": "admin",     "permissions": ["read_stories", "write_stories", "comment",
                                          "like_save", "follow", "edit_own",
                                          "moderate_stories", "manage_users",
                                          "manage_prompts"]},
]

# Permissions available without login
PUBLIC_PERMISSIONS = frozenset(["read_stories"])


def _apply_validator(db, name, validator):
    try:
        if name in db.list_collection_names():
            db.command("collMod", name, validator=validator,
                       validationLevel="strict", validationAction="error")
        else:
            db.create_collection(name, validator=validator,
                                 validationLevel="strict", validationAction="error")
        return True
    except (NotImplementedError, Exception):
        if name not in db.list_collection_names():
            db.create_collection(name)
        return False


def init_database(db, verbose=True):
    log = print if verbose else (lambda *a, **k: None)

    for name, validator in VALIDATORS.items():
        ok = _apply_validator(db, name, validator)
        log(f"  collection {name:<12} validator {'on' if ok else 'skipped (mock)'}")

    for name in ("roles", "permissions"):
        if name not in db.list_collection_names():
            db.create_collection(name)

    # Upsert RBAC data
    for p in PERMISSIONS:
        db.permissions.update_one({"name": p["name"]}, {"$set": p}, upsert=True)
    for r in ROLES:
        db.roles.update_one({"name": r["name"]}, {"$set": r}, upsert=True)
    log(f"  roles: {', '.join(ROLE_NAMES)}")

    # Indexes
    from pymongo import ASCENDING, DESCENDING
    db.users.create_index([("username", ASCENDING)], unique=True)
    db.users.create_index([("email", ASCENDING)], unique=True)
    db.roles.create_index([("name", ASCENDING)], unique=True)
    db.permissions.create_index([("name", ASCENDING)], unique=True)
    db.stories.create_index([("root_id", ASCENDING), ("depth", ASCENDING)])
    db.stories.create_index([("parent_id", ASCENDING)])
    db.stories.create_index([("author_id", ASCENDING), ("created_at", DESCENDING)])
    db.stories.create_index([("kind", ASCENDING), ("visibility", ASCENDING),
                              ("status", ASCENDING), ("created_at", DESCENDING)])
    db.stories.create_index([("genre", ASCENDING)])
    log("  indexes created")
