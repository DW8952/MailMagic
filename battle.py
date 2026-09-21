"""
=============================================================================
 battle.py  --  the actual card game
=============================================================================
Rules in one breath:

  * Both heroes start on 25 health and an empty board.
  * Mana goes 1, 2, 3 ... up to 10. You refill every turn.
  * You draw one card per turn. Empty deck = "fatigue", you start taking
    increasing damage each draw.
  * Creatures cannot attack the turn they are played (unless they have Rush).
  * If the enemy has a Guard creature you must attack it first.
  * Drop the enemy hero to 0 and you win.

The engine is data driven: it reads the "keywords" and "effects" lists from
cards.py, so a new card never needs new engine code unless you invent a new
action.
"""

import random

import cards
import ui

CHOSEN_TARGETS = ("enemy_target", "enemy_minion_target", "own_minion_target")


# ==========================================================================
#  CARD IN HAND / DECK
# ==========================================================================
class CardRef(object):
    """A specific copy of a card, at a specific upgrade level."""

    def __init__(self, card, level=1):
        self.card = card
        self.level = level

    @property
    def name(self):
        return self.card["name"]

    @property
    def cost(self):
        return self.card["cost"]

    @property
    def type(self):
        return self.card["type"]

    def label(self):
        text = "%s (%d)" % (self.name, self.cost)
        if self.card["type"] == "creature":
            text += " %s" % cards.stat_line(self.card, self.level)
        if self.level > 1:
            text += " Lv%d" % self.level
        return text


# ==========================================================================
#  FIGHTERS
# ==========================================================================
class Hero(object):
    is_hero = True

    def __init__(self, owner, hp=cards.HERO_HP):
        self.owner = owner
        self.name = owner.name
        self.health = hp
        self.max_health = hp
        self.shield = False
        self.keywords = set()
        self.attack = 0
        self.dead = False
        self.destroyed = False

    def take_damage(self, amount, source=None):
        if amount <= 0:
            return 0
        if self.shield:
            self.shield = False
            return 0
        self.health -= amount
        return amount

    def heal(self, amount):
        healed = min(amount, self.max_health - self.health)
        self.health += healed
        return healed


class Minion(object):
    is_hero = False

    def __init__(self, card, controller, level=1):
        self.card = card
        self.level = level
        self.name = card["name"]
        bonus = level - 1
        self.attack = card["attack"] + bonus
        self.max_health = card["health"] + bonus
        self.health = self.max_health
        self.keywords = set(card["keywords"])
        self.controller = controller
        self.dead = False
        self.destroyed = False
        self.stunned = False
        self.attacks_left = 0
        self.sleeping = "rush" not in self.keywords
        self.shield = "shield" in self.keywords
        self.hidden = "stealth" in self.keywords

    # ---- helpers -------------------------------------------------------
    @property
    def max_attacks(self):
        return 2 if "double_strike" in self.keywords else 1

    def effects_for(self, trigger):
        return [e for e in self.card["effects"] if e.get("trigger") == trigger]

    def can_attack(self):
        return (not self.sleeping and not self.stunned
                and self.attacks_left > 0 and self.attack > 0 and not self.dead)

    def label(self, show_state=False):
        text = "%-20s %d/%d" % (self.name, self.attack, self.health)
        tags = []
        if "guard" in self.keywords:
            tags.append("Guard")
        if self.shield:
            tags.append("Shield")
        if self.hidden:
            tags.append("Stealth")
        if "lifesteal" in self.keywords:
            tags.append("Lifesteal")
        if "poison" in self.keywords:
            tags.append("Poison")
        if "pierce" in self.keywords:
            tags.append("Pierce")
        if "thorns" in self.keywords:
            tags.append("Thorns")
        if "double_strike" in self.keywords:
            tags.append("x2")
        if tags:
            text += "  [" + ", ".join(tags) + "]"
        if show_state:
            if self.stunned:
                text += "  (stunned)"
            elif self.sleeping:
                text += "  (asleep)"
            elif self.attacks_left > 0:
                text += "  (ready)"
            else:
                text += "  (done)"
        return text

    # ---- combat --------------------------------------------------------
    def take_damage(self, amount, source=None):
        if amount <= 0 or self.dead:
            return 0
        if self.shield:
            self.shield = False
            return 0
        self.health -= amount
        if source is not None and "poison" in getattr(source, "keywords", ()):
            self.destroyed = True
        return amount

    def heal(self, amount):
        healed = min(amount, self.max_health - self.health)
        self.health += healed
        return healed

    def buff(self, attack=0, health=0):
        self.attack += attack
        self.max_health += health
        self.health += health


# ==========================================================================
#  A PLAYER INSIDE A BATTLE
# ==========================================================================
class Combatant(object):
    def __init__(self, name, deck, is_ai=False, profile=None):
        """deck is a list of (card_dict, level) tuples."""
        self.name = name
        self.is_ai = is_ai
        self.profile = profile
        self.hero = Hero(self)
        self.deck = [CardRef(card, level) for card, level in deck]
        random.shuffle(self.deck)
        self.hand = []
        self.board = []
        self.mana = 0
        self.max_mana = 0
        self.fatigue = 0
        self.coin = False          # going second: one extra mana on turn one
        self.opponent = None

    def draw(self, count=1, battle=None):
        for _ in range(count):
            if not self.deck:
                self.fatigue += 1
                self.hero.take_damage(self.fatigue)
                if battle:
                    battle.log("%s is out of cards and takes %d fatigue damage."
                               % (self.name, self.fatigue))
                continue
            ref = self.deck.pop()
            if len(self.hand) >= cards.HAND_LIMIT:
                if battle:
                    battle.log("%s's hand is full - %s is burned."
                               % (self.name, ref.name))
                continue
            self.hand.append(ref)

    def guards(self):
        return [m for m in self.board if "guard" in m.keywords and not m.hidden]

    def attackable(self):
        """What the enemy is allowed to swing at."""
        guards = self.guards()
        if guards:
            return guards
        return [m for m in self.board if not m.hidden] + [self.hero]


# ==========================================================================
#  THE BATTLE
# ==========================================================================
class Battle(object):
    def __init__(self, first, second, verbose=True, hotseat=False):
        self.players = [first, second]
        first.opponent = second
        second.opponent = first
        self.verbose = verbose
        self.hotseat = hotseat
        self.turn = 0
        self.active = 0
        self.finished = False
        self.winner = None

    # ---- plumbing ------------------------------------------------------
    def log(self, text, style=None):
        if not self.verbose:
            return
        if style:
            print(ui.c("  " + text, style))
        else:
            print("  " + text)

    def other(self, player):
        return player.opponent

    def check_winner(self):
        dead = [p for p in self.players if p.hero.health <= 0]
        if dead:
            self.finished = True
            if len(dead) == 2:
                self.winner = None                    # double KO = draw
            else:
                self.winner = self.other(dead[0])
        return self.finished

    # ---- setup ---------------------------------------------------------
    def opening_hands(self):
        self.players[0].draw(3, self)
        self.players[1].draw(4, self)       # going second gets one extra card
        self.players[1].coin = True         # ...and one extra mana on turn one

    # ==================================================================
    #  EFFECT RESOLUTION
    # ==================================================================
    def collect_targets(self, effect, source, controller, cached=None):
        where = effect.get("target")
        if where is None:
            where = "self" if effect.get("action") in ("buff", "grant", "heal") \
                else "enemy_hero"
        foe = self.other(controller)

        if where == "self":
            return [source] if source is not None else []
        if where == "own_hero":
            return [controller.hero]
        if where == "enemy_hero":
            return [foe.hero]
        if where == "own_minions":
            return list(controller.board)
        if where == "other_own_minions":
            return [m for m in controller.board if m is not source]
        if where == "enemy_minions":
            return list(foe.board)
        if where == "all_minions":
            return list(controller.board) + list(foe.board)
        if where == "enemy_all":
            return list(foe.board) + [foe.hero]
        if where == "own_random":
            return [random.choice(controller.board)] if controller.board else []
        if where == "enemy_random":
            return [random.choice(foe.board)] if foe.board else []
        if where == "enemy_random_any":
            pool = list(foe.board) + [foe.hero]
            return [random.choice(pool)]
        if where == "enemy_strongest":
            return [max(foe.board, key=lambda m: m.attack)] if foe.board else []
        if where in CHOSEN_TARGETS:
            if cached is not None:
                return [cached] if cached else []
            return []
        return []

    def options_for(self, where, controller):
        foe = self.other(controller)
        if where == "enemy_target":
            visible = [m for m in foe.board if not m.hidden]
            guards = [m for m in visible if "guard" in m.keywords]
            # spells ignore Guard, so everything visible is fair game
            del guards
            return visible + [foe.hero]
        if where == "enemy_minion_target":
            return [m for m in foe.board if not m.hidden]
        if where == "own_minion_target":
            return list(controller.board)
        return []

    def ask_target(self, effect, controller, source_name=""):
        where = effect.get("target")
        options = self.options_for(where, controller)
        if not options:
            return None
        if controller.is_ai:
            return self.ai_pick_target(effect, options, controller)
        print()
        ui.info("  Choose a target for %s:" % (source_name or "the effect"))
        for i, target in enumerate(options, 1):
            if target.is_hero:
                print("   %s %s (hero, %d HP)"
                      % (ui.c("[%d]" % i, "cyan"), target.name, target.health))
            else:
                print("   %s %s" % (ui.c("[%d]" % i, "cyan"), target.label()))
        while True:
            answer = ui.ask("  target >")
            if answer.isdigit() and 1 <= int(answer) <= len(options):
                return options[int(answer) - 1]
            ui.bad("  Pick one of the numbers.")

    def ai_pick_target(self, effect, options, controller):
        action = effect.get("action")
        amount = effect.get("amount", 0)
        minions = [t for t in options if not t.is_hero]
        heroes = [t for t in options if t.is_hero]

        if action in ("damage", "destroy", "stun"):
            enemy_minions = [m for m in minions if m.controller is not controller]
            if action == "damage":
                killable = [m for m in enemy_minions if m.health <= amount]
                if killable:
                    return max(killable, key=lambda m: m.attack)
            if enemy_minions:
                best = max(enemy_minions, key=lambda m: m.attack)
                if best.attack >= 3 or not heroes:
                    return best
            if heroes:
                return heroes[0]
            return enemy_minions[0] if enemy_minions else options[0]

        if action in ("buff", "grant", "heal"):
            friends = [m for m in minions if m.controller is controller]
            if friends:
                if action == "heal":
                    return min(friends, key=lambda m: m.health)
                return max(friends, key=lambda m: m.attack)
        return options[0]

    def resolve(self, effect, source, controller, level=1, cached_target=None):
        if self.finished:
            return
        action = effect.get("action")
        scales = effect.get("scales", True)
        bump = (level - 1) if scales else 0
        times = effect.get("times", 1)

        for _ in range(times):
            if self.finished:
                break
            targets = self.collect_targets(effect, source, controller,
                                           cached_target)
            if action == "draw":
                controller.draw(effect.get("amount", 1) + bump, self)
                self.log("%s draws a card." % controller.name, "grey")
                continue
            if action == "mana":
                controller.mana += effect.get("amount", 1) + bump
                continue
            if action == "summon":
                token = cards.get_card(effect.get("card", ""))
                if token:
                    for _ in range(effect.get("amount", 1)):
                        self.summon(token, controller, level=1)
                continue
            if not targets:
                continue

            for target in targets:
                if target is None or getattr(target, "dead", False):
                    continue
                if action == "damage":
                    dealt = target.take_damage(effect.get("amount", 1) + bump,
                                               source)
                    if dealt:
                        self.log("%s takes %d damage."
                                 % (target.name, dealt), "red")
                        if source is not None and "lifesteal" in getattr(
                                source, "keywords", ()):
                            controller.hero.heal(dealt)
                elif action == "heal":
                    healed = target.heal(effect.get("amount", 1) + bump)
                    if healed:
                        self.log("%s heals %d." % (target.name, healed), "green")
                elif action == "buff" and not target.is_hero:
                    target.buff(effect.get("attack", 0) + bump,
                                effect.get("health", 0) + bump)
                    self.log("%s gets +%d/+%d."
                             % (target.name, effect.get("attack", 0) + bump,
                                effect.get("health", 0) + bump), "green")
                elif action == "destroy" and not target.is_hero:
                    target.destroyed = True
                elif action == "stun" and not target.is_hero:
                    target.stunned = True
                    target.attacks_left = 0
                    self.log("%s is stunned." % target.name, "cyan")
                elif action == "grant":
                    keyword = effect.get("keyword")
                    if keyword:
                        target.keywords.add(keyword)
                        if keyword == "shield":
                            target.shield = True
                        if keyword == "stealth" and not target.is_hero:
                            target.hidden = True
                        self.log("%s gains %s." % (target.name, keyword), "green")
            self.check_deaths()
        self.check_winner()

    def fire(self, trigger, minion):
        for effect in minion.effects_for(trigger):
            cached = None
            if effect.get("target") in CHOSEN_TARGETS:
                cached = self.ask_target(effect, minion.controller, minion.name)
            self.resolve(effect, minion, minion.controller, minion.level, cached)

    # ==================================================================
    #  BOARD MANAGEMENT
    # ==================================================================
    def summon(self, card, controller, level=1, from_hand=False):
        if len(controller.board) >= cards.BOARD_LIMIT:
            self.log("%s's board is full." % controller.name, "grey")
            return None
        minion = Minion(card, controller, level)
        controller.board.append(minion)
        self.log("%s summons %s." % (controller.name, minion.label()), "yellow")
        for other in list(controller.board):
            if other is minion:
                continue
            for effect in other.effects_for("ally_summon"):
                self.resolve(effect, other, controller, other.level)
        if from_hand:
            self.fire("play", minion)
        self.check_deaths()
        return minion

    def check_deaths(self):
        for _ in range(20):                     # guard against weird loops
            dying = []
            for player in self.players:
                for minion in player.board:
                    if minion.health <= 0 or minion.destroyed:
                        dying.append(minion)
            if not dying:
                return
            for minion in dying:
                if minion.dead:
                    continue
                minion.dead = True
                owner = minion.controller
                if minion in owner.board:
                    owner.board.remove(minion)
                self.log("%s dies." % minion.name, "grey")
                for effect in minion.effects_for("death"):
                    cached = None
                    if effect.get("target") in CHOSEN_TARGETS:
                        cached = self.ask_target(effect, owner, minion.name)
                    self.resolve(effect, minion, owner, minion.level, cached)
                for ally in list(owner.board):
                    for effect in ally.effects_for("ally_death"):
                        self.resolve(effect, ally, owner, ally.level)

    # ==================================================================
    #  PLAYING CARDS + ATTACKING
    # ==================================================================
    def playable(self, player, ref):
        if ref.cost > player.mana:
            return False, "not enough mana"
        if ref.type == "creature":
            if len(player.board) >= cards.BOARD_LIMIT:
                return False, "board is full"
            return True, ""
        # a spell that needs a target it cannot get is a dead card
        for effect in ref.card["effects"]:
            where = effect.get("target")
            if where in CHOSEN_TARGETS and not self.options_for(where, player):
                return False, "no legal target"
        return True, ""

    def play_card(self, player, ref):
        player.mana -= ref.cost
        player.hand.remove(ref)
        if ref.type == "creature":
            self.summon(ref.card, player, ref.level, from_hand=True)
        else:
            self.log("%s casts %s." % (player.name, ref.name), "magenta")
            for effect in ref.card["effects"]:
                if effect.get("trigger", "play") != "play":
                    continue
                cached = None
                if effect.get("target") in CHOSEN_TARGETS:
                    cached = self.ask_target(effect, player, ref.name)
                self.resolve(effect, None, player, ref.level, cached)
        self.check_deaths()
        self.check_winner()

    def attack(self, attacker, target):
        attacker.attacks_left -= 1
        attacker.hidden = False
        for effect in attacker.effects_for("attack"):
            self.resolve(effect, attacker, attacker.controller, attacker.level)
        if attacker.dead or self.finished:
            return

        damage = attacker.attack
        if target.is_hero:
            dealt = target.take_damage(damage)
            self.log("%s hits %s for %d." % (attacker.name, target.name, dealt),
                     "red")
        else:
            overkill = damage - target.health
            dealt = target.take_damage(damage, attacker)
            back = target.attack + (1 if "thorns" in target.keywords else 0)
            self.log("%s (%d) strikes %s (%d)."
                     % (attacker.name, damage, target.name, back), "red")
            attacker.take_damage(back, target)
            if ("pierce" in attacker.keywords and overkill > 0
                    and (target.health <= 0 or target.destroyed)):
                spill = self.other(attacker.controller).hero.take_damage(overkill)
                if spill:
                    self.log("Pierce spills %d onto the enemy hero." % spill,
                             "red")
            if (target.health <= 0 or target.destroyed) and not attacker.dead:
                for effect in attacker.effects_for("kill"):
                    self.resolve(effect, attacker, attacker.controller,
                                 attacker.level)

        if dealt and "lifesteal" in attacker.keywords:
            healed = attacker.controller.hero.heal(dealt)
            if healed:
                self.log("%s heals %d from lifesteal."
                         % (attacker.controller.name, healed), "green")
        if attacker.health > 0 and not attacker.dead:
            for effect in attacker.effects_for("hurt"):
                self.resolve(effect, attacker, attacker.controller,
                             attacker.level)
        self.check_deaths()
        self.check_winner()

    # ==================================================================
    #  TURN STRUCTURE
    # ==================================================================
    def start_turn(self, player):
        self.turn += 1
        player.max_mana = min(cards.MAX_MANA, player.max_mana + 1)
        player.mana = player.max_mana
        if player.coin:
            player.coin = False
            player.mana += 1
            self.log("%s spends the coin (+1 mana this turn)." % player.name,
                     "cyan")
        for minion in player.board:
            minion.sleeping = False
            if minion.stunned:
                minion.stunned = False
                minion.attacks_left = 0
            else:
                minion.attacks_left = minion.max_attacks
            if "regenerate" in minion.keywords:
                minion.heal(1)
        for minion in list(player.board):
            if minion.dead:
                continue
            self.fire("turn_start", minion)
        if self.finished:
            return
        player.draw(1, self)
        self.check_winner()

    def end_turn(self, player):
        for minion in list(player.board):
            if not minion.dead:
                self.fire("turn_end", minion)
        self.check_deaths()
        self.check_winner()

    def run(self):
        self.opening_hands()
        while not self.finished:
            player = self.players[self.active]
            self.start_turn(player)
            if self.finished:
                break
            if player.is_ai:
                self.ai_turn(player)
            else:
                self.human_turn(player)
            if not self.finished:
                self.end_turn(player)
            self.active = 1 - self.active
            if self.turn > 300:                 # stalemate safety valve
                self.finished = True
                self.winner = None
        return self.winner

    # ==================================================================
    #  RENDERING
    # ==================================================================
    def render(self, player):
        foe = self.other(player)
        print()
        ui.rule("=")
        print(" %s   HP %s   hand %d   deck %d"
              % (ui.c(foe.name, "red", "bold"),
                 ui.c(foe.hero.health, "red"), len(foe.hand), len(foe.deck)))
        if foe.board:
            for i, minion in enumerate(foe.board, 1):
                print("   %s %s" % (ui.c("%d)" % i, "red"), minion.label()))
        else:
            ui.info("   (empty board)")
        ui.rule(".")
        if player.board:
            for i, minion in enumerate(player.board, 1):
                print("   %s %s" % (ui.c("%d)" % i, "green"),
                                    minion.label(show_state=True)))
        else:
            ui.info("   (empty board)")
        print(" %s   HP %s   mana %s   deck %d"
              % (ui.c(player.name, "green", "bold"),
                 ui.c(player.hero.health, "green"),
                 ui.c("%d/%d" % (player.mana, player.max_mana), "cyan"),
                 len(player.deck)))
        ui.rule("=")
        print(" HAND:")
        if not player.hand:
            ui.info("   (empty)")
        for i, ref in enumerate(player.hand, 1):
            ok, why = self.playable(player, ref)
            line = "   %s %s" % (ui.c("%d)" % i, "cyan"), ref.label())
            if not ok:
                line = ui.c("   %d) %s  - %s" % (i, ref.label(), why), "grey")
            print(line)

    # ==================================================================
    #  HUMAN TURN
    # ==================================================================
    def human_turn(self, player):
        if self.hotseat:
            ui.clear()
            ui.banner(["Pass the keyboard to %s" % player.name,
                       "(no peeking at the other hand)"], "yellow")
            ui.pause("Press ENTER when you are ready...")
        ui.title("%s's turn (turn %d)" % (player.name, (self.turn + 1) // 2))
        while not self.finished:
            self.render(player)
            choice = ui.menu("What now?",
                             ["Play a card", "Attack", "Read a card",
                              "Concede"],
                             back_label="End turn")
            if choice == -1:
                return
            if choice == 0:
                self.human_play(player)
            elif choice == 1:
                self.human_attack(player)
            elif choice == 2:
                self.human_inspect(player)
            elif choice == 3:
                if ui.ask_yes("Really give up?"):
                    player.hero.health = 0
                    self.check_winner()
                    return

    def human_play(self, player):
        if not player.hand:
            ui.info("  Your hand is empty.")
            return
        answer = ui.ask("  Play which card? (number, or ENTER to cancel)")
        if not answer.isdigit():
            return
        index = int(answer) - 1
        if not (0 <= index < len(player.hand)):
            ui.bad("  No such card.")
            return
        ref = player.hand[index]
        ok, why = self.playable(player, ref)
        if not ok:
            ui.bad("  You cannot play that: %s." % why)
            return
        self.play_card(player, ref)

    def human_attack(self, player):
        ready = [m for m in player.board if m.can_attack()]
        if not ready:
            ui.info("  Nothing of yours can attack right now.")
            return
        print()
        for i, minion in enumerate(ready, 1):
            print("   %s %s" % (ui.c("[%d]" % i, "green"), minion.label()))
        answer = ui.ask("  Attack with? (ENTER to cancel)")
        if not answer.isdigit() or not (1 <= int(answer) <= len(ready)):
            return
        attacker = ready[int(answer) - 1]

        foe = self.other(player)
        targets = foe.attackable()
        if not targets:
            ui.info("  Nothing to attack.")
            return
        print()
        for i, target in enumerate(targets, 1):
            if target.is_hero:
                print("   %s %s (hero, %d HP)"
                      % (ui.c("[%d]" % i, "red"), target.name, target.health))
            else:
                print("   %s %s" % (ui.c("[%d]" % i, "red"), target.label()))
        answer = ui.ask("  Attack what? (ENTER to cancel)")
        if not answer.isdigit() or not (1 <= int(answer) <= len(targets)):
            return
        self.attack(attacker, targets[int(answer) - 1])

    def human_inspect(self, player):
        pool = [("HAND: " + ref.label(), ref.card) for ref in player.hand]
        pool += [("YOURS: " + m.label(), m.card) for m in player.board]
        pool += [("THEIRS: " + m.label(), m.card)
                 for m in self.other(player).board]
        card = ui.pick("Read a card", pool, back_label="back")
        if card:
            print()
            print(cards.describe(card))
            ui.pause()

    # ==================================================================
    #  THE AI
    # ==================================================================
    def ai_turn(self, player):
        if self.verbose:
            ui.title("%s's turn" % player.name)
        self.ai_play_cards(player)
        self.ai_attacks(player)

    def ai_value(self, ref):
        """Rough 'how good is this card right now' score."""
        score = ref.cost * 10
        if ref.type == "creature":
            score += ref.card["attack"] + ref.card["health"]
        return score

    def ai_play_cards(self, player):
        safety = 0
        while not self.finished and safety < 20:
            safety += 1
            options = []
            for ref in player.hand:
                ok, _why = self.playable(player, ref)
                if ok:
                    options.append(ref)
            if not options:
                return
            options.sort(key=self.ai_value, reverse=True)
            self.play_card(player, options[0])

    def ai_attacks(self, player):
        foe = self.other(player)
        safety = 0
        while not self.finished and safety < 30:
            safety += 1
            ready = [m for m in player.board if m.can_attack()]
            if not ready:
                return
            targets = foe.attackable()
            if not targets:
                return
            attacker = max(ready, key=lambda m: m.attack)

            hero_open = any(t.is_hero for t in targets)
            total = sum(m.attack for m in ready)
            # lethal check: swing everything at the face
            if hero_open and total >= foe.hero.health:
                self.attack(attacker, foe.hero)
                continue

            enemy_minions = [t for t in targets if not t.is_hero]
            best_trade = None
            best_score = -99
            for target in enemy_minions:
                kills = attacker.attack >= target.health or \
                    "poison" in attacker.keywords
                survives = target.attack < attacker.health or attacker.shield
                score = 0
                if kills:
                    score += 6 + target.attack
                if survives:
                    score += 4
                if "guard" in target.keywords:
                    score += 2
                if not kills and not survives:
                    score -= 8
                if score > best_score:
                    best_score, best_trade = score, target
            if hero_open and best_score < 5:
                self.attack(attacker, foe.hero)
            elif best_trade is not None:
                self.attack(attacker, best_trade)
            elif hero_open:
                self.attack(attacker, foe.hero)
            else:
                return


# ==========================================================================
#  DECK BUILDING FOR AI OPPONENTS
# ==========================================================================
def random_ai_deck(difficulty="normal"):
    """Build a legal random deck for the practice opponent."""
    if difficulty == "easy":
        pool = cards.cards_of_rarity(cards.COMMON)
        level = 1
    elif difficulty == "hard":
        pool = cards.all_cards()
        level = 2
    else:
        pool = [card for card in cards.all_cards()
                if card["rarity"] in (cards.COMMON, cards.RARE)]
        level = 1

    deck = []
    guard = 0
    while len(deck) < cards.DECK_SIZE and guard < 500:
        guard += 1
        card = random.choice(pool)
        if deck.count(card) >= cards.max_copies(card):
            continue
        # keep the curve sane: no more than 6 cards costing 5+
        if card["cost"] >= 5 and sum(1 for c in deck if c["cost"] >= 5) >= 6:
            continue
        deck.append(card)
    return [(card, level) for card in deck]
