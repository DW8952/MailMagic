"""
=============================================================================
 ui.py  --  tiny terminal helpers
=============================================================================
Everything the game prints goes through here, so if you ever want to change
the look of the game (colours, box characters, widths) this is the only file
you need to edit.
"""

import os
import sys

WIDTH = 72
USE_COLOR = True

_CODES = {
    "reset": "\033[0m", "bold": "\033[1m", "dim": "\033[2m",
    "red": "\033[31m", "green": "\033[32m", "yellow": "\033[33m",
    "blue": "\033[34m", "magenta": "\033[35m", "cyan": "\033[36m",
    "white": "\033[37m", "grey": "\033[90m",
}


def init():
    """Turn on ANSI colours on Windows terminals."""
    if os.name == "nt":
        os.system("")          # magic no-op that enables VT100 on Win10+
    try:
        sys.stdout.reconfigure(encoding="utf-8")   # py3.7+
    except Exception:
        pass


def c(text, *styles):
    if not USE_COLOR:
        return str(text)
    prefix = "".join(_CODES.get(s, "") for s in styles)
    return prefix + str(text) + _CODES["reset"]


def clear():
    os.system("cls" if os.name == "nt" else "clear")


def rule(char="-"):
    print(c(char * WIDTH, "grey"))


def title(text):
    print()
    print(c("=" * WIDTH, "cyan"))
    print(c(text.center(WIDTH), "cyan", "bold"))
    print(c("=" * WIDTH, "cyan"))


def header(text):
    print()
    print(c(text, "bold"))
    rule()


def say(text=""):
    print(text)


def good(text):
    print(c(text, "green"))


def bad(text):
    print(c(text, "red"))


def warn(text):
    print(c(text, "yellow"))


def info(text):
    print(c(text, "grey"))


def pause(msg="Press ENTER to continue..."):
    try:
        input(c("\n" + msg, "grey"))
    except EOFError:
        raise SystemExit(0)


def ask(prompt, default=""):
    # EOF means the input stream is gone (window closed, piped input ran out).
    # Quitting here is what stops the menus looping forever.
    try:
        answer = input(c(prompt + " ", "yellow")).strip()
    except EOFError:
        raise SystemExit(0)
    return answer or default


def ask_yes(prompt):
    while True:
        answer = ask(prompt + " (y/n)").lower()
        if answer.startswith("y"):
            return True
        if answer.startswith("n"):
            return False


def menu(heading, options, back_label="Back", clear_first=False):
    """
    Show a numbered menu. Returns the index of the chosen option,
    or -1 if the player chose the back/exit entry.
    `options` is a list of strings, or (string, subtitle) tuples.
    """
    while True:
        if clear_first:
            clear()
        header(heading)
        for i, opt in enumerate(options, 1):
            if isinstance(opt, (tuple, list)):
                label, note = opt[0], opt[1]
                print(" %s %s" % (c("[%d]" % i, "cyan"), label))
                if note:
                    print("     " + c(note, "grey"))
            else:
                print(" %s %s" % (c("[%d]" % i, "cyan"), opt))
        if back_label:
            print(" %s %s" % (c("[0]", "cyan"), back_label))
        rule()
        choice = ask(">")
        if choice in ("0", "") and back_label:
            return -1
        if choice.isdigit() and 1 <= int(choice) <= len(options):
            return int(choice) - 1
        bad("Pick a number from the list.")


def pick(heading, entries, back_label="Back", page_size=12):
    """
    Like menu() but paged -- for long lists (collection, deck builder).
    `entries` is a list of (label, payload). Returns payload or None.
    """
    page = 0
    pages = max(1, (len(entries) + page_size - 1) // page_size)
    while True:
        start = page * page_size
        chunk = entries[start:start + page_size]
        header("%s   (page %d/%d)" % (heading, page + 1, pages))
        if not chunk:
            info("  nothing here yet")
        for i, (label, _payload) in enumerate(chunk, 1):
            print(" %s %s" % (c("[%2d]" % i, "cyan"), label))
        rule()
        extra = []
        if pages > 1:
            extra.append("n = next page, p = previous page")
        extra.append("0 = %s" % back_label)
        info("  " + " | ".join(extra))
        choice = ask(">").lower()
        if choice in ("0", ""):
            return None
        if choice == "n" and pages > 1:
            page = (page + 1) % pages
            continue
        if choice == "p" and pages > 1:
            page = (page - 1) % pages
            continue
        if choice.isdigit() and 1 <= int(choice) <= len(chunk):
            return chunk[int(choice) - 1][1]
        bad("Not a valid choice.")


def banner(lines, style="cyan"):
    print(c("+" + "-" * (WIDTH - 2) + "+", style))
    for line in lines:
        print(c("|" + line.center(WIDTH - 2) + "|", style))
    print(c("+" + "-" * (WIDTH - 2) + "+", style))
