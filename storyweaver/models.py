"""
Thin wrapper classes around MongoDB documents.
"""
from datetime import datetime, timezone

WORDS_PER_MINUTE = 200


def count_words(text: str) -> int:
    return len(text.split()) if text and text.strip() else 0


def _naive_utc(dt):
    if dt is None:
        return None
    if dt.tzinfo is not None:
        return dt.astimezone(timezone.utc).replace(tzinfo=None)
    return dt


def time_ago(dt) -> str:
    if dt is None:
        return ""
    now = datetime.now(timezone.utc).replace(tzinfo=None)
    diff = now - _naive_utc(dt)
    s = diff.total_seconds()
    if s < 60:
        return "just now"
    if s < 3600:
        m = int(s // 60)
        return f"{m} minute{'s' if m != 1 else ''} ago"
    if s < 86400:
        h = int(s // 3600)
        return f"{h} hour{'s' if h != 1 else ''} ago"
    if s < 86400 * 7:
        d = int(s // 86400)
        return f"{d} day{'s' if d != 1 else ''} ago"
    if s < 86400 * 30:
        w = int(s // (86400 * 7))
        return f"{w} week{'s' if w != 1 else ''} ago"
    if s < 86400 * 365:
        mo = int(s // (86400 * 30))
        return f"{mo} month{'s' if mo != 1 else ''} ago"
    y = int(s // (86400 * 365))
    return f"{y} year{'s' if y != 1 else ''} ago"


class Story:
    """A single passage: an opening, a continuation or an ending."""

    def __init__(self, doc, author_name=None):
        self.doc = dict(doc or {})
        if author_name is not None:
            self.doc["author_name"] = author_name

    def __getattr__(self, name):
        try:
            return self.doc[name]
        except KeyError:
            raise AttributeError(name) from None

    def __getitem__(self, key):
        return self.doc[key]

    def get(self, key, default=None):
        return self.doc.get(key, default)

    # ── identity ──────────────────────────────────────────────────────────────
    @property
    def id(self):
        return str(self.doc["_id"])

    @property
    def author_name(self):
        return self.doc.get("author_name") or "unknown"

    # ── kind / state ──────────────────────────────────────────────────────────
    @property
    def is_opening(self):
        return self.doc.get("kind") == "opening"

    @property
    def is_ending(self):
        return self.doc.get("kind") == "ending"

    @property
    def is_public(self):
        return self.doc.get("visibility") == "public"

    @property
    def is_hidden(self):
        return self.doc.get("status") == "hidden"

    @property
    def can_be_continued(self):
        return not self.is_ending and not self.is_hidden

    # ── text helpers ──────────────────────────────────────────────────────────
    @property
    def word_count(self):
        return self.doc.get("word_count") or count_words(self.doc.get("text", ""))

    @property
    def reading_time(self):
        """Estimated minutes to read (always at least 1)."""
        return max(1, round(self.word_count / WORDS_PER_MINUTE))

    @property
    def excerpt(self):
        text = " ".join((self.doc.get("text") or "").split())
        if len(text) <= 180:
            return text
        return text[:177].rsplit(" ", 1)[0].rstrip(".,;:!?") + "…"

    @property
    def first_line(self):
        text = (self.doc.get("text") or "").strip()
        for end in (". ", "! ", "? ", "\n"):
            i = text.find(end)
            if 0 < i < 160:
                return text[: i + 1].strip()
        return self.excerpt

    # ── stats ─────────────────────────────────────────────────────────────────
    @property
    def branch_count(self):
        return self.doc.get("stats", {}).get("continuations", 0)

    @property
    def like_count(self):
        return self.doc.get("stats", {}).get("likes", 0)

    @property
    def view_count(self):
        return self.doc.get("stats", {}).get("views", 0)

    @property
    def comment_count(self):
        return len(self.doc.get("comments", []))

    # ── time helpers ──────────────────────────────────────────────────────────
    @property
    def age(self):
        return time_ago(self.doc.get("created_at"))

    @property
    def was_edited(self):
        c = self.doc.get("created_at")
        u = self.doc.get("updated_at")
        return bool(c and u and (_naive_utc(u) - _naive_utc(c)).total_seconds() > 60)

    @property
    def kind_label(self):
        return {"opening": "Opening", "continuation": "Continuation",
                "ending": "Ending"}.get(self.doc.get("kind"), "")


class User:
    """Thin wrapper around a users document."""

    def __init__(self, doc):
        self.doc = doc or {}

    def __getattr__(self, name):
        try:
            return self.doc[name]
        except KeyError:
            raise AttributeError(name) from None

    def __getitem__(self, key):
        return self.doc[key]

    def get(self, key, default=None):
        return self.doc.get(key, default)

    @property
    def id(self):
        return str(self.doc["_id"])

    @property
    def default_visibility(self):
        return self.doc.get("default_visibility", "public")
