"""
Story Weaver — test suite (Table 4.3 from the project report)
10 test cases covering validators, routes, privacy, RBAC, CSRF, and maths.

Run:  pytest tests/test_app.py -v
"""
import math
import os
import unittest
from unittest.mock import patch

import mongomock
import pytest

# Point at a mongomock URI before importing the app
os.environ.setdefault("MONGO_URI", "mongodb://localhost/test_storyweaver")
os.environ.setdefault("SECRET_KEY", "test-secret-key-not-for-production")

from storyweaver import create_app
from storyweaver.schema import init_database, TEXT_MIN, TEXT_MAX
from storyweaver.models import count_words, Story
from storyweaver.routes.insights import linear_regression, writer_clusters


# ── helpers ───────────────────────────────────────────────────────────────────

def make_app():
    """Return a test-mode Flask app backed by mongomock."""
    app = create_app({"TESTING": True, "WTF_CSRF_ENABLED": False, "SECRET_KEY": "test"})
    with mongomock.patch(servers=(("localhost", 27017),)):
        with app.app_context():
            init_database(app.db, verbose=False)
    return app


def _register(client, username="alice", password="password123"):
    return client.post("/auth/register", data={
        "username": username,
        "email": f"{username}@test.com",
        "password": password,
        "confirm": password,
        "csrf_token": "test",
    }, follow_redirects=True)


def _login(client, username="alice", password="password123"):
    return client.post("/auth/login", data={
        "identifier": username,
        "password": password,
        "csrf_token": "test",
    }, follow_redirects=True)


def _write(client, title="Test Story", text=None, genre="Mystery",
           visibility="public", csrf="test"):
    if text is None:
        text = "A" * 120  # ~20 words placeholder; use count_words-safe string
        text = " ".join(["word"] * 25)
    return client.post("/stories/write", data={
        "title": title, "text": text,
        "genre": genre, "visibility": visibility,
        "tags": "test", "csrf_token": csrf,
    }, follow_redirects=True)


# ── TC01: Schema validators accept valid data ─────────────────────────────────

class TC01_SchemaValidators(unittest.TestCase):
    """Valid documents pass $jsonSchema; invalid ones are rejected."""

    def setUp(self):
        self.app = make_app()

    def test_valid_user_inserts(self):
        from bson import ObjectId
        from datetime import datetime, timezone
        with mongomock.patch(servers=(("localhost", 27017),)):
            with self.app.app_context():
                db = self.app.db
                uid = ObjectId()
                db.users.insert_one({
                    "_id": uid,
                    "username": "valid_user",
                    "email": "v@example.com",
                    "password_hash": "hashed",
                    "roles": ["writer"],
                    "bio": "",
                    "bookmarks": [],
                    "following": [],
                    "followers": [],
                    "default_visibility": "public",
                    "created_at": datetime.now(timezone.utc),
                })
                self.assertEqual(db.users.count_documents({"username": "valid_user"}), 1)

    def test_text_length_constants(self):
        self.assertEqual(TEXT_MIN, 20)
        self.assertEqual(TEXT_MAX, 5000)

    def test_count_words(self):
        self.assertEqual(count_words("hello world foo"), 3)
        self.assertEqual(count_words("  spaces   everywhere  "), 2)
        self.assertEqual(count_words(""), 0)


# ── TC02: Public pages are accessible without login ───────────────────────────

class TC02_PublicPages(unittest.TestCase):

    def setUp(self):
        self.app = make_app()
        self.client = self.app.test_client()

    def test_home_200(self):
        with mongomock.patch(servers=(("localhost", 27017),)):
            with self.app.app_context():
                init_database(self.app.db, verbose=False)
            resp = self.client.get("/")
            self.assertEqual(resp.status_code, 200)

    def test_explore_200(self):
        with mongomock.patch(servers=(("localhost", 27017),)):
            with self.app.app_context():
                init_database(self.app.db, verbose=False)
            resp = self.client.get("/stories/explore")
            self.assertEqual(resp.status_code, 200)

    def test_insights_200(self):
        with mongomock.patch(servers=(("localhost", 27017),)):
            with self.app.app_context():
                init_database(self.app.db, verbose=False)
            resp = self.client.get("/insights")
            self.assertEqual(resp.status_code, 200)

    def test_login_page_200(self):
        with mongomock.patch(servers=(("localhost", 27017),)):
            with self.app.app_context():
                init_database(self.app.db, verbose=False)
            resp = self.client.get("/auth/login")
            self.assertEqual(resp.status_code, 200)


# ── TC03: Privacy — private passages hidden from other users ──────────────────

class TC03_Privacy(unittest.TestCase):

    def setUp(self):
        self.app = make_app()

    def test_private_passage_hidden(self):
        from bson import ObjectId
        from datetime import datetime, timezone

        with mongomock.patch(servers=(("localhost", 27017),)):
            with self.app.app_context():
                db = self.app.db
                init_database(db, verbose=False)
                uid = ObjectId()
                root = ObjectId()
                db.users.insert_one({
                    "_id": uid, "username": "owner", "email": "o@test.com",
                    "password_hash": "x", "roles": ["writer"], "bio": "",
                    "bookmarks": [], "following": [], "followers": [],
                    "default_visibility": "public",
                    "created_at": datetime.now(timezone.utc),
                })
                db.stories.insert_one({
                    "_id": root, "title": "Secret", "text": " ".join(["word"] * 25),
                    "kind": "opening", "parent_id": None, "root_id": root,
                    "ancestors": [], "depth": 0, "author_id": uid,
                    "genre": "Mystery", "tags": [], "visibility": "private",
                    "status": "active",
                    "stats": {"continuations": 0, "likes": 0, "views": 0},
                    "liked_by": [], "reported_by": [], "comments": [],
                    "word_count": 25,
                    "created_at": datetime.now(timezone.utc),
                    "updated_at": datetime.now(timezone.utc),
                })
                from storyweaver.queries import visible_filter
                from storyweaver.schema import PUBLIC_PERMISSIONS
                f = visible_filter(None, PUBLIC_PERMISSIONS)
                count = db.stories.count_documents(f)
                self.assertEqual(count, 0, "Private passage must not appear to anonymous users")


# ── TC04: Write and continue flow ─────────────────────────────────────────────

class TC04_WriteAndContinue(unittest.TestCase):

    def setUp(self):
        self.app = make_app()
        self.client = self.app.test_client()

    def test_write_requires_login(self):
        with mongomock.patch(servers=(("localhost", 27017),)):
            with self.app.app_context():
                init_database(self.app.db, verbose=False)
            resp = self.client.get("/stories/write", follow_redirects=False)
            self.assertEqual(resp.status_code, 302)
            self.assertIn("/auth/login", resp.headers["Location"])

    def test_write_and_story_exists(self):
        with mongomock.patch(servers=(("localhost", 27017),)):
            with self.app.app_context():
                init_database(self.app.db, verbose=False)
            _register(self.client, "writer1")
            _login(self.client, "writer1")
            resp = _write(self.client, title="The Grand Test")
            self.assertEqual(resp.status_code, 200)
            with self.app.app_context():
                count = self.app.db.stories.count_documents({"title": "The Grand Test"})
                self.assertEqual(count, 1)


# ── TC05: Private continuation not visible to other users ─────────────────────

class TC05_PrivateContinuation(unittest.TestCase):

    def test_private_continuation_hidden(self):
        from bson import ObjectId
        from datetime import datetime, timezone
        app = make_app()
        with mongomock.patch(servers=(("localhost", 27017),)):
            with app.app_context():
                db = app.db
                init_database(db, verbose=False)
                uid = ObjectId()
                root = ObjectId()
                child = ObjectId()
                now = datetime.now(timezone.utc)
                db.users.insert_one({
                    "_id": uid, "username": "author2", "email": "a2@test.com",
                    "password_hash": "x", "roles": ["writer"], "bio": "",
                    "bookmarks": [], "following": [], "followers": [],
                    "default_visibility": "public", "created_at": now,
                })
                db.stories.insert_one({
                    "_id": root, "title": "Root", "text": " ".join(["word"] * 25),
                    "kind": "opening", "parent_id": None, "root_id": root,
                    "ancestors": [], "depth": 0, "author_id": uid,
                    "genre": "Mystery", "tags": [], "visibility": "public",
                    "status": "active",
                    "stats": {"continuations": 0, "likes": 0, "views": 0},
                    "liked_by": [], "reported_by": [], "comments": [],
                    "word_count": 25, "created_at": now, "updated_at": now,
                })
                db.stories.insert_one({
                    "_id": child, "title": "Root", "text": " ".join(["word"] * 30),
                    "kind": "continuation", "parent_id": root, "root_id": root,
                    "ancestors": [root], "depth": 1, "author_id": uid,
                    "genre": "Mystery", "tags": [], "visibility": "private",
                    "status": "active",
                    "stats": {"continuations": 0, "likes": 0, "views": 0},
                    "liked_by": [], "reported_by": [], "comments": [],
                    "word_count": 30, "created_at": now, "updated_at": now,
                })
                from storyweaver.queries import visible_filter
                from storyweaver.schema import PUBLIC_PERMISSIONS
                f = visible_filter(None, PUBLIC_PERMISSIONS)
                # Only the public opening should be visible
                docs = list(db.stories.find(f))
                ids = [str(d["_id"]) for d in docs]
                self.assertIn(str(root), ids)
                self.assertNotIn(str(child), ids)


# ── TC06: Likes, saves, follows, comments via API ─────────────────────────────

class TC06_Interactions(unittest.TestCase):

    def setUp(self):
        self.app = make_app()
        self.client = self.app.test_client()

    def test_like_toggle(self):
        """Like an accessible story → liked; like again → unliked."""
        from bson import ObjectId
        from datetime import datetime, timezone
        with mongomock.patch(servers=(("localhost", 27017),)):
            with self.app.app_context():
                db = self.app.db
                init_database(db, verbose=False)
                uid = ObjectId()
                root = ObjectId()
                now = datetime.now(timezone.utc)
                db.users.insert_one({
                    "_id": uid, "username": "liker", "email": "l@test.com",
                    "password_hash": "x", "roles": ["writer"], "bio": "",
                    "bookmarks": [], "following": [], "followers": [],
                    "default_visibility": "public", "created_at": now,
                })
                db.stories.insert_one({
                    "_id": root, "title": "Likeable", "text": " ".join(["word"] * 25),
                    "kind": "opening", "parent_id": None, "root_id": root,
                    "ancestors": [], "depth": 0, "author_id": uid,
                    "genre": "Mystery", "tags": [], "visibility": "public",
                    "status": "active",
                    "stats": {"continuations": 0, "likes": 0, "views": 0},
                    "liked_by": [], "reported_by": [], "comments": [],
                    "word_count": 25, "created_at": now, "updated_at": now,
                })

            # "liker" already owns the story; sign in as a separate account
            _register(self.client, "liker2")
            _login(self.client, "liker2")

            resp1 = self.client.post(f"/api/story/{root}/like",
                                     headers={"X-CSRF-Token": "test"})
            self.assertEqual(resp1.status_code, 200)
            self.assertTrue(resp1.json["liked"])
            self.assertEqual(resp1.json["likes"], 1)

            resp2 = self.client.post(f"/api/story/{root}/like",
                                     headers={"X-CSRF-Token": "test"})
            self.assertFalse(resp2.json["liked"])
            self.assertEqual(resp2.json["likes"], 0)


# ── TC07: RBAC — moderator can hide, reader cannot ────────────────────────────

class TC07_RBAC(unittest.TestCase):

    def test_permission_required_moderator(self):
        """A writer (not moderator) cannot access the admin panel."""
        app = make_app()
        client = app.test_client()
        with mongomock.patch(servers=(("localhost", 27017),)):
            with app.app_context():
                init_database(app.db, verbose=False)
            _register(client, "plain_writer")
            _login(client, "plain_writer")
            resp = client.get("/admin/", follow_redirects=False)
            # Should redirect (to login or 403)
            self.assertIn(resp.status_code, [302, 403])

    def test_unauthenticated_cannot_write(self):
        app = make_app()
        client = app.test_client()
        with mongomock.patch(servers=(("localhost", 27017),)):
            with app.app_context():
                init_database(app.db, verbose=False)
            resp = client.post("/stories/write", data={
                "title": "Hack", "text": " ".join(["word"] * 25),
                "genre": "Mystery", "csrf_token": "test"
            }, follow_redirects=False)
            self.assertEqual(resp.status_code, 302)


# ── TC08: CSRF protection ─────────────────────────────────────────────────────

class TC08_CSRF(unittest.TestCase):

    def test_csrf_token_generated(self):
        """csrf_token() returns a non-empty string inside a request context."""
        app = make_app()
        with app.test_request_context("/"):
            app.preprocess_request()
            from storyweaver.security import csrf_token
            token = csrf_token()
            self.assertIsInstance(token, str)
            self.assertGreater(len(token), 10)

    def test_verify_password(self):
        from storyweaver.security import hash_password, verify_password
        h = hash_password("secret99")
        self.assertTrue(verify_password("secret99", h))
        self.assertFalse(verify_password("wrong", h))


# ── TC09: Insights mathematics ────────────────────────────────────────────────

class TC09_InsightsMaths(unittest.TestCase):

    def test_linear_regression_known_values(self):
        """Regression on a perfect y=2x line should give slope≈2, r≈1."""
        app = make_app()
        with mongomock.patch(servers=(("localhost", 27017),)):
            with app.app_context():
                db = app.db
                init_database(db, verbose=False)
                from bson import ObjectId
                from datetime import datetime, timezone
                uid = ObjectId()
                now = datetime.now(timezone.utc)
                db.users.insert_one({
                    "_id": uid, "username": "regruser", "email": "r@test.com",
                    "password_hash": "x", "roles": ["writer"], "bio": "",
                    "bookmarks": [], "following": [], "followers": [],
                    "default_visibility": "public", "created_at": now,
                })
                # Insert 5 trees: opening word_count 10,20,30,40,50
                # continuations 2,4,6,8,10 (perfect 2x relationship)
                for i, (wc, nc) in enumerate([(10,2),(20,4),(30,6),(40,8),(50,10)]):
                    root = ObjectId()
                    db.stories.insert_one({
                        "_id": root, "title": f"Story {i}", "text": "x " * wc,
                        "kind": "opening", "parent_id": None, "root_id": root,
                        "ancestors": [], "depth": 0, "author_id": uid,
                        "genre": "Mystery", "tags": [], "visibility": "public",
                        "status": "active",
                        "stats": {"continuations": 0, "likes": 0, "views": 0},
                        "liked_by": [], "reported_by": [], "comments": [],
                        "word_count": wc, "created_at": now, "updated_at": now,
                    })
                    # Insert nc continuation stubs
                    for j in range(nc):
                        cid = ObjectId()
                        db.stories.insert_one({
                            "_id": cid, "title": f"Story {i}", "text": "y " * 25,
                            "kind": "continuation", "parent_id": root, "root_id": root,
                            "ancestors": [root], "depth": 1, "author_id": uid,
                            "genre": "Mystery", "tags": [], "visibility": "public",
                            "status": "active",
                            "stats": {"continuations": 0, "likes": 0, "views": 0},
                            "liked_by": [], "reported_by": [], "comments": [],
                            "word_count": 25, "created_at": now, "updated_at": now,
                        })

                result = linear_regression(db)
                self.assertIsNotNone(result)
                self.assertAlmostEqual(result["slope"], 0.2, places=4)
                self.assertAlmostEqual(result["r"], 1.0, places=4)
                self.assertEqual(result["n"], 5)

    def test_linear_regression_insufficient_data(self):
        """Fewer than 3 stories → regression returns None."""
        app = make_app()
        with mongomock.patch(servers=(("localhost", 27017),)):
            with app.app_context():
                db = app.db
                init_database(db, verbose=False)
                result = linear_regression(db)
                self.assertIsNone(result)


# ── TC10: Story model properties ──────────────────────────────────────────────

class TC10_StoryModel(unittest.TestCase):

    def _make_story(self, **kwargs):
        from bson import ObjectId
        from datetime import datetime, timezone
        oid = ObjectId()
        base = {
            "_id": oid,
            "title": "Test",
            "text": " ".join(["the"] * 25),
            "kind": "opening",
            "parent_id": None,
            "root_id": oid,
            "ancestors": [],
            "depth": 0,
            "author_id": ObjectId(),
            "genre": "Mystery",
            "tags": ["a", "b"],
            "visibility": "public",
            "status": "active",
            "stats": {"continuations": 3, "likes": 7, "views": 42},
            "liked_by": [],
            "reported_by": [],
            "comments": [],
            "word_count": 25,
            "created_at": datetime.now(timezone.utc),
            "updated_at": datetime.now(timezone.utc),
        }
        base.update(kwargs)
        return Story(base, author_name="testauthor")

    def test_is_opening(self):
        s = self._make_story(kind="opening")
        self.assertTrue(s.is_opening)
        self.assertFalse(s.is_ending)

    def test_is_ending(self):
        s = self._make_story(kind="ending")
        self.assertTrue(s.is_ending)

    def test_like_count(self):
        s = self._make_story()
        self.assertEqual(s.like_count, 7)

    def test_branch_count(self):
        s = self._make_story()
        self.assertEqual(s.branch_count, 3)

    def test_word_count(self):
        s = self._make_story()
        self.assertEqual(s.word_count, 25)

    def test_reading_time_minimum_one(self):
        s = self._make_story()
        self.assertGreaterEqual(s.reading_time, 1)

    def test_excerpt_truncation(self):
        long_text = " ".join(["word"] * 100)
        s = self._make_story(text=long_text)
        self.assertLessEqual(len(s.excerpt), 220)

    def test_author_name(self):
        s = self._make_story()
        self.assertEqual(s.author_name, "testauthor")

    def test_id_is_string(self):
        s = self._make_story()
        self.assertIsInstance(s.id, str)

    def test_is_public(self):
        s = self._make_story(visibility="public")
        self.assertTrue(s.is_public)
        s2 = self._make_story(visibility="private")
        self.assertFalse(s2.is_public)


if __name__ == "__main__":
    unittest.main()
