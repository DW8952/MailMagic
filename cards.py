"""
=============================================================================
 cards.py  --  THE CARD DATABASE
=============================================================================
This is the ONLY file you need to touch to add new cards.
Everything else (battles, shop, chests, upgrades) reads from here.

-----------------------------------------------------------------------------
HOW TO ADD A CARD
-----------------------------------------------------------------------------
Copy this template to the bottom of the CARDS list and change the values:

    {
        "id":       "unique_snake_case_id",   # never reuse an id
        "name":     "Pretty Name",
        "type":     "creature",               # "creature" or "spell"
        "cost":     3,                        # mana cost
        "attack":   2,                        # creatures only
        "health":   4,                        # creatures only
        "rarity":   RARE,                     # COMMON / RARE / EPIC / LEGENDARY
        "keywords": ["guard"],                # see KEYWORDS below
        "text":     "Guard. When played, draw a card.",
        "flavor":   "Something funny here.",  # optional
        "effects":  [
            {"trigger": "play", "action": "draw", "amount": 1},
        ],
    },

-----------------------------------------------------------------------------
KEYWORDS (always-on abilities)
-----------------------------------------------------------------------------
    guard         Enemies must attack this before your hero or other minions.
    rush          Can attack the turn it is played.
    lifesteal     Damage it deals also heals your hero.
    poison        Any minion it damages is destroyed.
    thorns        Deals 1 extra damage back when attacked.
    pierce        Excess damage from a kill spills onto the enemy hero.
    shield        Ignores the first instance of damage it takes.
    stealth       Cannot be attacked or targeted until it attacks once.
    regenerate    Heals 1 at the start of your turn.
    double_strike Can attack twice per turn.

-----------------------------------------------------------------------------
EFFECTS (triggered abilities)
-----------------------------------------------------------------------------
Each effect is a dict. Keys:

  "trigger":  when it fires
      play         -> when this creature is summoned / this spell is cast
      death        -> when this creature dies
      turn_start   -> at the start of its controller's turn
      turn_end     -> at the end of its controller's turn
      attack       -> when this creature attacks
      hurt         -> when this creature survives damage
      kill         -> when this creature kills another creature
      ally_death   -> when another friendly creature dies
      ally_summon  -> when another friendly creature is summoned

  "action":   what it does
      damage      amount
      heal        amount
      buff        attack / health  (permanent stat change)
      draw        amount
      summon      card (an id from this file) + amount (how many)
      destroy     (kill outright, ignores shield? no -- shield still blocks nothing,
                   destroy is absolute)
      stun        target loses its next attack
      grant       keyword (give a keyword to the target)
      mana        amount (temporary mana this turn)

  "target":   who it hits (default "enemy_hero" for damage, "self" for buff)
      self                 this creature
      own_hero             your hero
      enemy_hero           their hero
      own_minions          all your creatures
      other_own_minions    all your creatures except this one
      enemy_minions        all their creatures
      all_minions          everything on the board
      own_random           a random friendly creature
      enemy_random         a random enemy creature
      enemy_random_any     a random enemy creature OR their hero
      enemy_all            all enemy creatures AND their hero
      enemy_strongest      the enemy creature with the highest attack
      enemy_target         YOU PICK: an enemy creature or their hero
      enemy_minion_target  YOU PICK: an enemy creature
      own_minion_target    YOU PICK: a friendly creature

  "times":    repeat the effect N times (great for random damage). Default 1.
  "scales":   set to False if card LEVEL should not increase the amount.

A card can have as many effects as you want -- they resolve in order.
=============================================================================
"""

import random

# --------------------------------------------------------------------------
# RARITY + ECONOMY CONSTANTS  (tweak these to rebalance the whole game)
# --------------------------------------------------------------------------
COMMON = "common"
RARE = "rare"
EPIC = "epic"
LEGENDARY = "legendary"

RARITIES = [COMMON, RARE, EPIC, LEGENDARY]

# Chance of pulling each rarity from a chest slot
RARITY_WEIGHT = {COMMON: 66, RARE: 25, EPIC: 7, LEGENDARY: 2}

# Shop price per rarity (a small random wobble is added in economy.py)
RARITY_PRICE = {COMMON: 45, RARE: 110, EPIC: 220, LEGENDARY: 420}

# How many copies of a card you may put in one deck
MAX_COPIES = {COMMON: 2, RARE: 2, EPIC: 2, LEGENDARY: 1}

# Upgrading:  level -> (duplicate copies needed, points needed)
# A card at level N gets +(N-1)/+(N-1) stats, and spells get +(N-1) to amounts.
MAX_LEVEL = 5
UPGRADE_COST = {
    2: (2, 60),
    3: (3, 150),
    4: (4, 320),
    5: (6, 600),
}

# Rules of the game itself
DECK_SIZE = 20
HERO_HP = 25
MAX_MANA = 10
BOARD_LIMIT = 6
HAND_LIMIT = 8

# --------------------------------------------------------------------------
# THE CARDS
# --------------------------------------------------------------------------
CARDS = [

    # ======================= TOKENS (not collectible) =====================
    {"id": "rat", "name": "Sewer Rat", "type": "creature", "cost": 1,
     "attack": 1, "health": 1, "rarity": COMMON, "collectible": False,
     "text": "", "flavor": "It found you first."},

    {"id": "skeleton", "name": "Skeleton", "type": "creature", "cost": 2,
     "attack": 2, "health": 2, "rarity": COMMON, "collectible": False,
     "text": "", "flavor": "Rattles ominously."},

    {"id": "treant", "name": "Treant Sapling", "type": "creature", "cost": 2,
     "attack": 2, "health": 2, "rarity": COMMON, "collectible": False,
     "keywords": ["guard"], "text": "Guard."},

    {"id": "spark", "name": "Spark", "type": "creature", "cost": 1,
     "attack": 1, "health": 1, "rarity": COMMON, "collectible": False,
     "keywords": ["rush"], "text": "Rush."},

    # ============================== COMMON ================================
    {"id": "glimmer_wisp", "name": "Glimmer Wisp", "type": "creature", "cost": 0,
     "attack": 1, "health": 2, "rarity": COMMON,
     "text": "", "flavor": "Free, and almost worth it."},

    {"id": "ember_imp", "name": "Ember Imp", "type": "creature", "cost": 1,
     "attack": 2, "health": 1, "rarity": COMMON,
     "text": "Play: deal 1 damage to the enemy hero.",
     "flavor": "Small hands, big matches.",
     "effects": [{"trigger": "play", "action": "damage",
                  "target": "enemy_hero", "amount": 1}]},

    {"id": "pebble_pup", "name": "Pebble Pup", "type": "creature", "cost": 1,
     "attack": 1, "health": 3, "rarity": COMMON, "keywords": ["guard"],
     "text": "Guard.", "flavor": "Loyal. Extremely heavy."},

    {"id": "flame_bolt", "name": "Flame Bolt", "type": "spell", "cost": 1,
     "rarity": COMMON,
     "text": "Deal 2 damage to a target.",
     "effects": [{"trigger": "play", "action": "damage",
                  "target": "enemy_target", "amount": 2}]},

    {"id": "sharpen", "name": "Sharpen", "type": "spell", "cost": 1,
     "rarity": COMMON,
     "text": "Give a friendly creature +2/+1.",
     "effects": [{"trigger": "play", "action": "buff",
                  "target": "own_minion_target", "attack": 2, "health": 1}]},

    {"id": "quick_scout", "name": "Quick Scout", "type": "creature", "cost": 2,
     "attack": 2, "health": 1, "rarity": COMMON, "keywords": ["rush"],
     "text": "Rush.", "flavor": "Arrives before the rumour does."},

    {"id": "field_medic", "name": "Field Medic", "type": "creature", "cost": 2,
     "attack": 1, "health": 3, "rarity": COMMON,
     "text": "Play: restore 4 health to your hero.",
     "effects": [{"trigger": "play", "action": "heal",
                  "target": "own_hero", "amount": 4}]},

    {"id": "grave_rat", "name": "Grave Rat", "type": "creature", "cost": 2,
     "attack": 2, "health": 2, "rarity": COMMON,
     "text": "Death: summon a 1/1 Sewer Rat.",
     "effects": [{"trigger": "death", "action": "summon",
                  "card": "rat", "amount": 1}]},

    {"id": "militia_recruit", "name": "Militia Recruit", "type": "creature",
     "cost": 2, "attack": 3, "health": 2, "rarity": COMMON,
     "text": "", "flavor": "Volunteered. Regrets it."},

    {"id": "quick_study", "name": "Quick Study", "type": "spell", "cost": 2,
     "rarity": COMMON,
     "text": "Draw 2 cards.",
     "effects": [{"trigger": "play", "action": "draw", "amount": 2,
                  "scales": False}]},

    {"id": "healing_wind", "name": "Healing Wind", "type": "spell", "cost": 2,
     "rarity": COMMON,
     "text": "Restore 6 health to your hero.",
     "effects": [{"trigger": "play", "action": "heal",
                  "target": "own_hero", "amount": 6}]},

    {"id": "torch_thrower", "name": "Torch Thrower", "type": "creature",
     "cost": 3, "attack": 2, "health": 2, "rarity": COMMON,
     "text": "Play: deal 2 damage to a target.",
     "effects": [{"trigger": "play", "action": "damage",
                  "target": "enemy_target", "amount": 2}]},

    {"id": "bramble_guard", "name": "Bramble Guard", "type": "creature",
     "cost": 3, "attack": 2, "health": 4, "rarity": COMMON,
     "keywords": ["guard", "thorns"],
     "text": "Guard. Thorns.", "flavor": "Hugs are discouraged."},

    {"id": "arcane_apprentice", "name": "Arcane Apprentice", "type": "creature",
     "cost": 3, "attack": 2, "health": 3, "rarity": COMMON,
     "text": "Play: draw a card.",
     "effects": [{"trigger": "play", "action": "draw", "amount": 1,
                  "scales": False}]},

    {"id": "shield_bearer", "name": "Shield Bearer", "type": "creature",
     "cost": 4, "attack": 3, "health": 6, "rarity": COMMON,
     "keywords": ["guard"], "text": "Guard."},

    {"id": "iron_hound", "name": "Iron Hound", "type": "creature", "cost": 4,
     "attack": 4, "health": 4, "rarity": COMMON,
     "text": "", "flavor": "Sheds rust, not fur."},

    {"id": "temple_healer", "name": "Temple Healer", "type": "creature",
     "cost": 4, "attack": 3, "health": 4, "rarity": COMMON,
     "text": "Play: restore 3 health to all friendly creatures.",
     "effects": [{"trigger": "play", "action": "heal",
                  "target": "own_minions", "amount": 3}]},

    {"id": "boulder_brute", "name": "Boulder Brute", "type": "creature",
     "cost": 6, "attack": 6, "health": 6, "rarity": COMMON,
     "text": "", "flavor": "Simple plan. Large rock."},

    # =============================== RARE =================================
    {"id": "frost_wolf", "name": "Frost Wolf", "type": "creature", "cost": 3,
     "attack": 3, "health": 3, "rarity": RARE,
     "text": "Play: stun an enemy creature (it loses its next attack).",
     "effects": [{"trigger": "play", "action": "stun",
                  "target": "enemy_minion_target"}]},

    {"id": "venom_spider", "name": "Venom Spider", "type": "creature", "cost": 3,
     "attack": 1, "health": 3, "rarity": RARE, "keywords": ["poison"],
     "text": "Poison.", "flavor": "One bite is the whole conversation."},

    {"id": "gravedigger", "name": "Gravedigger", "type": "creature", "cost": 3,
     "attack": 2, "health": 3, "rarity": RARE,
     "text": "Whenever another friendly creature dies, gain +1/+1.",
     "effects": [{"trigger": "ally_death", "action": "buff",
                  "target": "self", "attack": 1, "health": 1, "scales": False}]},

    {"id": "lightning_arc", "name": "Lightning Arc", "type": "spell", "cost": 3,
     "rarity": RARE,
     "text": "Deal 3 damage to a target, then 1 damage to all enemy creatures.",
     "effects": [
         {"trigger": "play", "action": "damage", "target": "enemy_target", "amount": 3},
         {"trigger": "play", "action": "damage", "target": "enemy_minions",
          "amount": 1, "scales": False},
     ]},

    {"id": "soul_tax", "name": "Soul Tax", "type": "spell", "cost": 3,
     "rarity": RARE,
     "text": "Deal 3 damage to the enemy hero and restore 3 to yours.",
     "effects": [
         {"trigger": "play", "action": "damage", "target": "enemy_hero", "amount": 3},
         {"trigger": "play", "action": "heal", "target": "own_hero", "amount": 3},
     ]},

    {"id": "cloak_of_night", "name": "Cloak of Night", "type": "spell", "cost": 2,
     "rarity": RARE,
     "text": "Give a friendly creature +1/+1 and Stealth.",
     "effects": [
         {"trigger": "play", "action": "buff", "target": "own_minion_target",
          "attack": 1, "health": 1},
         {"trigger": "play", "action": "grant", "target": "own_minion_target",
          "keyword": "stealth"},
     ]},

    {"id": "blood_knight", "name": "Blood Knight", "type": "creature", "cost": 4,
     "attack": 4, "health": 3, "rarity": RARE, "keywords": ["lifesteal"],
     "text": "Lifesteal.", "flavor": "Dinner and a duel."},

    {"id": "thunder_hawk", "name": "Thunder Hawk", "type": "creature", "cost": 4,
     "attack": 3, "health": 3, "rarity": RARE, "keywords": ["rush"],
     "text": "Rush. Play: deal 2 damage to a random enemy creature.",
     "effects": [{"trigger": "play", "action": "damage",
                  "target": "enemy_random", "amount": 2}]},

    {"id": "banner_captain", "name": "Banner Captain", "type": "creature",
     "cost": 4, "attack": 3, "health": 3, "rarity": RARE,
     "text": "Play: give your other creatures +1/+1.",
     "effects": [{"trigger": "play", "action": "buff",
                  "target": "other_own_minions", "attack": 1, "health": 1,
                  "scales": False}]},

    {"id": "chaos_sprite", "name": "Chaos Sprite", "type": "creature", "cost": 4,
     "attack": 3, "health": 3, "rarity": RARE,
     "text": "Play: deal 1 damage 3 times to random enemies.",
     "flavor": "It is not aiming. It never was.",
     "effects": [{"trigger": "play", "action": "damage",
                  "target": "enemy_random_any", "amount": 1, "times": 3,
                  "scales": False}]},

    {"id": "mass_growth", "name": "Mass Growth", "type": "spell", "cost": 4,
     "rarity": RARE,
     "text": "Give your creatures +2/+2.",
     "effects": [{"trigger": "play", "action": "buff", "target": "own_minions",
                  "attack": 2, "health": 2}]},

    {"id": "siege_ram", "name": "Siege Ram", "type": "creature", "cost": 5,
     "attack": 6, "health": 3, "rarity": RARE, "keywords": ["pierce"],
     "text": "Pierce.", "flavor": "The wall was also a bystander."},

    {"id": "runic_golem", "name": "Runic Golem", "type": "creature", "cost": 5,
     "attack": 5, "health": 5, "rarity": RARE, "keywords": ["shield"],
     "text": "Shield."},

    # =============================== EPIC =================================
    {"id": "shadow_assassin", "name": "Shadow Assassin", "type": "creature",
     "cost": 4, "attack": 4, "health": 2, "rarity": EPIC, "keywords": ["stealth"],
     "text": "Stealth. Whenever it kills a creature, draw a card.",
     "effects": [{"trigger": "kill", "action": "draw", "amount": 1,
                  "scales": False}]},

    {"id": "reanimate", "name": "Reanimate", "type": "spell", "cost": 4,
     "rarity": EPIC,
     "text": "Summon two 2/2 Skeletons.",
     "effects": [{"trigger": "play", "action": "summon", "card": "skeleton",
                  "amount": 2, "scales": False}]},

    {"id": "dragonling", "name": "Dragonling", "type": "creature", "cost": 5,
     "attack": 4, "health": 4, "rarity": EPIC, "keywords": ["rush", "pierce"],
     "text": "Rush. Pierce.", "flavor": "Teething, unfortunately."},

    {"id": "time_weaver", "name": "Time Weaver", "type": "creature", "cost": 5,
     "attack": 3, "health": 5, "rarity": EPIC,
     "text": "At the start of your turn, draw a card.",
     "effects": [{"trigger": "turn_start", "action": "draw", "amount": 1,
                  "scales": False}]},

    {"id": "soul_harvester", "name": "Soul Harvester", "type": "creature",
     "cost": 5, "attack": 3, "health": 4, "rarity": EPIC,
     "keywords": ["lifesteal"],
     "text": "Lifesteal. Whenever another friendly creature dies, gain +2/+1.",
     "effects": [{"trigger": "ally_death", "action": "buff", "target": "self",
                  "attack": 2, "health": 1, "scales": False}]},

    {"id": "meteor", "name": "Meteor", "type": "spell", "cost": 6,
     "rarity": EPIC,
     "text": "Deal 5 damage to all enemy creatures.",
     "effects": [{"trigger": "play", "action": "damage",
                  "target": "enemy_minions", "amount": 5}]},

    {"id": "archlich", "name": "Archlich", "type": "creature", "cost": 6,
     "attack": 5, "health": 5, "rarity": EPIC,
     "text": "Death: deal 3 damage to all enemies.",
     "flavor": "Dying is merely a change of address.",
     "effects": [{"trigger": "death", "action": "damage",
                  "target": "enemy_all", "amount": 3}]},

    {"id": "warden_of_dawn", "name": "Warden of Dawn", "type": "creature",
     "cost": 6, "attack": 4, "health": 7, "rarity": EPIC,
     "keywords": ["guard", "shield"],
     "text": "Guard. Shield."},

    {"id": "stone_titan", "name": "Stone Titan", "type": "creature", "cost": 7,
     "attack": 7, "health": 8, "rarity": EPIC, "keywords": ["guard"],
     "text": "Guard.", "flavor": "Older than the argument it ends."},

    # ============================ LEGENDARY ===============================
    {"id": "zyx_unstable", "name": "Zyx the Unstable", "type": "creature",
     "cost": 5, "attack": 4, "health": 4, "rarity": LEGENDARY,
     "text": "Play: deal 1 damage 4 times, split randomly among enemies.",
     "flavor": "Zyx apologises in advance, and also afterwards.",
     "effects": [{"trigger": "play", "action": "damage",
                  "target": "enemy_random_any", "amount": 1, "times": 4,
                  "scales": False}]},

    {"id": "kaela_stormblade", "name": "Kaela, Stormblade", "type": "creature",
     "cost": 5, "attack": 5, "health": 4, "rarity": LEGENDARY,
     "keywords": ["rush"],
     "text": "Rush. Whenever she kills a creature, gain +2/+2.",
     "effects": [{"trigger": "kill", "action": "buff", "target": "self",
                  "attack": 2, "health": 2, "scales": False}]},

    {"id": "mordak_collector", "name": "Mordak the Collector", "type": "creature",
     "cost": 6, "attack": 5, "health": 5, "rarity": LEGENDARY,
     "text": "Play: draw 2 cards. Death: draw a card.",
     "flavor": "He keeps everything. Everything.",
     "effects": [
         {"trigger": "play", "action": "draw", "amount": 2, "scales": False},
         {"trigger": "death", "action": "draw", "amount": 1, "scales": False},
     ]},

    {"id": "sylva_rootmother", "name": "Sylva, Root Mother", "type": "creature",
     "cost": 6, "attack": 4, "health": 7, "rarity": LEGENDARY,
     "keywords": ["guard"],
     "text": "Guard. At the start of your turn, summon a 2/2 Treant with Guard.",
     "effects": [{"trigger": "turn_start", "action": "summon",
                  "card": "treant", "amount": 1, "scales": False}]},

    {"id": "vera_dawnbringer", "name": "Vera, Dawnbringer", "type": "creature",
     "cost": 7, "attack": 6, "health": 6, "rarity": LEGENDARY,
     "keywords": ["lifesteal"],
     "text": "Lifesteal. Play: give all your creatures Shield.",
     "effects": [{"trigger": "play", "action": "grant",
                  "target": "own_minions", "keyword": "shield"}]},

    {"id": "cataclysm", "name": "Cataclysm", "type": "spell", "cost": 8,
     "rarity": LEGENDARY,
     "text": "Destroy all creatures.",
     "flavor": "Fair is fair.",
     "effects": [{"trigger": "play", "action": "destroy", "target": "all_minions"}]},

    {"id": "ignis_everflame", "name": "Ignis, the Everflame", "type": "creature",
     "cost": 8, "attack": 8, "health": 8, "rarity": LEGENDARY,
     "text": "At the start of your turn, deal 2 damage to all enemies.",
     "flavor": "The sky has been on fire for three days. He is warming up.",
     "effects": [{"trigger": "turn_start", "action": "damage",
                  "target": "enemy_all", "amount": 2}]},
]

# Cards every brand new player is given (id -> copies owned)
STARTER_COLLECTION = {
    "glimmer_wisp": 2, "ember_imp": 2, "pebble_pup": 2, "flame_bolt": 2,
    "quick_scout": 2, "field_medic": 2, "militia_recruit": 2, "grave_rat": 2,
    "quick_study": 2, "torch_thrower": 2, "arcane_apprentice": 2,
    "bramble_guard": 2, "shield_bearer": 2, "iron_hound": 2, "healing_wind": 2,
    "blood_knight": 1, "frost_wolf": 1,
}

# --------------------------------------------------------------------------
# LOOKUP HELPERS -- you normally don't need to edit below this line
# --------------------------------------------------------------------------
_DEFAULTS = {
    "type": "creature", "cost": 1, "attack": 0, "health": 1,
    "rarity": COMMON, "keywords": [], "effects": [], "text": "",
    "flavor": "", "collectible": True,
}

_BY_ID = {}


def _normalise():
    """Fill in missing keys so the rest of the game never crashes on a typo."""
    for card in CARDS:
        for key, default in _DEFAULTS.items():
            if key not in card:
                card[key] = list(default) if isinstance(default, list) else default
        if card["type"] == "spell":
            card["attack"] = 0
            card["health"] = 0
        if card["id"] in _BY_ID:
            raise ValueError("Duplicate card id in cards.py: " + card["id"])
        _BY_ID[card["id"]] = card


_normalise()


def get_card(card_id):
    """Return the raw card dict for an id (or None if you typed it wrong)."""
    return _BY_ID.get(card_id)


def all_cards(collectible_only=True):
    if collectible_only:
        return [c for c in CARDS if c["collectible"]]
    return list(CARDS)


def cards_of_rarity(rarity, collectible_only=True):
    return [c for c in all_cards(collectible_only) if c["rarity"] == rarity]


def roll_rarity(rng=random, floor=None):
    """Pick a random rarity using RARITY_WEIGHT. `floor` forces a minimum."""
    pool = RARITIES
    if floor:
        pool = RARITIES[RARITIES.index(floor):]
    weights = [RARITY_WEIGHT[r] for r in pool]
    return rng.choices(pool, weights=weights, k=1)[0]


def random_card(rng=random, floor=None):
    rarity = roll_rarity(rng, floor)
    pool = cards_of_rarity(rarity)
    if not pool:                       # safety net if a rarity is empty
        pool = all_cards()
    return rng.choice(pool)


def max_copies(card):
    return MAX_COPIES.get(card["rarity"], 2)


def price_of(card):
    return RARITY_PRICE.get(card["rarity"], 50)


def stat_line(card, level=1):
    """'3/4' for creatures, '' for spells."""
    if card["type"] != "creature":
        return ""
    bonus = level - 1
    return "%d/%d" % (card["attack"] + bonus, card["health"] + bonus)


def describe(card, level=1, width=66):
    """Multi-line card description used everywhere in the menus."""
    tag = {COMMON: "C", RARE: "R", EPIC: "E", LEGENDARY: "L"}[card["rarity"]]
    lines = []
    head = "%s  (%s mana)" % (card["name"], card["cost"])
    if card["type"] == "creature":
        head += "  %s" % stat_line(card, level)
    head += "   [%s]" % tag
    if level > 1:
        head += " Lv%d" % level
    lines.append(head)
    if card["text"]:
        lines.append("   " + card["text"])
    if card["flavor"]:
        lines.append("   \"%s\"" % card["flavor"])
    return "\n".join(lines)
