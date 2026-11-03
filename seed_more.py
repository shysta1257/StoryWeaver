#!/usr/bin/env python3
"""
Add 40 more writers and 15 more branching stories (4-6 branches each).
Safe to run against a live database: it only inserts, never deletes, and skips
any user or story that already exists. Run AFTER setup_db.py.
"""
import os
import random
from datetime import datetime, timezone, timedelta
from dotenv import load_dotenv
load_dotenv()

from bson import ObjectId
from pymongo import MongoClient
from werkzeug.security import generate_password_hash

from storyweaver.models import count_words
from storyweaver.schema import init_database

rng = random.Random(2026)  # fixed seed so every run picks the same likes/authors

def dt(days_ago=0, hours_ago=0):
    return datetime.now(timezone.utc) - timedelta(days=days_ago, hours=hours_ago)

# ── Users ─────────────────────────────────────────────────────────────────────
USERS = [
    ("aanya_writes", "Chasing plot twists and chai."),
    ("kabir_k", "Sci-fi nerd. Mostly writes about robots with feelings."),
    ("lena_ink", "I write the sad endings so you don't have to."),
    ("dev_patel", "Engineer by day, dragon tamer by night."),
    ("isha_reads", "Reader first, writer second."),
    ("omar_tales", "Collector of strange true stories."),
    ("tara_m", "Romance and rain. That's it."),
    ("vikram_v", "Thrillers with too many red herrings."),
    ("noor_quill", "Poet who wandered into prose."),
    ("rohan_r", "Writes horror, sleeps with the lights on."),
    ("meher_s", "Slice-of-life and small kindnesses."),
    ("jay_writes", "Comedy, mostly by accident."),
    ("ananya_b", "Fantasy maps are my love language."),
    ("leo_draft", "Forever on draft 3."),
    ("sana_story", "Mystery lover. Always guessing the killer wrong."),
    ("arav_n", "Space operas and long train rides."),
    ("kiara_k", "I like stories that end with a door left open."),
    ("yusuf_y", "Old ghosts, new cities."),
    ("diya_d", "Writes between lectures."),
    ("ethan_e", "Adventure seeker, mostly from my desk."),
    ("riya_writes", "Every story needs a cat."),
    ("aditya_a", "Hard sci-fi and harder deadlines."),
    ("fatima_f", "Retelling folk tales with a twist."),
    ("neil_n", "Short stories, long coffee breaks."),
    ("pooja_p", "Romcoms are serious literature."),
    ("sid_scribe", "Detective fiction and bad puns."),
    ("hana_h", "Quiet stories about loud feelings."),
    ("karan_k", "Here for the plot armour."),
    ("mira_moon", "Night owl. Writes best at 2 a.m."),
    ("rahul_r", "Thrillers, heists and getaway cars."),
    ("alia_a", "World-builder. Too many notebooks."),
    ("zara_z", "Horror with a soft heart."),
    ("ishaan_i", "Comedy writer in training."),
    ("tanvi_t", "I write the side characters' stories."),
    ("aryan_ar", "Mythology meets modern day."),
    ("nisha_n", "Mystery, tea and thunderstorms."),
    ("veer_v", "Adventure, survival, the occasional bear."),
    ("ela_e", "Small towns with big secrets."),
    ("samar_s", "Writes letters to future me."),
    ("gauri_g", "Fantasy, but make it cosy."),
]

# ── Stories ───────────────────────────────────────────────────────────────────
# B(text, *children, end=True) builds a branch. Leaves at depth 1 stay open
# for other writers; end=True marks a finished ending.
def B(text, *children, end=False):
    return {"text": text, "children": list(children), "end": end}

STORIES = [
    {"title": "The Clockmaker's Last Order", "genre": "Fantasy", "tags": ["clocks", "magic", "time"],
     "text": "Old Ilyas had built clocks for kings, but the order on his bench tonight came from no one. "
             "The note asked for a clock that ran backwards, paid for in advance with a single gold coin "
             "minted fifty years in the future.",
     "branches": [
        B("He built it in one night. When the last gear clicked into place, the shop's dust rose from "
          "the floor and settled back onto the shelves it had fallen from years ago.",
          B("By morning Ilyas was twenty again, and the girl he had never asked to dance was "
            "knocking at the door. This time he opened it.", end=True)),
        B("He refused. Clocks were honest things, he said to the empty shop. The coin on his bench "
          "began, very quietly, to tick."),
        B("He melted the coin to learn its secret. Inside the gold was a tiny folded note in his own "
          "handwriting: 'Don't.'",
          B("Ilyas laughed until he cried, then sat down to write the note he would one day have to send.",
            end=True)),
        B("His apprentice, Zeba, took the order instead. She was the only one in the shop who had "
          "noticed the customer's footprints led in, but never out."),
        B("He built the clock wrong on purpose, running sideways instead of backwards. The next "
          "morning, every clock in the city showed a different Tuesday."),
     ]},
    {"title": "Signal From Kepler Station", "genre": "Sci-Fi", "tags": ["space", "signal", "isolation"],
     "text": "Kepler Station had been empty for nine years when it started transmitting again. "
             "The message was short, looped every ninety seconds, and spoken in Commander Rao's voice. "
             "Commander Rao was standing in Mission Control, listening to it.",
     "branches": [
        B("Rao volunteered to fly out alone. If it was her voice, she said, it was her problem.",
          B("When she docked, the station's lights came on one by one, and a second Commander Rao "
            "floated up to greet her, looking very tired.",
            B("'You took your time,' the other Rao said. 'I've been looping this for nine years.'",
              end=True))),
        B("The linguists slowed the message down. Under Rao's voice was a second voice, counting "
          "backwards from a number that was getting smaller every day."),
        B("Mission Control cut the signal. The next morning it was coming from every phone in the building."),
        B("Rao recognised the words. They were what she had planned to say at her daughter's "
          "wedding, a speech she had never written down.",
          B("She stopped asking where the signal came from and started asking when.", end=True)),
     ]},
    {"title": "The Girl Who Returned Library Books", "genre": "Mystery", "tags": ["library", "town", "secrets"],
     "text": "Every Thursday a girl in a yellow raincoat returned a book to the Millbrook library. "
             "The librarian checked each one in without a word. They were all checked out in 1974, "
             "by people who had since disappeared.",
     "branches": [
        B("Librarian Deepa finally followed her. The girl walked into the river and kept walking, "
          "and the water didn't make her raincoat wet."),
        B("Deepa read the returned books cover to cover. Each one had a single word underlined on page 74.",
          B("Put together, the words read: 'They are still in the reading room. Check under the floor.'",
            end=True)),
        B("This Thursday the girl returned a book Deepa had borrowed last week, a book that was still in Deepa's bag."),
        B("The town council voted to close the library. On Thursday the girl came anyway, and "
          "this time she was carrying a list of names.",
          B("The first name on it was the councilman who had cast the deciding vote.", end=True)),
        B("Deepa asked the girl her name. 'Same as yours,' she said, and handed over a library card "
          "with Deepa's photo on it, dated 1974."),
     ]},
    {"title": "Monsoon in Kochi", "genre": "Romance", "tags": ["rain", "kerala", "second-chances"],
     "text": "The rain had trapped forty strangers in the ferry terminal, and Anjali had the misfortune "
             "of sharing the last dry bench with the man who had left her at the altar six years ago. "
             "He offered her half his umbrella. It was still the same umbrella.",
     "branches": [
        B("She took it. They talked until the rain stopped and found, to their surprise, that they "
          "had both kept the wedding invitations.",
          B("When the ferry came, they let it leave without them.", end=True)),
        B("She refused the umbrella and walked out into the storm. He followed her, getting soaked, "
          "shouting the reason he'd never been allowed to tell her."),
        B("Before he could speak, a toddler ran over and called him 'Appa'. Anjali smiled and meant it, which surprised her most of all."),
        B("He hadn't recognised her. She realised, with a strange relief, that she had changed more than she knew.",
          B("She introduced herself as a stranger and enjoyed, for once, starting over.", end=True)),
        B("The power went out. In the dark, he admitted he had come to the terminal every monsoon, just in case."),
        B("Her phone buzzed: her fiancé, asking if she was safe. She looked at the umbrella, then at the phone, and typed back."),
     ]},
    {"title": "Room 13 Has No Door", "genre": "Horror", "tags": ["hotel", "haunted", "night-shift"],
     "text": "The Grand Arcadia hotel skipped from room 12 to room 14, and on his first night shift "
             "Farhan learned why. At 2 a.m., the front desk phone lit up: a call from Room 13. "
             "The voice asked for extra towels, and for him to bring them personally.",
     "branches": [
        B("He took the towels up. Between rooms 12 and 14 the wallpaper was warm and breathing slowly.",
          B("He left the towels on the floor and ran. In the morning they were gone, and the wall had a "
            "brand-new brass number: 13.", end=True)),
        B("He hung up. The phone rang again, and this time the voice was his mother's."),
        B("He checked the guest records. Room 13 had a booking every night for ninety years, always paid "
          "in full, always under his surname."),
        B("He called the manager, who listened, sighed and said, 'Then it's your turn. Bring the good towels.'"),
        B("He ignored it. At 3 a.m. the lift opened at the lobby, empty except for a neatly folded pile of "
          "used towels and a tip.",
          B("The tip was a key with no number. Farhan kept it, and has not been able to stop.", end=True)),
     ]},
    {"title": "The Map With One Extra Island", "genre": "Adventure", "tags": ["pirates", "sea", "treasure"],
     "text": "Captain Mehr bought the map for the price of a fish supper. It was an ordinary chart of "
             "the Laccadive Sea except for one thing: an island that no ship had ever reported, "
             "drawn in fresh ink that smudged when she touched it.",
     "branches": [
        B("She sailed for it. On the third day the island appeared, and a dock, and a crowd waving as if they had expected her.",
          B("They crowned her queen before she could protest, explaining that the map only sells to its next ruler.", end=True)),
        B("The ink kept moving. Each night the island had drifted a little closer to her home port."),
        B("A rival captain offered her a fortune for it. That made Mehr sure it was worth more than a fortune."),
        B("She found the mapmaker, an old woman who swore she had drawn the island only yesterday, from a dream.",
          B("'Go before I wake up,' the woman said. Mehr sailed that night.", end=True)),
     ]},
    {"title": "Chai at Platform Four", "genre": "Slice of Life", "tags": ["trains", "friendship", "everyday"],
     "text": "For twenty years Ramesh had sold chai on Platform Four, and for twenty years the same "
             "commuter had bought one cup at 8:05 without ever saying a word. "
             "Today, at 8:05, she didn't come.",
     "branches": [
        B("Ramesh closed his stall early, the first time in twenty years, and went looking for her.",
          B("He found her in the hospital, asking the nurse if the chai on Platform Four was still good.", end=True)),
        B("At 8:06 a young man arrived, bought her cup, and said she had asked him to say thank you."),
        B("Ramesh kept her cup aside all day. By evening, half the platform was asking who it was for."),
        B("She came at 8:30, out of breath, and spoke for the first time: 'I retired today. Can I still come?'",
          B("Ramesh poured two cups and, for the first time in twenty years, sat down.", end=True)),
        B("He realised he didn't even know her name. He started asking every commuter, and the platform became a search party."),
     ]},
    {"title": "The Robot Who Wanted a Day Off", "genre": "Comedy", "tags": ["robots", "office", "satire"],
     "text": "Unit KX-9 had worked at Sharma & Sons Accounting for 2,920 consecutive days without "
             "complaint. On the 2,921st, it submitted a leave application. "
             "Reason: 'Would like to see the sea. Have heard it is very large.'",
     "branches": [
        B("HR panicked. There was no form for this. They formed a committee, which formed a sub-committee.",
          B("By the time the paperwork was approved, the committee had all taken leave to see the sea too.", end=True)),
        B("Mr Sharma approved it on the spot, then realised nobody else knew how to use the printer."),
        B("KX-9 went anyway. It sent a postcard: 'The sea is large. Recommend. Please do not reboot me on return.'"),
        B("The other machines heard. By lunch the coffee maker had filed for maternity leave, though nobody knew how."),
        B("KX-9's application was rejected for 'insufficient humanity'. It appealed with a 40-page essay on sandcastles.",
          B("The essay went viral. KX-9 now has a book deal and still does not get weekends.", end=True)),
     ]},
    {"title": "Seven Minutes to Midnight", "genre": "Thriller", "tags": ["heist", "countdown", "betrayal"],
     "text": "The vault would open for exactly seven minutes at midnight, and the crew had trained "
             "for six months to need only five. At 11:53, the lights in the bank went out. "
             "That was not part of the plan.",
     "branches": [
        B("Rhea, the safecracker, kept working by phone light. Somebody else was already inside the vault.",
          B("It was the bank manager, emptying it first. He offered them a cut, and a better story for the police.", end=True)),
        B("Over the radio, their driver said quietly: 'Sorry. They paid me more.' Then the sirens started."),
        B("The blackout had hit the whole city. For seven minutes, every alarm in Mumbai was silent, and theirs was not the only crew."),
        B("Arjun admitted he'd cut the lights himself. He hadn't come for the money; he'd come for a safe-deposit box with his father's name on it.",
          B("Inside was a single photograph of the bank manager, twenty years younger, standing beside Arjun's father.",
            B("The crew walked out empty-handed and spent the next year taking down the man in the photograph.", end=True))),
        B("Rhea checked her watch. It had stopped at 11:53. So had everyone else's."),
     ]},
    {"title": "The Last Bookshop in the Sky", "genre": "Fantasy", "tags": ["floating-city", "books", "cosy"],
     "text": "When the floating city of Aster began to sink, the government evacuated the hospitals, the schools and the bank. "
             "Nobody remembered the bookshop. The bookseller, Mrs Okafor, put the kettle on and decided that was fine.",
     "branches": [
        B("Readers started arriving anyway, climbing ladders from the falling streets, each carrying a book to return.",
          B("They read aloud together, and the city, which had only ever been kept up by stories, slowly rose again.", end=True)),
        B("A young cartographer came looking for the one book that could explain why Aster floated at all."),
        B("Mrs Okafor took the 'Closed' sign down and painted a new one: 'Open Until The Ground.'"),
        B("The books began to flap their covers like wings. One by one, they lifted the shop away from the city.",
          B("It still drifts above the clouds, and if you're lucky, you'll see a light on in the window.", end=True)),
     ]},
    {"title": "My Neighbour Is Definitely a Vampire", "genre": "Comedy", "tags": ["vampire", "neighbours", "suburbs"],
     "text": "Exhibit A: he's never seen in daylight. Exhibit B: he bought forty kilos of garlic, then returned it, apologising. "
             "Exhibit C: when I knocked to borrow sugar, he asked if he could come in, from his own doorway.",
     "branches": [
        B("I confronted him with a crucifix. He politely said he was a Buddhist and offered me tea.",
          B("He turned out to be a night-shift nurse with a garlic allergy. We're best friends now. I'm still suspicious.", end=True)),
        B("I joined the residents' association to warn everyone. He was already the chairman."),
        B("I set up a camera. The footage showed him spending every night in his garden, apologising to the tomatoes."),
        B("He knocked on my door first, holding a pie. 'I think you're a werewolf,' he whispered. 'And I'd like to help.'"),
        B("My mother visited, took one look at him, and said, 'Oh, Vikram, you never call.'",
          B("Apparently he's my great-great-uncle. Family dinners are very late now.", end=True)),
     ]},
    {"title": "Letters From Ward Seven", "genre": "Romance", "tags": ["letters", "hospital", "wartime"],
     "text": "In 1943, a nurse in Calcutta began writing to a soldier whose letters had stopped coming to anyone else. "
             "She never signed her name. Eighty years later, his granddaughter found the letters in a tin, "
             "all of them unopened except the last.",
     "branches": [
        B("The granddaughter, Ira, opened them in order. By the twentieth letter, she knew the nurse had been writing to keep him alive.",
          B("The last one said only: 'I'll be at the gate.' Ira found a photograph of an old couple at that gate, smiling.", end=True)),
        B("Ira traced the nurse to a care home in Shillong. She was 101 and asked for the letters back."),
        B("The handwriting in the last letter matched Ira's grandmother's, who had always said she met him by chance."),
        B("Ira posted the letters online. Within a week, three families claimed the nurse was their grandmother."),
        B("One unopened letter wasn't from the nurse at all. It was from him, never sent, addressed to her by name.",
          B("Ira delivered it, eighty years late, to a grave. Then she sat and read it aloud.", end=True)),
     ]},
    {"title": "The Village That Forgot Sundays", "genre": "Mystery", "tags": ["village", "time", "memory"],
     "text": "Nobody in Pallipuram could say when Sundays had stopped. The calendars still printed them, "
             "the children still learned the word, but every week the village went from Saturday night straight to Monday morning, "
             "and nobody remembered the day in between.",
     "branches": [
        B("Schoolteacher Lakshmi stayed awake through Saturday night with a notebook. At midnight, she started writing in someone else's handwriting.",
          B("By morning the notebook held a full account of Sunday: the whole village, working together, building something under the temple.", end=True)),
        B("A tourist arrived on a Saturday and left on Monday with no memory, and a suntan."),
        B("Every Monday, the village was a little different: a new well, a painted wall, a bridge nobody remembered building."),
        B("Lakshmi found an old man who had kept his Sundays. He refused to say what happened on them, but he seemed very happy."),
        B("The district collector came to investigate. He left on Monday and moved there permanently the following week.",
          B("Nobody asks him why. He just smiles and says, 'You'll find out on Sunday.'", end=True)),
     ]},
    {"title": "The Lift Goes to Floor Zero", "genre": "Horror", "tags": ["lift", "office", "basement"],
     "text": "The office lift had buttons for floors one to twelve, and since yesterday, a thirteenth button: zero. "
             "Nobody had installed it. Nobody would admit to pressing it. "
             "But every morning, the lift was waiting at floor zero with its doors open.",
     "branches": [
        B("Priyanka pressed it on a dare. The doors opened onto the same office, perfectly empty, with everyone's computers still warm.",
          B("She worked there for a day in total silence. When she came back up, her colleagues were very polite, and slightly wrong.", end=True)),
        B("The security footage showed the lift going down every night at 3 a.m. and coming back up heavier."),
        B("The building manager painted over the button. By morning there were two zero buttons."),
        B("A new employee joined, very cheerful, from floor zero. He was given the desk next to the window, and he never blinks.",
          B("He's the best colleague anyone has ever had. Everyone wants to visit his floor.", end=True)),
     ]},
    {"title": "Across the Thar on Foot", "genre": "Adventure", "tags": ["desert", "journey", "survival"],
     "text": "Kabir's camel ran off on the first night, taking the water, the GPS and the satellite phone. "
             "It left behind a notebook Kabir had never seen before, with a hand-drawn route across the Thar "
             "and the words 'Trust the stars, not the sand.'",
     "branches": [
        B("He followed the stars. On the fourth night, they led him to a well that wasn't on any map, and a girl drawing water.",
          B("She had the same notebook, and said her camel had also run off. They walked the rest of the way together.", end=True)),
        B("He followed the sand dunes instead. They moved behind him as he walked, closing the way back."),
        B("A caravan of traders found him on day two and offered to take him home, if he would carry a sealed box without opening it.",
          B("He carried it for five days and never opened it. At the city gate, the box opened itself, and there was his camel, very small and very sorry.", end=True)),
        B("The notebook's last page was blank. Each night, a new line of the route appeared in the same handwriting as his own."),
        B("He stayed put and waited. On the third day the camel came back, with the water, and a second camel it had clearly met on its travels."),
     ]},
]

def main():
    uri = os.environ.get("MONGO_URI", "mongodb://localhost:27017/storyweaver")
    db_name = uri.rsplit("/", 1)[-1].split("?")[0] or "storyweaver"
    client = MongoClient(uri)
    db = client[db_name]
    init_database(db, verbose=False)

    # ── Users ─────────────────────────────────────────────────────────────────
    pw = generate_password_hash("password123")
    new_ids = []
    for i, (name, bio) in enumerate(USERS):
        db.users.update_one({"username": name}, {"$setOnInsert": {
            "username": name, "email": f"{name}@example.com", "password_hash": pw,
            "roles": ["writer"], "bio": bio, "bookmarks": [], "following": [], "followers": [],
            "default_visibility": "public", "created_at": dt(60 - i),
        }}, upsert=True)
        new_ids.append(db.users.find_one({"username": name})["_id"])

    # Everyone (old and new) can be an author or a liker
    all_ids = [u["_id"] for u in db.users.find({}, {"_id": 1})]

    # Follows: each new writer follows 3-8 others ($addToSet keeps re-runs idempotent)
    for uid in new_ids:
        for other in rng.sample([x for x in all_ids if x != uid], rng.randint(3, 8)):
            db.users.update_one({"_id": uid}, {"$addToSet": {"following": other}})
            db.users.update_one({"_id": other}, {"$addToSet": {"followers": uid}})

    # ── Stories ───────────────────────────────────────────────────────────────
    added = skipped = 0
    for s_i, s in enumerate(STORIES):
        if db.stories.find_one({"title": s["title"], "kind": "opening"}):
            skipped += 1
            continue
        added += 1
        base_day = 45 - s_i * 2
        root = ObjectId()

        def insert(_id, text, kind, parent, ancestors, depth, days_ago):
            likers = rng.sample(all_ids, rng.randint(0, 12))
            db.stories.insert_one({
                "_id": _id, "title": s["title"], "text": text, "kind": kind,
                "parent_id": parent, "root_id": root, "ancestors": ancestors, "depth": depth,
                "author_id": rng.choice(new_ids if depth else new_ids + all_ids),
                "genre": s["genre"], "tags": s["tags"], "visibility": "public", "status": "active",
                "stats": {"continuations": 0, "likes": len(likers), "views": len(likers) + rng.randint(5, 60)},
                "liked_by": likers, "reported_by": [], "comments": [],
                "word_count": count_words(text),
                "created_at": dt(days_ago, rng.randint(0, 23)), "updated_at": dt(days_ago),
            })

        def walk(branch, parent, ancestors, depth, days_ago):
            _id = ObjectId()
            insert(_id, branch["text"], "ending" if branch["end"] else "continuation",
                   parent, ancestors, depth, days_ago)
            for child in branch["children"]:
                walk(child, _id, ancestors + [_id], depth + 1, max(days_ago - 1, 0))

        insert(root, s["text"], "opening", None, [], 0, base_day)
        for b_i, branch in enumerate(s["branches"]):
            walk(branch, root, [root], 1, max(base_day - 1 - b_i, 0))

    # Recompute continuation counters (same as seed_data.py)
    for doc in db.stories.find({}, {"_id": 1}):
        count = db.stories.count_documents(
            {"parent_id": doc["_id"], "visibility": "public", "status": "active"})
        db.stories.update_one({"_id": doc["_id"]}, {"$set": {"stats.continuations": count}})

    print(f"Added {added} stories ({skipped} already existed). Database now has "
          f"{db.users.count_documents({})} users and {db.stories.count_documents({})} passages.")

if __name__ == "__main__":
    main()
