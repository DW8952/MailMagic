"""
=============================================================================
 economy.py  --  points, chests, the shop and upgrades
=============================================================================
This is where you tune how generous the game is. Every number that decides
"how long until I get a legendary" lives here or at the top of cards.py.
"""

import random
import time

import cards
import storage


# --------------------------------------------------------------------------
# CHESTS
# --------------------------------------------------------------------------
# name -> (price, number of cards, guaranteed minimum rarity in one slot)
CHESTS = {
    "Wooden Chest": (100, 3, cards.RARE),
    "Iron Chest": (250, 5, cards.EPIC),
    "Dragon Hoard": (600, 8, cards.LEGENDARY),
}

# Duplicates you already own are still useful: they are the fuel for upgrades.
# A duplicate of a card you own at max copies also refunds a few points.
DUPE_REFUND = {cards.COMMON: 5, cards.RARE: 12, cards.EPIC: 25,
               cards.LEGENDARY: 60}


def open_chest(profile, chest_name):
    """Roll the loot, put it in the collection, return a list of
    (card, is_new, refund) so the menu can show a nice reveal."""
    price, count, floor = CHESTS[chest_name]
    if profile["points"] < price:
        return None
    profile["points"] -= price
    profile["chests_opened"] += 1

    pulls = []
    for slot in range(count):
        # the last slot is the guaranteed good one
        forced = floor if slot == count - 1 else None
        card = cards.random_card(random, floor=forced)
        is_new = storage.add_card(profile, card["id"], 1)
        refund = 0
        entry = profile["collection"][card["id"]]
        if not is_new and entry["copies"] > 8:
            refund = DUPE_REFUND[card["rarity"]]
            profile["points"] += refund
        pulls.append((card, is_new, refund))
    return pulls


# --------------------------------------------------------------------------
# THE SHOP
# --------------------------------------------------------------------------
# The shop rerolls every time the game is launched. If you would rather it
# reroll once per day, swap the seed line in roll_shop() for the dated one.
SHOP_SLOTS = 5


def roll_shop(profile):
    seed = int(time.time() * 1000) % 100000 + len(profile["collection"])
    # daily version instead:
    # seed = hash(time.strftime("%Y-%m-%d") + profile["name"]) % 100000
    rng = random.Random(seed)

    offers = []
    for slot in range(SHOP_SLOTS):
        floor = cards.EPIC if slot == 0 else None       # one fancy slot
        card = cards.random_card(rng, floor=floor)
        price = cards.price_of(card)
        price = int(price * rng.uniform(0.85, 1.15))
        offers.append({"card_id": card["id"], "price": price,
                       "sold": False, "discount": False})

    # one random slot goes on sale
    lucky = rng.randrange(len(offers))
    offers[lucky]["price"] = int(offers[lucky]["price"] * 0.6)
    offers[lucky]["discount"] = True
    return offers


def buy_offer(profile, offer):
    if offer["sold"]:
        return False, "Already sold."
    if profile["points"] < offer["price"]:
        return False, "Not enough points."
    profile["points"] -= offer["price"]
    offer["sold"] = True
    card = cards.get_card(offer["card_id"])
    is_new = storage.add_card(profile, card["id"], 1)
    return True, "%s added to your collection.%s" % (
        card["name"], "  (NEW!)" if is_new else "")


# --------------------------------------------------------------------------
# UPGRADES
# --------------------------------------------------------------------------
def upgrade_info(profile, card_id):
    """Return (can_upgrade, next_level, copies_needed, points_needed, reason)."""
    entry = profile["collection"].get(card_id)
    if entry is None:
        return False, 0, 0, 0, "You do not own this card."
    level = entry["level"]
    if level >= cards.MAX_LEVEL:
        return False, level, 0, 0, "Already at max level."
    need_copies, need_points = cards.UPGRADE_COST[level + 1]
    # the copy in your collection that you actually play does not count as fuel
    spare = entry["copies"] - 1
    if spare < need_copies:
        return (False, level + 1, need_copies, need_points,
                "Need %d spare copies, you have %d." % (need_copies, spare))
    if profile["points"] < need_points:
        return (False, level + 1, need_copies, need_points,
                "Need %d points." % need_points)
    return True, level + 1, need_copies, need_points, ""


def do_upgrade(profile, card_id):
    ok, level, need_copies, need_points, reason = upgrade_info(profile, card_id)
    if not ok:
        return False, reason
    entry = profile["collection"][card_id]
    entry["copies"] -= need_copies
    entry["level"] = level
    profile["points"] -= need_points
    card = cards.get_card(card_id)
    return True, "%s is now level %d (%s)." % (
        card["name"], level, cards.stat_line(card, level) or "stronger spell")


# --------------------------------------------------------------------------
# MATCH REWARDS
# --------------------------------------------------------------------------
REWARDS = {
    # mode -> (points for a win, points for a loss)
    "easy": (18, 6),
    "normal": (28, 9),
    "hard": (45, 14),
    "duel": (55, 18),
    "hotseat": (35, 12),
}


def reward_for(mode, won):
    win_points, loss_points = REWARDS.get(mode, (20, 8))
    base = win_points if won else loss_points
    return base + random.randint(0, 5)
