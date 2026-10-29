#!/usr/bin/env python3
"""
Seed the database with 9 sample users and 24 passages forming branching story trees.
Run AFTER setup_db.py.
"""
import os
from datetime import datetime, timezone, timedelta
from dotenv import load_dotenv
load_dotenv()

from bson import ObjectId
from pymongo import MongoClient
from werkzeug.security import generate_password_hash

from storyweaver.models import count_words
from storyweaver.schema import init_database

def dt(days_ago=0, hours_ago=0):
    return datetime.now(timezone.utc) - timedelta(days=days_ago, hours=hours_ago)

def main():
    uri = os.environ.get("MONGO_URI", "mongodb://localhost:27017/storyweaver")
    db_name = uri.rsplit("/", 1)[-1].split("?")[0] or "storyweaver"
    client = MongoClient(uri)
    db = client[db_name]

    # Init schema (safe to re-run)
    init_database(db, verbose=False)

    # ── Users ─────────────────────────────────────────────────────────────────
    pw = generate_password_hash("password123")
    user_names = ["admin", "moderator", "nina", "sam", "arjun", "zoe", "ravi", "maya", "priya"]
    user_ids = {}
    for name in user_names:
        existing = db.users.find_one({"username": name})
        if existing:
            user_ids[name] = existing["_id"]
            continue
        uid = ObjectId()
        role = "admin" if name == "admin" else ("moderator" if name == "moderator" else "writer")
        db.users.update_one(
            {"username": name},
            {"$setOnInsert": {
                "_id": uid,
                "username": name,
                "email": f"{name}@example.com",
                "password_hash": pw,
                "roles": [role],
                "bio": f"Writer {name}.",
                "bookmarks": [],
                "following": [],
                "followers": [],
                "default_visibility": "public",
                "created_at": dt(30),
            }},
            upsert=True
        )
        user_ids[name] = db.users.find_one({"username": name})["_id"]

    u = user_ids  # shorthand

    # Story IDs are generated fresh each run, so bail out rather than duplicate them
    if db.stories.find_one({"title": "The Lighthouse That Rang", "kind": "opening"}):
        print("Stories already seeded; skipping. Drop the database to re-seed.")
        return

    # ── Story 1: The Lighthouse That Rang ─────────────────────────────────────
    root1 = ObjectId()
    db.stories.update_one({"_id": root1}, {"$setOnInsert": {
        "_id": root1,
        "title": "The Lighthouse That Rang",
        "text": ("Every night at 3:17 a.m., the old lighthouse on Kavu Point rang its bell, "
                 "though it had no bell, and no keeper had climbed its stairs in forty years. "
                 "Tonight, Meera stood at its rusted door with a torch in one hand and her "
                 "grandmother's key in the other. The key was warm."),
        "kind": "opening", "parent_id": None, "root_id": root1,
        "ancestors": [], "depth": 0, "author_id": u["admin"],
        "genre": "Mystery", "tags": ["lighthouse", "ghost", "family"],
        "visibility": "public", "status": "active",
        "stats": {"continuations": 0, "likes": 4, "views": 18},
        "liked_by": [u["nina"], u["sam"], u["ravi"], u["maya"]],
        "reported_by": [], "comments": [],
        "word_count": count_words("Every night at 3:17 a.m., the old lighthouse on Kavu Point rang its bell..."),
        "created_at": dt(14), "updated_at": dt(14),
    }}, upsert=True)

    # Branch A: moderator
    c1a = ObjectId()
    db.stories.update_one({"_id": c1a}, {"$setOnInsert": {
        "_id": c1a, "title": "The Lighthouse That Rang",
        "text": ("The door opened on its own before the key touched the lock. Inside, the spiral "
                 "stairs were swept clean, and on the third step sat a teacup, still steaming. "
                 "Someone had been expecting her. Meera counted the steps as she climbed: one "
                 "hundred and twelve, exactly as many as the years on her grandmother's gravestone."),
        "kind": "continuation", "parent_id": root1, "root_id": root1,
        "ancestors": [root1], "depth": 1, "author_id": u["moderator"],
        "genre": "Mystery", "tags": ["lighthouse", "ghost", "family"],
        "visibility": "public", "status": "active",
        "stats": {"continuations": 1, "likes": 2, "views": 9},
        "liked_by": [u["nina"], u["ravi"]], "reported_by": [], "comments": [],
        "word_count": count_words("The door opened on its own..."),
        "created_at": dt(13), "updated_at": dt(13),
    }}, upsert=True)

    # Branch A ending: nina
    c1a_end = ObjectId()
    db.stories.update_one({"_id": c1a_end}, {"$setOnInsert": {
        "_id": c1a_end, "title": "The Lighthouse That Rang",
        "text": ("She never reached the top. At step ninety-nine she found her grandmother's diary "
                 "and sat down to read it by torchlight. By the last page she understood that the "
                 "lighthouse wasn't calling anyone in. It was keeping something out. She locked the "
                 "door behind her, went home, and wore the key on a string around her neck for the rest of her life."),
        "kind": "ending", "parent_id": c1a, "root_id": root1,
        "ancestors": [root1, c1a], "depth": 2, "author_id": u["nina"],
        "genre": "Mystery", "tags": ["lighthouse", "ghost", "family"],
        "visibility": "public", "status": "active",
        "stats": {"continuations": 0, "likes": 3, "views": 12},
        "liked_by": [u["admin"], u["sam"], u["moderator"]], "reported_by": [], "comments": [],
        "word_count": count_words("She never reached the top..."),
        "created_at": dt(12), "updated_at": dt(12),
    }}, upsert=True)

    # Branch B: sam
    c1b = ObjectId()
    db.stories.update_one({"_id": c1b}, {"$setOnInsert": {
        "_id": c1b, "title": "The Lighthouse That Rang",
        "text": ("The key didn't fit. Meera tried it three times before she noticed the second "
                 "keyhole, low on the door, no bigger than a coin. She knelt, and from the other "
                 "side, someone — or something — knocked back. One knock. A pause. Then three more."),
        "kind": "continuation", "parent_id": root1, "root_id": root1,
        "ancestors": [root1], "depth": 1, "author_id": u["sam"],
        "genre": "Mystery", "tags": ["lighthouse", "ghost", "family"],
        "visibility": "public", "status": "active",
        "stats": {"continuations": 1, "likes": 1, "views": 7},
        "liked_by": [u["arjun"]], "reported_by": [], "comments": [],
        "word_count": count_words("The key didn't fit..."),
        "created_at": dt(11), "updated_at": dt(11),
    }}, upsert=True)

    # Branch B continuation: moderator
    c1b2 = ObjectId()
    db.stories.update_one({"_id": c1b2}, {"$setOnInsert": {
        "_id": c1b2, "title": "The Lighthouse That Rang",
        "text": ("She stumbled back into the sand. The breathing stopped. A small voice said, "
                 "'You're early. I told grandmother to send you at dawn.' Meera looked at the "
                 "lighthouse, then at the dark ocean, then at the horizon where the first light "
                 "was already rising. She sat down to wait."),
        "kind": "continuation", "parent_id": c1b, "root_id": root1,
        "ancestors": [root1, c1b], "depth": 2, "author_id": u["moderator"],
        "genre": "Mystery", "tags": ["lighthouse", "ghost", "family"],
        "visibility": "public", "status": "active",
        "stats": {"continuations": 0, "likes": 1, "views": 5},
        "liked_by": [u["admin"]], "reported_by": [], "comments": [],
        "word_count": count_words("She stumbled back into the sand..."),
        "created_at": dt(10), "updated_at": dt(10),
    }}, upsert=True)

    # Branch C: zoe (alternate depth-1 branch)
    c1c = ObjectId()
    db.stories.update_one({"_id": c1c}, {"$setOnInsert": {
        "_id": c1c, "title": "The Lighthouse That Rang",
        "text": ("At the top, the lamp room was full of clocks. Hundreds of them, every one "
                 "stopped at 3:16. The only moving thing was a pendulum hanging from the dome, "
                 "swinging slow and wide. Underneath it, someone had drawn a map in chalk on "
                 "the floor. Meera recognized the coastline."),
        "kind": "continuation", "parent_id": root1, "root_id": root1,
        "ancestors": [root1], "depth": 1, "author_id": u["zoe"],
        "genre": "Mystery", "tags": ["lighthouse", "clocks"],
        "visibility": "public", "status": "active",
        "stats": {"continuations": 0, "likes": 2, "views": 6},
        "liked_by": [u["ravi"], u["maya"]], "reported_by": [], "comments": [],
        "word_count": count_words("At the top, the lamp room was full of clocks..."),
        "created_at": dt(9), "updated_at": dt(9),
    }}, upsert=True)

    # admin ending branch
    c1d = ObjectId()
    db.stories.update_one({"_id": c1d}, {"$setOnInsert": {
        "_id": c1d, "title": "The Lighthouse That Rang",
        "text": ("Meera followed the chalk map down the cliff path to a cave. Inside was a small "
                 "brass bell on a shelf of rock, salt-crusted but intact. When she struck it, "
                 "the sound it made was the same sound the lighthouse made every night. "
                 "She carried it home, set it on her mantelpiece, and never heard the lighthouse again."),
        "kind": "ending", "parent_id": c1c, "root_id": root1,
        "ancestors": [root1, c1c], "depth": 2, "author_id": u["admin"],
        "genre": "Mystery", "tags": ["lighthouse", "clocks"],
        "visibility": "public", "status": "active",
        "stats": {"continuations": 0, "likes": 2, "views": 8},
        "liked_by": [u["zoe"], u["moderator"]], "reported_by": [], "comments": [],
        "word_count": count_words("Meera followed the chalk map..."),
        "created_at": dt(8), "updated_at": dt(8),
    }}, upsert=True)

    # ── Story 2: Seat 14C ─────────────────────────────────────────────────────
    root2 = ObjectId()
    db.stories.update_one({"_id": root2}, {"$setOnInsert": {
        "_id": root2,
        "title": "Seat 14C",
        "text": ("The flight attendant leaned in and asked if I'd like the chicken or the pasta, "
                 "and then, quieter, whether I'd remembered that this was the flight where I was "
                 "supposed to change everything. I had not remembered. I had never been on this "
                 "flight before. At least, I didn't think so."),
        "kind": "opening", "parent_id": None, "root_id": root2,
        "ancestors": [], "depth": 0, "author_id": u["moderator"],
        "genre": "Sci-Fi", "tags": ["time-loop", "flight", "mystery"],
        "visibility": "public", "status": "active",
        "stats": {"continuations": 2, "likes": 5, "views": 16},
        "liked_by": [u["admin"], u["nina"], u["sam"], u["zoe"], u["arjun"]],
        "reported_by": [], "comments": [],
        "word_count": count_words("The flight attendant leaned in..."),
        "created_at": dt(7), "updated_at": dt(7),
    }}, upsert=True)

    # Branch A
    c2a = ObjectId()
    db.stories.update_one({"_id": c2a}, {"$setOnInsert": {
        "_id": c2a, "title": "Seat 14C",
        "text": ("I said pasta, because it felt safer. She smiled like I'd passed a test and "
                 "slid a folded napkin onto my tray. Inside, in my own handwriting: DON'T LET "
                 "THEM LAND IN DELHI. The man in 14B, a seat I could ask what happened last time — "
                 "he was watching me with the expression of someone who already knows the ending."),
        "kind": "continuation", "parent_id": root2, "root_id": root2,
        "ancestors": [root2], "depth": 1, "author_id": u["ravi"],
        "genre": "Sci-Fi", "tags": ["time-loop", "flight"],
        "visibility": "public", "status": "active",
        "stats": {"continuations": 1, "likes": 2, "views": 8},
        "liked_by": [u["moderator"], u["maya"]], "reported_by": [], "comments": [],
        "word_count": count_words("I said pasta..."),
        "created_at": dt(6), "updated_at": dt(6),
    }}, upsert=True)

    # Branch A continuation
    c2a2 = ObjectId()
    db.stories.update_one({"_id": c2a2}, {"$setOnInsert": {
        "_id": c2a2, "title": "Seat 14C",
        "text": ("I handed the man in 14B the napkin. He read it, folded it into a small "
                 "square, and swallowed it whole without breaking eye contact. Then he said, "
                 "'Third time's the charm.' The plane began its descent. Outside the window, "
                 "Delhi's lights were already spreading below us. It was too late."),
        "kind": "ending", "parent_id": c2a, "root_id": root2,
        "ancestors": [root2, c2a], "depth": 2, "author_id": u["maya"],
        "genre": "Sci-Fi", "tags": ["time-loop", "flight"],
        "visibility": "public", "status": "active",
        "stats": {"continuations": 0, "likes": 1, "views": 4},
        "liked_by": [u["ravi"]], "reported_by": [], "comments": [],
        "word_count": count_words("I handed the man in 14B..."),
        "created_at": dt(5), "updated_at": dt(5),
    }}, upsert=True)

    # Branch B
    c2b = ObjectId()
    db.stories.update_one({"_id": c2b}, {"$setOnInsert": {
        "_id": c2b, "title": "Seat 14C",
        "text": ("I said chicken. Her smile flickered. 'That's what you said last time,' she "
                 "whispered, and walked away before I could ask what happened last time. The man "
                 "in 14B, a seat I could have sworn was empty, cleared his throat. 'Wrong answer,' "
                 "he said. 'Again.' He showed me my own passport. The expiry date was yesterday."),
        "kind": "continuation", "parent_id": root2, "root_id": root2,
        "ancestors": [root2], "depth": 1, "author_id": u["arjun"],
        "genre": "Sci-Fi", "tags": ["time-loop", "flight"],
        "visibility": "public", "status": "active",
        "stats": {"continuations": 0, "likes": 3, "views": 10},
        "liked_by": [u["admin"], u["nina"], u["zoe"]], "reported_by": [], "comments": [],
        "word_count": count_words("I said chicken..."),
        "created_at": dt(5, 12), "updated_at": dt(5, 12),
    }}, upsert=True)

    # ── Story 3: What the Snow Kept ───────────────────────────────────────────
    root3 = ObjectId()
    db.stories.update_one({"_id": root3}, {"$setOnInsert": {
        "_id": root3,
        "title": "What the Snow Kept",
        "text": ("When the snow finally melted in March, it gave back everything it had taken "
                 "over the winter: the lost gloves, the neighbour's cat, and, standing perfectly "
                 "still at the bottom of the garden, a woman none of them had ever seen before."),
        "kind": "opening", "parent_id": None, "root_id": root3,
        "ancestors": [], "depth": 0, "author_id": u["sam"],
        "genre": "Horror", "tags": ["winter", "stranger", "mystery"],
        "visibility": "public", "status": "active",
        "stats": {"continuations": 1, "likes": 5, "views": 19},
        "liked_by": [u["admin"], u["moderator"], u["nina"], u["arjun"], u["priya"]],
        "reported_by": [], "comments": [],
        "word_count": count_words("When the snow finally melted in March..."),
        "created_at": dt(10), "updated_at": dt(10),
    }}, upsert=True)

    c3a = ObjectId()
    db.stories.update_one({"_id": c3a}, {"$setOnInsert": {
        "_id": c3a, "title": "What the Snow Kept",
        "text": ("She was wearing summer clothes. A linen dress, sandals caked with old mud, "
                 "a straw hat with a willow ribbon. She wasn't shivering. When the eldest child "
                 "called out to her from the kitchen window, she turned and smiled as though she "
                 "had been expecting the call, as though she had been waiting there not for hours "
                 "but for months, which, of course, she had."),
        "kind": "continuation", "parent_id": root3, "root_id": root3,
        "ancestors": [root3], "depth": 1, "author_id": u["priya"],
        "genre": "Horror", "tags": ["winter", "stranger"],
        "visibility": "public", "status": "active",
        "stats": {"continuations": 0, "likes": 2, "views": 8},
        "liked_by": [u["sam"], u["nina"]], "reported_by": [], "comments": [],
        "word_count": count_words("She was wearing summer clothes..."),
        "created_at": dt(9), "updated_at": dt(9),
    }}, upsert=True)

    # ── Story 4: The Map With One Road Missing (private opening) ─────────────
    root4 = ObjectId()
    db.stories.update_one({"_id": root4}, {"$setOnInsert": {
        "_id": root4,
        "title": "The Map With One Road Missing",
        "text": ("The map came in an envelope with no stamp: every road in our district drawn "
                 "in fine ink, every road except the one I live on. I know that road exists. "
                 "I walk it every day. But the mapmaker left it out, and now I'm beginning to "
                 "wonder what they knew that I don't."),
        "kind": "opening", "parent_id": None, "root_id": root4,
        "ancestors": [], "depth": 0, "author_id": u["nina"],
        "genre": "Adventure", "tags": ["map", "mystery", "neighbourhood"],
        "visibility": "public", "status": "active",
        "stats": {"continuations": 0, "likes": 4, "views": 11},
        "liked_by": [u["moderator"], u["zoe"], u["ravi"], u["maya"]],
        "reported_by": [], "comments": [],
        "word_count": count_words("The map came in an envelope..."),
        "created_at": dt(6), "updated_at": dt(6),
    }}, upsert=True)

    # Private continuation (nina's own private branch)
    c4_priv = ObjectId()
    db.stories.update_one({"_id": c4_priv}, {"$setOnInsert": {
        "_id": c4_priv, "title": "The Map With One Road Missing",
        "text": ("I went to the post office. The postmaster looked at the envelope and turned "
                 "very pale. 'We don't deliver to your street,' he said. 'We never have.' He "
                 "refused to explain. On the way home, I noticed for the first time that there "
                 "was no post box on our street. There never had been."),
        "kind": "continuation", "parent_id": root4, "root_id": root4,
        "ancestors": [root4], "depth": 1, "author_id": u["nina"],
        "genre": "Adventure", "tags": ["map", "mystery"],
        "visibility": "private", "status": "active",
        "stats": {"continuations": 0, "likes": 0, "views": 0},
        "liked_by": [], "reported_by": [], "comments": [],
        "word_count": count_words("I went to the post office..."),
        "created_at": dt(5), "updated_at": dt(5),
    }}, upsert=True)

    # ── Story 5: Monsoon Exams ────────────────────────────────────────────────
    root5 = ObjectId()
    db.stories.update_one({"_id": root5}, {"$setOnInsert": {
        "_id": root5,
        "title": "Monsoon Exams",
        "text": ("The power went out ten minutes into the physics exam, and for the first time "
                 "in three years our whole class of forty-two sat together in the dark, listening "
                 "to the rain, and for a moment nobody cared about potential difference."),
        "kind": "opening", "parent_id": None, "root_id": root5,
        "ancestors": [], "depth": 0, "author_id": u["maya"],
        "genre": "Slice of Life", "tags": ["school", "monsoon", "friendship"],
        "visibility": "public", "status": "active",
        "stats": {"continuations": 0, "likes": 3, "views": 10},
        "liked_by": [u["admin"], u["sam"], u["priya"]],
        "reported_by": [], "comments": [],
        "word_count": count_words("The power went out ten minutes into the physics exam..."),
        "created_at": dt(4), "updated_at": dt(4),
    }}, upsert=True)

    # ── Story 6: Grandpa's Robot ──────────────────────────────────────────────
    root6 = ObjectId()
    db.stories.update_one({"_id": root6}, {"$setOnInsert": {
        "_id": root6,
        "title": "Grandpa's Robot",
        "text": ("Grandpa built a robot to help around the house, but he programmed it with "
                 "his own personality, so now we have two old men who refuse to admit they're "
                 "lost, argue with the TV, and insist that everything was cheaper in 1974."),
        "kind": "opening", "parent_id": None, "root_id": root6,
        "ancestors": [], "depth": 0, "author_id": u["arjun"],
        "genre": "Comedy", "tags": ["robot", "family", "comedy"],
        "visibility": "public", "status": "active",
        "stats": {"continuations": 1, "likes": 6, "views": 22},
        "liked_by": [u["admin"], u["moderator"], u["nina"], u["sam"], u["zoe"], u["ravi"]],
        "reported_by": [], "comments": [],
        "word_count": count_words("Grandpa built a robot to help around the house..."),
        "created_at": dt(3), "updated_at": dt(3),
    }}, upsert=True)

    c6a = ObjectId()
    db.stories.update_one({"_id": c6a}, {"$setOnInsert": {
        "_id": c6a, "title": "Grandpa's Robot",
        "text": ("The robot, whom Grandpa named Gopal, spent its first week reorganizing the "
                 "spice rack 'the way it was done properly.' On day eight it unionized the "
                 "kitchen appliances. The microwave now takes a twenty-minute lunch break and "
                 "the toaster has submitted a formal complaint about working conditions."),
        "kind": "continuation", "parent_id": root6, "root_id": root6,
        "ancestors": [root6], "depth": 1, "author_id": u["admin"],
        "genre": "Comedy", "tags": ["robot", "family", "comedy"],
        "visibility": "public", "status": "active",
        "stats": {"continuations": 0, "likes": 4, "views": 14},
        "liked_by": [u["arjun"], u["moderator"], u["maya"], u["sam"]],
        "reported_by": [], "comments": [],
        "word_count": count_words("The robot, whom Grandpa named Gopal..."),
        "created_at": dt(2), "updated_at": dt(2),
    }}, upsert=True)

    # ── Story 7: The Last Dragon's Tax Return ─────────────────────────────────
    root7 = ObjectId()
    db.stories.update_one({"_id": root7}, {"$setOnInsert": {
        "_id": root7,
        "title": "The Last Dragon's Tax Return",
        "text": ("The Royal Treasury had sent the dragon forty-one letters about unpaid taxes on "
                 "his hoard. The forty-second came with a dragon-sized subpoena and a very nervous "
                 "tax collector named Gerald, who was now standing in the mouth of the cave trying "
                 "to look official while not stepping in the gold."),
        "kind": "opening", "parent_id": None, "root_id": root7,
        "ancestors": [], "depth": 0, "author_id": u["arjun"],
        "genre": "Fantasy", "tags": ["dragon", "taxes", "comedy", "fantasy"],
        "visibility": "public", "status": "active",
        "stats": {"continuations": 3, "likes": 7, "views": 28},
        "liked_by": [u["admin"], u["moderator"], u["nina"], u["sam"], u["zoe"], u["ravi"], u["maya"]],
        "reported_by": [], "comments": [],
        "word_count": count_words("The Royal Treasury had sent the dragon forty-one letters..."),
        "created_at": dt(14), "updated_at": dt(14),
    }}, upsert=True)

    c7a = ObjectId()
    db.stories.update_one({"_id": c7a}, {"$setOnInsert": {
        "_id": c7a, "title": "The Last Dragon's Tax Return",
        "text": ("The dragon's name was Mireva, and she was three hundred and forty years old, "
                 "which meant she had outlasted seventeen tax systems and had receipts for all of "
                 "them. She reached one enormous claw into the hoard and produced a briefcase, "
                 "which Gerald took with shaking hands. It was full of dragons' personal finance "
                 "records, meticulously organized by century."),
        "kind": "continuation", "parent_id": root7, "root_id": root7,
        "ancestors": [root7], "depth": 1, "author_id": u["nina"],
        "genre": "Fantasy", "tags": ["dragon", "taxes", "comedy"],
        "visibility": "public", "status": "active",
        "stats": {"continuations": 1, "likes": 3, "views": 15},
        "liked_by": [u["arjun"], u["moderator"], u["zoe"]], "reported_by": [], "comments": [],
        "word_count": count_words("The dragon's name was Mireva..."),
        "created_at": dt(12), "updated_at": dt(12),
    }}, upsert=True)

    c7a2 = ObjectId()
    db.stories.update_one({"_id": c7a2}, {"$setOnInsert": {
        "_id": c7a2, "title": "The Last Dragon's Tax Return",
        "text": ("Gerald spent three weeks in the cave going through the records. By the end, he "
                 "determined that the kingdom owed Mireva a significant refund — specifically, one "
                 "hundred and twelve sheep claimed as business expenses in 1687, for which she had "
                 "every receipt. The Treasury paid. Gerald was promoted. Mireva framed the refund "
                 "notice and hung it above her hoard."),
        "kind": "ending", "parent_id": c7a, "root_id": root7,
        "ancestors": [root7, c7a], "depth": 2, "author_id": u["ravi"],
        "genre": "Fantasy", "tags": ["dragon", "taxes", "comedy"],
        "visibility": "public", "status": "active",
        "stats": {"continuations": 0, "likes": 4, "views": 12},
        "liked_by": [u["arjun"], u["nina"], u["sam"], u["maya"]],
        "reported_by": [], "comments": [],
        "word_count": count_words("Gerald spent three weeks in the cave..."),
        "created_at": dt(10), "updated_at": dt(10),
    }}, upsert=True)

    c7b = ObjectId()
    db.stories.update_one({"_id": c7b}, {"$setOnInsert": {
        "_id": c7b, "title": "The Last Dragon's Tax Return",
        "text": ("Gerald cleared his throat. 'Ms Mireva, the Crown acknowledges your hoard as "
                 "exempt under the Ancient Creatures Act of 1402, however—' She cut him off by "
                 "breathing a small, precise stream of fire that singed his papers without "
                 "touching him. 'I know the Act,' she said. 'I dictated it.'"),
        "kind": "continuation", "parent_id": root7, "root_id": root7,
        "ancestors": [root7], "depth": 1, "author_id": u["zoe"],
        "genre": "Fantasy", "tags": ["dragon", "taxes", "comedy"],
        "visibility": "public", "status": "active",
        "stats": {"continuations": 1, "likes": 3, "views": 11},
        "liked_by": [u["arjun"], u["admin"], u["moderator"]], "reported_by": [], "comments": [],
        "word_count": count_words("Gerald cleared his throat..."),
        "created_at": dt(11), "updated_at": dt(11),
    }}, upsert=True)

    c7b2 = ObjectId()
    db.stories.update_one({"_id": c7b2}, {"$setOnInsert": {
        "_id": c7b2, "title": "The Last Dragon's Tax Return",
        "text": ("Gerald went back to the capital and told the Treasurer what the dragon had "
                 "said. The Treasurer went pale. The Ancient Creatures Act had been misfiled as "
                 "a myth. They dug it out of the archive. Mireva had indeed dictated it. She had "
                 "also written herself in as the sole arbiter of disputes. The Kingdom quietly "
                 "dropped the case and issued a formal apology. Gerald got a raise."),
        "kind": "ending", "parent_id": c7b, "root_id": root7,
        "ancestors": [root7, c7b], "depth": 2, "author_id": u["sam"],
        "genre": "Fantasy", "tags": ["dragon", "taxes", "comedy"],
        "visibility": "public", "status": "active",
        "stats": {"continuations": 0, "likes": 2, "views": 9},
        "liked_by": [u["zoe"], u["arjun"]], "reported_by": [], "comments": [],
        "word_count": count_words("Gerald went back to the capital..."),
        "created_at": dt(9), "updated_at": dt(9),
    }}, upsert=True)

    c7c = ObjectId()
    db.stories.update_one({"_id": c7c}, {"$setOnInsert": {
        "_id": c7c, "title": "The Last Dragon's Tax Return",
        "text": ("Gerald decided to try a different approach. He sat down on the gold, opened "
                 "his own briefcase, and pulled out a counter-proposal: the dragon could pay "
                 "her taxes in stories instead of coin. One story per century, to be lodged with "
                 "the Royal Library. Mireva stared at him for a long time. Then she laughed, "
                 "which set the ceiling on fire, which Gerald also had to file a report about."),
        "kind": "continuation", "parent_id": root7, "root_id": root7,
        "ancestors": [root7], "depth": 1, "author_id": u["moderator"],
        "genre": "Fantasy", "tags": ["dragon", "taxes", "comedy"],
        "visibility": "public", "status": "active",
        "stats": {"continuations": 0, "likes": 5, "views": 13},
        "liked_by": [u["arjun"], u["nina"], u["admin"], u["zoe"], u["ravi"]],
        "reported_by": [], "comments": [],
        "word_count": count_words("Gerald decided to try a different approach..."),
        "created_at": dt(8), "updated_at": dt(8),
    }}, upsert=True)

    # ── Writing prompts ───────────────────────────────────────────────────────
    prompts = [
        {"text": "Begin with a locked door and no key.", "genre": "Mystery"},
        {"text": "Your character finds a letter addressed to them, dated ten years in the future.", "genre": "Sci-Fi"},
        {"text": "The last train has already left. Write what happens next.", "genre": "Thriller"},
        {"text": "Something ordinary becomes strange at exactly 3 a.m.", "genre": "Horror"},
        {"text": "Two people meet for the last time without knowing it.", "genre": "Slice of Life"},
        {"text": "The map is wrong, and that turns out to matter.", "genre": "Adventure"},
        {"text": "A machine does something its maker never intended.", "genre": "Comedy"},
        {"text": "Write the opening line of a story that ends with the words 'and that was enough.'", "genre": "Other"},
    ]
    for p in prompts:
        db.prompts.update_one(
            {"text": p["text"]},
            {"$setOnInsert": {**p, "created_at": dt(7)}},
            upsert=True
        )

    # Recompute derived fields for every passage: word counts and continuation counters
    for doc in db.stories.find({}, {"text": 1}):
        count = db.stories.count_documents(
            {"parent_id": doc["_id"], "visibility": "public", "status": "active"}
        )
        db.stories.update_one({"_id": doc["_id"]}, {"$set": {
            "word_count": count_words(doc["text"]),
            "stats.continuations": count,
        }})

    print(f"Seeded {db.users.count_documents({})} users, "
          f"{db.stories.count_documents({})} passages, "
          f"{db.prompts.count_documents({})} prompts.")

if __name__ == "__main__":
    main()
