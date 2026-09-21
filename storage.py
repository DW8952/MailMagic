"""
=============================================================================
 storage.py  --  player profiles on disk
=============================================================================
Every player gets one JSON file inside the `playerdata` folder that sits
next to the game (or next to the .exe once you compile it):

    game folder/
        game.exe          <- or main.py while you are developing
        playerdata/
            luke.json
            girlfriend.json

When you mail the game to each other, zip the WHOLE folder so both profiles
travel together. That is what makes the "send it back and forth" loop work.
"""

import hashlib
import json
import os
import re
import sys
import time

import cards


# --------------------------------------------------------------------------
# WHERE THE FILES LIVE
# --------------------------------------------------------------------------
def base_dir():
    """Folder of the .exe when frozen by PyInstaller, else folder of this file."""
    if getattr(sys, "frozen", False):
        return os.path.dirname(os.path.abspath(sys.executable))
    return os.path.dirname(os.path.abspath(__file__))


DATA_DIR = os.path.join(base_dir(), "playerdata")


def ensure_dirs():
    if not os.path.isdir(DATA_DIR):
        os.makedirs(DATA_DIR)


def safe_name(name):
    """Turn 'My Name!' into 'my_name' so it is a legal filename."""
    slug = re.sub(r"[^a-z0-9_]+", "_", name.strip().lower())
    return slug.strip("_") or "player"


def profile_path(name):
    return os.path.join(DATA_DIR, safe_name(name) + ".json")


def list_profiles():
    """Return a list of loaded player dicts, newest-played first."""
    ensure_dirs()
    out = []
    for fname in os.listdir(DATA_DIR):
        if not fname.endswith(".json"):
            continue
        try:
            with open(os.path.join(DATA_DIR, fname), "r", encoding="utf-8") as fh:
                out.append(migrate(json.load(fh)))
        except Exception:
            continue          # ignore corrupt files instead of crashing
    out.sort(key=lambda p: p.get("last_played", 0), reverse=True)
    return out


# --------------------------------------------------------------------------
# PASSWORDS (not real security -- just stops casual peeking at each other)
# --------------------------------------------------------------------------
def hash_pw(password):
    if not password:
        return ""
    return hashlib.sha256(("saltyrunes::" + password).encode("utf-8")).hexdigest()


def check_pw(profile, password):
    stored = profile.get("password", "")
    if not stored:
        return True
    return hash_pw(password) == stored


# --------------------------------------------------------------------------
# THE PROFILE ITSELF
# --------------------------------------------------------------------------
def blank_profile(name, password=""):
    profile = {
        "name": name.strip() or "Player",
        "password": hash_pw(password),
        "created": time.time(),
        "last_played": time.time(),
        "points": 150,
        "wins": 0,
        "losses": 0,
        "defense_wins": 0,
        "defense_losses": 0,
        "chests_opened": 0,
        # collection: card_id -> {"copies": n, "level": n}
        "collection": {},
        "deck": [],
        "inbox": [],
        "history": [],
    }
    for card_id, copies in cards.STARTER_COLLECTION.items():
        if cards.get_card(card_id):
            profile["collection"][card_id] = {"copies": copies, "level": 1}
    profile["deck"] = auto_build_deck(profile)
    return profile


def migrate(profile):
    """Add any keys that are missing -- keeps old save files working when
    you add new features later."""
    template = {
        "name": "Player", "password": "", "created": time.time(),
        "last_played": 0, "points": 0, "wins": 0, "losses": 0,
        "defense_wins": 0, "defense_losses": 0, "chests_opened": 0,
        "collection": {}, "deck": [], "inbox": [], "history": [],
    }
    for key, value in template.items():
        profile.setdefault(key, value)

    # drop cards that no longer exist in cards.py (e.g. you renamed an id)
    profile["collection"] = {
        cid: entry for cid, entry in profile["collection"].items()
        if cards.get_card(cid)
    }
    for entry in profile["collection"].values():
        entry.setdefault("copies", 1)
        entry.setdefault("level", 1)
    profile["deck"] = [cid for cid in profile["deck"] if cards.get_card(cid)]
    return profile


def save(profile):
    ensure_dirs()
    profile["last_played"] = time.time()
    path = profile_path(profile["name"])
    tmp = path + ".tmp"
    with open(tmp, "w", encoding="utf-8") as fh:
        json.dump(profile, fh, indent=2)
    os.replace(tmp, path)       # atomic-ish, so a crash never eats a save


def load(name):
    path = profile_path(name)
    if not os.path.exists(path):
        return None
    with open(path, "r", encoding="utf-8") as fh:
        return migrate(json.load(fh))


def create(name, password=""):
    profile = blank_profile(name, password)
    save(profile)
    return profile


# --------------------------------------------------------------------------
# COLLECTION HELPERS
# --------------------------------------------------------------------------
def owned(profile, card_id):
    return profile["collection"].get(card_id)


def level_of(profile, card_id):
    entry = profile["collection"].get(card_id)
    return entry["level"] if entry else 1


def add_card(profile, card_id, copies=1):
    """Returns True if this was a brand new card."""
    entry = profile["collection"].get(card_id)
    if entry is None:
        profile["collection"][card_id] = {"copies": copies, "level": 1}
        return True
    entry["copies"] += copies
    return False


def owned_cards(profile, sort="cost"):
    """List of (card_dict, entry) for everything the player owns."""
    items = []
    for card_id, entry in profile["collection"].items():
        card = cards.get_card(card_id)
        if card:
            items.append((card, entry))
    if sort == "cost":
        items.sort(key=lambda t: (t[0]["cost"], t[0]["name"]))
    elif sort == "rarity":
        items.sort(key=lambda t: (cards.RARITIES.index(t[0]["rarity"]),
                                  t[0]["cost"], t[0]["name"]))
    else:
        items.sort(key=lambda t: t[0]["name"])
    return items


def deck_counts(profile):
    counts = {}
    for card_id in profile["deck"]:
        counts[card_id] = counts.get(card_id, 0) + 1
    return counts


def deck_is_legal(profile):
    """Return (ok, message)."""
    deck = profile["deck"]
    if len(deck) != cards.DECK_SIZE:
        return False, "Your deck has %d/%d cards." % (len(deck), cards.DECK_SIZE)
    for card_id, count in deck_counts(profile).items():
        card = cards.get_card(card_id)
        if card is None:
            return False, "Unknown card in deck: %s" % card_id
        if card_id not in profile["collection"]:
            return False, "You no longer own %s." % card["name"]
        if count > cards.max_copies(card):
            return False, "Too many copies of %s." % card["name"]
    return True, "Deck is legal."


def auto_build_deck(profile):
    """Fill a legal 20 card deck out of whatever the player owns.
    Prefers a sane mana curve (cheap cards first, a few big ones)."""
    pool = []
    for card, _entry in owned_cards(profile):
        for _ in range(cards.max_copies(card)):
            pool.append(card)
    # sort by cost so we grab a curve, but keep a little randomness of order
    pool.sort(key=lambda card: (card["cost"], card["name"]))
    deck = [card["id"] for card in pool[:cards.DECK_SIZE]]
    return deck


def build_battle_deck(profile):
    """Turn the saved deck list into [(card_dict, level), ...] for battle.py."""
    out = []
    for card_id in profile["deck"]:
        card = cards.get_card(card_id)
        if card:
            out.append((card, level_of(profile, card_id)))
    return out


# --------------------------------------------------------------------------
# MAIL / NEWS between the two of you
# --------------------------------------------------------------------------
def notify(profile, message):
    profile["inbox"].append({"time": time.time(), "text": message})
    profile["inbox"] = profile["inbox"][-30:]


def log_match(profile, message):
    profile["history"].append({"time": time.time(), "text": message})
    profile["history"] = profile["history"][-30:]


def stamp(ts):
    return time.strftime("%d %b %H:%M", time.localtime(ts))
