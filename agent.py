"""
The FitFindr planning loop.

This is the file that makes FitFindr an agent rather than a script. It decides
which tool to run next based on what the last one returned.

If your loop calls all three tools no matter what comes back, you have a list
of function calls. A loop looks at the last result before it picks the next
step. **That branch is the graded part of this unit.**

Build and test your three tools in `tools.py` first. Then come here.

    python agent.py          runs both example paths below
"""

import re

import config
import trace
from tools import search_listings, suggest_outfit, create_fit_card
from generate import ModelUnavailable
from utils.data_loader import load_listings


# ── session state ─────────────────────────────────────────────────────────────

def new_session(query: str, wardrobe: dict) -> dict:
    """
    A fresh session for one user interaction.

    The session is the single source of truth for a run. Every tool result goes
    in here, and the next tool reads it back out.

    You could pass values straight from one call to the next. It would work,
    and you would not be able to test it — you can't print a variable you have
    already overwritten. Going through the session is what makes the state
    visible, and unit 4 has you write a criterion about exactly that.

    Add fields if you need them.
    """
    return {
        "query": query,              # what the user typed
        "parsed": {},                # description / size / max_price you pulled out of it
        "search_results": [],        # everything search_listings returned
        "selected_item": None,       # the one you chose — goes into suggest_outfit
        "wardrobe": wardrobe,        # the user's wardrobe
        "outfit_suggestion": None,   # what suggest_outfit returned
        "fit_card": None,            # what create_fit_card returned
        "error": None,               # set when the run ended early
    }


# ── parsing the query ─────────────────────────────────────────────────────────
# Regex, not a model call: it is deterministic, costs nothing, and a wrong
# parse is easy to see by printing session["parsed"].

_PRICE_PATTERNS = [
    # "under $30", "under 30", "less than 40 dollars", "max $25", "up to 50"
    re.compile(
        r"\b(?:under|below|less than|at most|max(?:imum)?|up to|budget(?: of)?)"
        r"\s*\$?\s*(\d+(?:\.\d+)?)",
        re.I,
    ),
    # a bare "$30" anywhere
    re.compile(r"\$\s*(\d+(?:\.\d+)?)"),
]

_SIZE_PATTERNS = [
    re.compile(r"\bsize\s+([a-z0-9.]+)", re.I),            # "size M", "size 8", "size XXS"
    re.compile(r"\b(us\s?\d+(?:\.\d+)?)\b", re.I),          # "US 8", "US 8.5"
    re.compile(r"\b(w\d{2})\b", re.I),                      # "W30"
    re.compile(r"\b(xxs|xs|s|m|l|xl|xxl)\b", re.I),         # a bare letter size
    re.compile(r"\b(extra small|small|medium|large|extra large)\b", re.I),
]


def _parse_query(query: str) -> dict:
    """
    Pull a description, a size and a price ceiling out of plain language.

        "90s track jacket in size M"      -> {"description": "90s track jacket in",
                                              "size": "M", "max_price": None}
        "vintage graphic tee under $30"   -> {"description": "vintage graphic tee",
                                              "size": None, "max_price": 30.0}

    Whatever the price and size patterns match is cut out of the text, and the
    rest is the description. Leftover words like "in" are stop words to
    search_listings, so they do no harm.
    """
    text = query or ""

    max_price = None
    for pattern in _PRICE_PATTERNS:
        match = pattern.search(text)
        if match:
            max_price = float(match.group(1))
            text = text[: match.start()] + " " + text[match.end():]
            break

    size = None
    for pattern in _SIZE_PATTERNS:
        match = pattern.search(text)
        if match:
            size = match.group(1).strip().rstrip(".")
            text = text[: match.start()] + " " + text[match.end():]
            break

    description = " ".join(text.replace(",", " ").split())
    return {"description": description, "size": size, "max_price": max_price}


def _no_match_message(parsed: dict) -> str:
    """
    The message for the empty branch. It names what was searched for and what
    the user could change — "No results" tells them nothing.
    """
    listings = load_listings()
    prices = [listing["price"] for listing in listings]

    asked = f"'{parsed['description']}'" if parsed["description"] else "that"
    constraints = []
    if parsed["size"]:
        constraints.append(f"in size {parsed['size']}")
    if parsed["max_price"] is not None:
        constraints.append(f"under ${parsed['max_price']:g}")
    where = (" " + " ".join(constraints)) if constraints else ""

    tips = []
    if parsed["description"]:
        tips.append("try fewer or more general keywords (for example 'tee' instead of 'tee shirt')")
    else:
        tips.append("add a few words describing the item you want")
    if parsed["size"]:
        tips.append("drop the size, or write it the way listings do (M, S/M, US 8, W30)")
    if parsed["max_price"] is not None:
        tips.append("raise the price ceiling")

    return (
        f"No listings matched {asked}{where}. You could: {'; '.join(tips)}. "
        f"There are {len(listings)} listings priced from ${min(prices):g} to "
        f"${max(prices):g} across tops, bottoms, outerwear, shoes and accessories."
    )


# ── planning loop ─────────────────────────────────────────────────────────────

def run_agent(query: str, wardrobe: dict) -> dict:
    """
    Run the loop once and return the finished session.

    Args:
        query:    what the user asked for, in plain language
                  (e.g. "vintage graphic tee under $30, size M").
        wardrobe: a wardrobe dict — get_example_wardrobe() or
                  get_empty_wardrobe() from utils/data_loader.py.

    Returns:
        The session dict. **Check session["error"] first** — if it isn't None,
        the run ended early and the later fields will still be None.

    How it works: each time round the loop, `next_step` says which tool runs,
    and the tool's result decides what `next_step` becomes. Every tool reads
    its inputs from the session and writes its result back into it.

        search  -> parse the query, call search_listings
                   THE BRANCH: empty list -> session["error"], stop
                               otherwise  -> "select"
        select  -> session["selected_item"] = the first result -> "suggest"
        suggest -> suggest_outfit(selected_item, wardrobe)      -> "card"
        card    -> create_fit_card(outfit_suggestion, selected_item) -> stop

    IN UNIT 4 you come back and add two things:

      • Trace calls. One per step. `trace.step("search_listings", inputs=...,
        returned=...)` — see trace.py. Your README needs the output.

      • A handler for ModelUnavailable, so a bad key produces a message rather
        than a stack trace. The import is already at the top of this file.
    """
    # A wardrobe with no "items" list counts as an empty wardrobe.
    if not isinstance(wardrobe, dict) or not isinstance(wardrobe.get("items"), list):
        wardrobe = {"items": []}

    session = new_session(query, wardrobe)

    next_step = "search"
    count = 0
    while next_step:
        count += 1
        trace.check_iterations(count)

        if next_step == "search":
            session["parsed"] = _parse_query(session["query"])
            session["search_results"] = search_listings(
                session["parsed"]["description"],
                session["parsed"]["size"],
                session["parsed"]["max_price"],
            )
            # THE BRANCH. Nothing came back: say what to change, and stop
            # before suggest_outfit ever runs.
            if not session["search_results"]:
                session["error"] = _no_match_message(session["parsed"])
                next_step = None
            else:
                next_step = "select"

        elif next_step == "select":
            session["selected_item"] = session["search_results"][0]
            next_step = "suggest"

        elif next_step == "suggest":
            session["outfit_suggestion"] = suggest_outfit(
                session["selected_item"], session["wardrobe"]
            )
            next_step = "card"

        elif next_step == "card":
            session["fit_card"] = create_fit_card(
                session["outfit_suggestion"], session["selected_item"]
            )
            next_step = None

    return session


# ── running it directly ───────────────────────────────────────────────────────

def _show(session: dict) -> None:
    if session["error"]:
        print(f"  stopped: {session['error']}")
        print(f"  fit_card is {session['fit_card']!r} — it should still be None here")
        return

    item = session["selected_item"] or {}
    print(f"  found:    {item.get('title')} — ${item.get('price')} on {item.get('platform')}")
    print(f"  outfit:   {session['outfit_suggestion']}")
    print(f"  fit card: {session['fit_card']}")


if __name__ == "__main__":
    from utils.data_loader import get_example_wardrobe

    print("=== A query the data can match ===")
    _show(run_agent(
        query="looking for a vintage graphic tee under $30",
        wardrobe=get_example_wardrobe(),
    ))

    print("\n=== A query it can't ===")
    _show(run_agent(
        query="designer ballgown size XXS under $5",
        wardrobe=get_example_wardrobe(),
    ))

    print(
        "\nThe second one should stop before the fit card. If both paths look "
        "the same,\nthe branch isn't doing anything yet."
    )
