"""
=============================================================================
 main.py  --  MAIL MAGIC
=============================================================================
Run this file to play. Everything the player sees starts here.

Folder layout (keep it exactly like this when you zip it up and mail it):

    game folder/
        main.py        (or game.exe once you compile)
        cards.py
        battle.py
        storage.py
        economy.py
        ui.py
        playerdata/
            BabolTS.json
            her.json

Building the exe:
    pip install pyinstaller
    pyinstaller --onefile --name game main.py
Then copy dist/game.exe into your game folder. The exe looks for the
`playerdata` folder next to itself, so the saves are never trapped inside it.
=============================================================================
"""

import random
import sys
import traceback

import battle
import cards
import economy
import storage
import ui

GAME_NAME = "MAILMAGIC"


# ==========================================================================
#  LOGIN
# ==========================================================================
def login():
    """Pick or create a profile. Returns a profile dict, or None to quit."""
    while True:
        ui.clear()
        ui.banner([GAME_NAME, "a very small card game for two people"])
        profiles = storage.list_profiles()

        options = []
        for profile in profiles:
            note = "%d points | %dW/%dL | %d cards" % (
                profile["points"], profile["wins"], profile["losses"],
                len(profile["collection"]))
            options.append((profile["name"], note))
        options.append(("Create a new player", "start a fresh collection"))

        choice = ui.menu("Who is playing?", options, back_label="Quit")
        if choice == -1:
            return None
        if choice == len(options) - 1:
            profile = create_player()
            if profile:
                return profile
            continue

        profile = profiles[choice]
        if profile.get("password"):
            for _attempt in range(3):
                password = ui.ask("Password for %s:" % profile["name"])
                if storage.check_pw(profile, password):
                    return profile
                ui.bad("Wrong password.")
            ui.pause()
            continue
        return profile


def create_player():
    ui.header("New player")
    name = ui.ask("Name:")
    if not name:
        return None
    if storage.load(name):
        ui.bad("That name is taken (names are not case sensitive).")
        ui.pause()
        return None
    ui.info("A password is optional. It only stops the other one of you from")
    ui.info("opening your profile - leave it empty if you don't care.")
    password = ui.ask("Password (ENTER for none):")
    profile = storage.create(name, password)
    ui.good("\nWelcome, %s!" % profile["name"])
    ui.info("You start with 150 points, a starter collection and a deck")
    ui.info("that has already been built for you. Go win something.")
    ui.pause()
    return profile


# ==========================================================================
#  MAIN MENU
# ==========================================================================
def session(profile):
    """Returns True to log out, False to quit the game entirely."""
    shop = economy.roll_shop(profile)
    while True:
        ui.clear()
        ui.banner([GAME_NAME])
        print(" %s   points: %s   record: %s"
              % (ui.c(profile["name"], "bold"),
                 ui.c(profile["points"], "yellow"),
                 ui.c("%dW / %dL" % (profile["wins"], profile["losses"]),
                      "cyan")))
        unread = len(profile["inbox"])
        choice = ui.menu(
            "Main menu",
            [("Battle", "practice, duel your rival, or play side by side"),
             ("Collection", "look at your cards and upgrade them"),
             ("Deck", "build the 20 cards you fight with"),
             ("Shop", "rerolls every time you open the game"),
             ("Chests", "spend points, get cards"),
             ("Profile", "stats and news%s"
              % ("  (%d messages)" % unread if unread else ""))],
            back_label="Log out / quit")

        if choice == -1:
            storage.save(profile)
            again = ui.menu("Leaving", ["Log out (switch player)",
                                        "Save and quit"], back_label="Cancel")
            if again == 0:
                return True
            if again == 1:
                return False
            continue
        if choice == 0:
            battle_menu(profile)
        elif choice == 1:
            collection_menu(profile)
        elif choice == 2:
            deck_menu(profile)
        elif choice == 3:
            shop_menu(profile, shop)
        elif choice == 4:
            chest_menu(profile)
        elif choice == 5:
            profile_menu(profile)
        storage.save(profile)


# ==========================================================================
#  BATTLE FLOW
# ==========================================================================
def ensure_deck(profile):
    ok, message = storage.deck_is_legal(profile)
    if ok:
        return True
    ui.bad(message)
    if ui.ask_yes("Build a deck automatically?"):
        profile["deck"] = storage.auto_build_deck(profile)
        storage.save(profile)
        ok, message = storage.deck_is_legal(profile)
        if ok:
            ui.good("Deck built.")
            return True
        ui.bad(message)
    ui.pause()
    return False


def battle_menu(profile):
    while True:
        choice = ui.menu(
            "Battle",
            [("Practice - easy", "commons only, gentle"),
             ("Practice - normal", "a real deck"),
             ("Practice - hard", "everything, upgraded"),
             ("Duel your rival", "fight another player's saved deck"),
             ("Side by side", "two people, one keyboard")],
            back_label="Back")
        if choice == -1:
            return
        if not ensure_deck(profile):
            continue
        if choice in (0, 1, 2):
            mode = ["easy", "normal", "hard"][choice]
            practice(profile, mode)
        elif choice == 3:
            duel(profile)
        elif choice == 4:
            hotseat(profile)


def practice(profile, mode):
    deck = storage.build_battle_deck(profile)
    names = {"easy": "Training Dummy", "normal": "Wandering Duelist",
             "hard": "The Archmagister"}
    you = battle.Combatant(profile["name"], deck, is_ai=False, profile=profile)
    them = battle.Combatant(names[mode], battle.random_ai_deck(mode),
                            is_ai=True)
    first, second = (you, them) if random.random() < 0.5 else (them, you)
    fight = battle.Battle(first, second, verbose=True)
    ui.clear()
    ui.banner(["%s  vs  %s" % (you.name, them.name)])
    ui.info("%s goes first." % first.name)
    ui.pause("Press ENTER to start...")
    result = fight.run()
    print()
    won = result is you
    if result is None:
        ui.warn("A draw!")
    elif won:
        ui.banner(["YOU WIN"], "green")
    else:
        ui.banner(["YOU LOSE"], "red")
    finish_match(profile, mode, won, them.name, counted=True)


def duel(profile):
    others = [p for p in storage.list_profiles()
              if storage.safe_name(p["name"]) != storage.safe_name(profile["name"])]
    if not others:
        ui.info("There is nobody else on this copy of the game yet.")
        ui.info("Make a second profile, or get your rival to play and send")
        ui.info("the whole folder back to you.")
        ui.pause()
        return
    entries = []
    for other in others:
        ok, _msg = storage.deck_is_legal(other)
        note = "%d cards | %dW/%dL" % (len(other["collection"]),
                                       other["wins"], other["losses"])
        if not ok:
            note += "  (no legal deck - cannot be challenged)"
        entries.append(("%-16s %s" % (other["name"], note),
                        other if ok else None))
    target = ui.pick("Whose deck do you want to fight?", entries)
    if target is None:
        return

    deck = storage.build_battle_deck(profile)
    enemy_deck = storage.build_battle_deck(target)
    you = battle.Combatant(profile["name"], deck, is_ai=False, profile=profile)
    them = battle.Combatant(target["name"] + "'s deck", enemy_deck, is_ai=True)
    first, second = (you, them) if random.random() < 0.5 else (them, you)

    ui.clear()
    ui.banner(["DUEL", "%s  vs  %s" % (you.name, them.name)])
    ui.info("Their deck is played by the computer, but every card and every")
    ui.info("upgrade is exactly what they saved.")
    ui.info("%s goes first." % first.name)
    ui.pause("Press ENTER to start...")
    result = battle.Battle(first, second, verbose=True).run()
    print()
    won = result is you
    if result is None:
        ui.warn("A draw!")
    elif won:
        ui.banner(["YOU BEAT %s" % target["name"].upper()], "green")
    else:
        ui.banner(["%s'S DECK HELD" % target["name"].upper()], "red")

    finish_match(profile, "duel", won, target["name"], counted=True)

    # leave a message in their file so they see it when they open the game
    fresh = storage.load(target["name"])
    if fresh:
        if won:
            fresh["defense_losses"] += 1
            storage.notify(fresh, "%s beat your deck in a duel." % profile["name"])
        else:
            fresh["defense_wins"] += 1
            fresh["points"] += 10
            storage.notify(fresh, "Your deck defended against %s. +10 points."
                           % profile["name"])
        storage.save(fresh)


def hotseat(profile):
    ui.header("Side by side")
    ui.info("The second player logs in now. You will pass the keyboard back")
    ui.info("and forth, and the screen clears between turns.")
    profiles = [p for p in storage.list_profiles()
                if storage.safe_name(p["name"]) != storage.safe_name(profile["name"])]
    if not profiles:
        ui.bad("There is no second profile on this copy yet.")
        ui.pause()
        return
    entries = [("%s  (%d points)" % (p["name"], p["points"]), p)
               for p in profiles]
    other = ui.pick("Second player", entries)
    if other is None:
        return
    if other.get("password"):
        for _attempt in range(3):
            if storage.check_pw(other, ui.ask("Password for %s:" % other["name"])):
                break
            ui.bad("Wrong password.")
        else:
            return
    ok, message = storage.deck_is_legal(other)
    if not ok:
        ui.bad("%s has no legal deck: %s" % (other["name"], message))
        ui.pause()
        return

    you = battle.Combatant(profile["name"], storage.build_battle_deck(profile),
                           is_ai=False, profile=profile)
    them = battle.Combatant(other["name"], storage.build_battle_deck(other),
                            is_ai=False, profile=other)
    first, second = (you, them) if random.random() < 0.5 else (them, you)
    ui.clear()
    ui.banner(["%s  vs  %s" % (first.name, second.name)])
    ui.info("%s goes first." % first.name)
    ui.pause()
    result = battle.Battle(first, second, verbose=True, hotseat=True).run()
    print()
    if result is None:
        ui.warn("A draw!")
    else:
        ui.banner(["%s WINS" % result.name.upper()], "green")

    finish_match(profile, "hotseat", result is you, other["name"], counted=True)
    fresh = storage.load(other["name"])
    if fresh:
        won = result is them
        fresh["wins" if won else "losses"] += 1
        gain = economy.reward_for("hotseat", won)
        fresh["points"] += gain
        storage.log_match(fresh, "%s %s in a side-by-side game. +%d points."
                          % ("Beat" if won else "Lost to", profile["name"], gain))
        storage.save(fresh)
        ui.good("%s earned %d points." % (fresh["name"], gain))
    ui.pause()


def finish_match(profile, mode, won, opponent_name, counted=True):
    gain = economy.reward_for(mode, won)
    profile["points"] += gain
    if counted:
        profile["wins" if won else "losses"] += 1
    storage.log_match(profile, "%s %s (%s). +%d points."
                      % ("Beat" if won else "Lost to", opponent_name, mode, gain))
    storage.save(profile)
    print()
    ui.good("+%d points  (you now have %d)" % (gain, profile["points"]))
    ui.pause()


# ==========================================================================
#  COLLECTION + UPGRADES
# ==========================================================================
def collection_label(profile, card, entry):
    in_deck = storage.deck_counts(profile).get(card["id"], 0)
    tag = {cards.COMMON: "C", cards.RARE: "R", cards.EPIC: "E",
           cards.LEGENDARY: "L"}[card["rarity"]]
    stats = cards.stat_line(card, entry["level"]) or "spell"
    return "%-22s %-5s (%d) %-6s x%-2d  Lv%d%s" % (
        card["name"], tag, card["cost"], stats, entry["copies"],
        entry["level"], "  [in deck: %d]" % in_deck if in_deck else "")


def collection_menu(profile):
    sort = "cost"
    while True:
        items = storage.owned_cards(profile, sort)
        entries = [(collection_label(profile, card, entry), card["id"])
                   for card, entry in items]
        ui.clear()
        print(" Collection: %d different cards | %d points"
              % (len(items), profile["points"]))
        ui.info(" (sorted by %s)" % sort)
        card_id = ui.pick("Your cards", entries, back_label="Back")
        if card_id is None:
            sort_choice = ui.menu("Anything else?",
                                  ["Sort by cost", "Sort by rarity",
                                   "Sort by name"], back_label="Back to menu")
            if sort_choice == -1:
                return
            sort = ["cost", "rarity", "name"][sort_choice]
            continue
        card_detail(profile, card_id)


def card_detail(profile, card_id):
    while True:
        card = cards.get_card(card_id)
        entry = profile["collection"][card_id]
        ui.clear()
        ui.header(card["name"])
        print(cards.describe(card, entry["level"]))
        print()
        print("  Rarity   : %s" % card["rarity"])
        print("  Copies   : %d  (1 is kept for playing, the rest are upgrade fuel)"
              % entry["copies"])
        print("  Level    : %d / %d" % (entry["level"], cards.MAX_LEVEL))
        print("  Max/deck : %d" % cards.max_copies(card))
        ok, next_level, need_copies, need_points, reason = \
            economy.upgrade_info(profile, card_id)
        print()
        if entry["level"] >= cards.MAX_LEVEL:
            ui.good("  This card is fully upgraded.")
        else:
            print("  Next level (%d) costs %d spare copies + %d points."
                  % (next_level, need_copies, need_points))
            if card["type"] == "creature":
                ui.info("  It would become %s."
                        % cards.stat_line(card, next_level))
            else:
                ui.info("  Its numbers would each go up by 1.")
            if not ok:
                ui.warn("  " + reason)
        rule = ["Upgrade this card"] if ok else []
        choice = ui.menu("", rule, back_label="Back")
        if choice == -1:
            return
        if choice == 0:
            success, message = economy.do_upgrade(profile, card_id)
            (ui.good if success else ui.bad)("  " + message)
            storage.save(profile)
            ui.pause()


# ==========================================================================
#  DECK BUILDER
# ==========================================================================
def show_deck(profile):
    counts = storage.deck_counts(profile)
    entries = []
    for card_id, count in counts.items():
        card = cards.get_card(card_id)
        entries.append((card["cost"], card["name"], count, card_id))
    entries.sort()
    ui.header("Your deck (%d/%d)" % (len(profile["deck"]), cards.DECK_SIZE))
    if not entries:
        ui.info("  empty")
    for cost, name, count, card_id in entries:
        level = storage.level_of(profile, card_id)
        card = cards.get_card(card_id)
        print("   %dx  (%d) %-22s %s%s"
              % (count, cost, name, cards.stat_line(card, level) or "spell",
                 "  Lv%d" % level if level > 1 else ""))
    curve = {}
    for card_id in profile["deck"]:
        cost = min(7, cards.get_card(card_id)["cost"])
        curve[cost] = curve.get(cost, 0) + 1
    print()
    print("   curve: " + "  ".join(
        "%d%s:%s" % (cost, "+" if cost == 7 else "", "#" * curve.get(cost, 0))
        for cost in range(0, 8)))


def deck_menu(profile):
    while True:
        ui.clear()
        show_deck(profile)
        ok, message = storage.deck_is_legal(profile)
        (ui.good if ok else ui.warn)("  " + message)
        choice = ui.menu("Deck",
                         ["Add cards", "Remove cards", "Auto-build a deck",
                          "Empty the deck"], back_label="Back")
        if choice == -1:
            return
        if choice == 0:
            deck_add(profile)
        elif choice == 1:
            deck_remove(profile)
        elif choice == 2:
            profile["deck"] = storage.auto_build_deck(profile)
            ui.good("  Built a deck from your collection.")
            ui.pause()
        elif choice == 3:
            if ui.ask_yes("  Remove every card from the deck?"):
                profile["deck"] = []
        storage.save(profile)


def deck_add(profile):
    while True:
        counts = storage.deck_counts(profile)
        entries = []
        for card, entry in storage.owned_cards(profile):
            in_deck = counts.get(card["id"], 0)
            limit = cards.max_copies(card)
            if in_deck >= limit:
                continue
            level = entry["level"]
            entries.append((
                "(%d) %-22s %-6s %s [%d/%d in deck]"
                % (card["cost"], card["name"],
                   cards.stat_line(card, level) or "spell",
                   ("Lv%d" % level) if level > 1 else "   ", in_deck, limit),
                card["id"]))
        if len(profile["deck"]) >= cards.DECK_SIZE:
            ui.warn("  Deck is already full (%d)." % cards.DECK_SIZE)
            ui.pause()
            return
        card_id = ui.pick("Add which card?  (deck %d/%d)"
                          % (len(profile["deck"]), cards.DECK_SIZE), entries)
        if card_id is None:
            return
        profile["deck"].append(card_id)
        storage.save(profile)


def deck_remove(profile):
    while True:
        counts = storage.deck_counts(profile)
        entries = []
        for card_id, count in sorted(
                counts.items(), key=lambda kv: cards.get_card(kv[0])["cost"]):
            card = cards.get_card(card_id)
            entries.append(("%dx (%d) %s" % (count, card["cost"], card["name"]),
                            card_id))
        if not entries:
            return
        card_id = ui.pick("Remove which card?  (deck %d/%d)"
                          % (len(profile["deck"]), cards.DECK_SIZE), entries)
        if card_id is None:
            return
        profile["deck"].remove(card_id)
        storage.save(profile)


# ==========================================================================
#  SHOP
# ==========================================================================
def shop_menu(profile, shop):
    while True:
        ui.clear()
        ui.header("The Wandering Shop")
        ui.info(" New stock every time you open the game. Spend it or lose it.")
        print(" You have %s points." % ui.c(profile["points"], "yellow"))
        print()
        entries = []
        for offer in shop:
            card = cards.get_card(offer["card_id"])
            level = storage.level_of(profile, card["id"])
            owned = profile["collection"].get(card["id"], {}).get("copies", 0)
            label = "%-22s %-5s (%d) %-6s  %s points%s%s" % (
                card["name"], card["rarity"][:4].upper(), card["cost"],
                cards.stat_line(card, level) or "spell", offer["price"],
                "  SALE" if offer["discount"] else "",
                "  owned x%d" % owned if owned else "  NEW")
            if offer["sold"]:
                label = "SOLD OUT - " + card["name"]
            entries.append((label, offer))
        chosen = ui.pick("Stock", entries, back_label="Leave")
        if chosen is None:
            return
        card = cards.get_card(chosen["card_id"])
        print()
        print(cards.describe(card))
        if not ui.ask_yes("  Buy %s for %d points?" % (card["name"],
                                                       chosen["price"])):
            continue
        ok, message = economy.buy_offer(profile, chosen)
        (ui.good if ok else ui.bad)("  " + message)
        storage.save(profile)
        ui.pause()


# ==========================================================================
#  CHESTS
# ==========================================================================
def chest_menu(profile):
    while True:
        ui.clear()
        ui.header("Chests")
        print(" You have %s points." % ui.c(profile["points"], "yellow"))
        ui.info(" Duplicates are not wasted - spare copies are the fuel you")
        ui.info(" need to upgrade a card's level.")
        options = []
        names = list(economy.CHESTS.keys())
        for name in names:
            price, count, floor = economy.CHESTS[name]
            options.append((name, "%d points - %d cards, at least one %s"
                            % (price, count, floor)))
        choice = ui.menu("Open what?", options, back_label="Back")
        if choice == -1:
            return
        name = names[choice]
        price = economy.CHESTS[name][0]
        if profile["points"] < price:
            ui.bad("  You need %d points." % price)
            ui.pause()
            continue
        pulls = economy.open_chest(profile, name)
        storage.save(profile)
        reveal(pulls, name)


def reveal(pulls, chest_name):
    ui.clear()
    ui.banner([chest_name + " opens..."], "yellow")
    for card, is_new, refund in pulls:
        ui.pause("  ENTER to reveal...")
        colour = {cards.COMMON: "white", cards.RARE: "cyan",
                  cards.EPIC: "magenta", cards.LEGENDARY: "yellow"}[card["rarity"]]
        print(ui.c("  " + card["rarity"].upper(), colour))
        print(ui.c("  " + cards.describe(card).replace("\n", "\n  "), colour))
        if is_new:
            ui.good("  *** NEW CARD ***")
        elif refund:
            ui.info("  (you have plenty of these - refunded %d points)" % refund)
    ui.pause()


# ==========================================================================
#  PROFILE
# ==========================================================================
def profile_menu(profile):
    ui.clear()
    ui.header(profile["name"])
    print("  Points          : %d" % profile["points"])
    print("  Record          : %d wins / %d losses"
          % (profile["wins"], profile["losses"]))
    print("  Deck defence    : %d held / %d broken"
          % (profile["defense_wins"], profile["defense_losses"]))
    print("  Chests opened   : %d" % profile["chests_opened"])
    print("  Cards collected : %d of %d"
          % (len(profile["collection"]), len(cards.all_cards())))
    total = sum(e["copies"] for e in profile["collection"].values())
    print("  Total copies    : %d" % total)

    if profile["inbox"]:
        ui.header("News since you last played")
        for item in reversed(profile["inbox"][-10:]):
            print("  %s  %s" % (ui.c(storage.stamp(item["time"]), "grey"),
                                item["text"]))
        profile["inbox"] = []
    if profile["history"]:
        ui.header("Your last games")
        for item in reversed(profile["history"][-8:]):
            print("  %s  %s" % (ui.c(storage.stamp(item["time"]), "grey"),
                                item["text"]))
    storage.save(profile)
    ui.pause()


# ==========================================================================
#  ENTRY POINT
# ==========================================================================
def main():
    ui.init()
    storage.ensure_dirs()
    while True:
        profile = login()
        if profile is None:
            break
        keep_going = session(profile)
        if not keep_going:
            break
    ui.clear()
    ui.banner(["Thanks for playing", "zip the folder and mail it onward"])


if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        print("\nBye.")
    except Exception:                      # keeps the .exe window open on a bug
        traceback.print_exc()
        try:
            input("\nSomething broke. Send this text to BabolTS. ENTER to close.")
        except EOFError:
            pass
        sys.exit(1)
