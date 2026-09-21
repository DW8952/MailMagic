RUNEBOUND RIVALS
================

A tiny Magic-ish card game for two people who mail a folder back and forth.


RUNNING IT
----------
    python main.py

Needs nothing but Python 3.8+. No pip installs.


MAKING THE EXE
--------------
    pip install pyinstaller
    pyinstaller --onefile --name game main.py

Copy dist/game.exe into a folder on its own. The first time it runs it makes
a `playerdata` folder NEXT TO the exe, which is the whole point: the saves
never get trapped inside the exe, so you can zip the folder and mail it.

    game folder/
        game.exe
        playerdata/
            BabolTS.json
            her.json

Zip the WHOLE folder every time you send it. Whoever has the zip is the one
who can play, same as passing a board game across a table.


THE FILES
---------
    cards.py     every card in the game. The only file you need to edit to
                 add more. Full instructions are in the comment at the top.
    battle.py    the rules engine: keywords, triggers, combat, the AI.
    storage.py   profiles, saving, loading, deck legality.
    economy.py   points, chests, shop, upgrades, match rewards.
    ui.py        menus, prompts, colours. Change the look here.
    main.py      login screen, main menu, everything the player clicks.


HOW THE GAME LOOP WORKS
-----------------------
  * Log in as yourself. Each player gets their own json file.
  * Battle: practice against the computer, duel your rival (you fight the
    exact deck they saved, played by the AI), or play side by side on one
    keyboard.
  * Winning gives points. Points buy chests and shop cards.
  * Duplicates are upgrade fuel: spare copies + points raise a card's level,
    which gives creatures +1/+1 per level and makes spell numbers bigger.
  * The shop rerolls every time the game is opened.
  * When you beat someone's deck in a duel, a message lands in THEIR profile,
    so they see it next time they open the game. Their deck gets points for
    defending successfully.


NUMBERS YOU'LL PROBABLY WANT TO CHANGE
--------------------------------------
    cards.py    -> DECK_SIZE, HERO_HP, MAX_MANA, RARITY_WEIGHT, UPGRADE_COST
    economy.py  -> CHESTS, REWARDS, SHOP_SLOTS

Two balance notes from testing 1000+ simulated games:
  * Average game is about 10 turns each.
  * Going first wins roughly 60% of the time even with the extra card and
    the coin the second player gets. Turn order is random each match, so it
    evens out, but if you want it tighter give the coin +2 mana instead of
    +1 (battle.py, start_turn).


ADDING A CARD IN 30 SECONDS
---------------------------
Open cards.py, scroll to the bottom of the CARDS list, paste:

    {
        "id": "ice_lance", "name": "Ice Lance", "type": "spell", "cost": 2,
        "rarity": RARE,
        "text": "Deal 2 damage to a target and stun it.",
        "effects": [
            {"trigger": "play", "action": "damage",
             "target": "enemy_target", "amount": 2},
            {"trigger": "play", "action": "stun",
             "target": "enemy_minion_target"},
        ],
    },

Save. It is instantly in chests, in the shop, and playable. Old save files
keep working; profiles automatically drop cards whose id disappears.
