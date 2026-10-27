"""
The three FitFindr tools.

Each one is a standalone function you can call and test on its own, before any
of them are wired into the loop. Build and test them one at a time — three
untested tools joined by a loop is one problem that looks like six, because you
can't tell which layer is lying to you.

    search_listings(description, size, max_price)  → list[dict]
    suggest_outfit(new_item, wardrobe)             → str
    create_fit_card(outfit, new_item)              → str

The contract for each one — inputs with types, what comes back, and what comes
back when there is nothing — is written in the Tool Inventory section of the
README. The code here follows that spec; if the two ever disagree, the README
is the one to fix first.
"""

import re

import config
from generate import generate
from utils.data_loader import load_listings


# ── Tool 1: search_listings ───────────────────────────────────────────────────

# Words that carry no search signal. "under", "size" and "length" show up in
# almost every query and would otherwise score noise against the descriptions.
_STOP_WORDS = {
    "a", "an", "the", "and", "or", "in", "on", "with", "for", "under", "over",
    "size", "length", "of", "to", "at", "by", "from", "is", "are", "something",
    "some", "me", "my", "i", "want", "need", "looking",
}

# Spelled-out sizes a person might type instead of the letter.
_WORD_SIZES = {
    "extra small": "XS",
    "small": "S",
    "medium": "M",
    "large": "L",
    "extra large": "XL",
    "xlarge": "XL",
    "x-large": "XL",
}


def _size_tokens(size: str) -> set[str]:
    """
    Split a listing's size string into comparable tokens.

        "S/M"                 -> {"S", "M"}
        "US 8.5"              -> {"US", "8.5"}
        "W30 L30"             -> {"W30", "L30"}
        "XL (fits oversized)" -> {"XL", "FITS", "OVERSIZED"}

    Tokens are compared whole, never as substrings, so "S" does not match
    "US 9" and "8" does not match "US 8.5".
    """
    return {token for token in re.split(r"[\s/()]+", size.upper()) if token}


def _normalize_size(request: str) -> str:
    """Turn what the user asked for into one token: 'size 8' -> '8', 'medium' -> 'M'."""
    text = request.strip().lower()
    text = re.sub(r"^(?:size|us)\s+", "", text).strip()
    if text in _WORD_SIZES:
        return _WORD_SIZES[text]
    return text.upper()


def _size_matches(listing_size: str, request: str) -> bool:
    tokens = _size_tokens(listing_size)
    if {"ONE", "SIZE"} <= tokens:
        return True  # One Size fits anyone, so it passes every size filter
    return _normalize_size(request) in tokens


def _keywords(text: str) -> list[str]:
    """Lowercase words from the description, minus stop words and bare numbers."""
    keywords: list[str] = []
    for word in re.findall(r"[a-z0-9]+", text.lower()):
        if word in _STOP_WORDS or word.isdigit() or len(word) < 2:
            continue
        if word not in keywords:
            keywords.append(word)
    return keywords


def _hits(word: str, haystack: str) -> bool:
    """Whole-word match, allowing a trailing-s plural either way (tee/tees, sneakers/sneaker)."""
    forms = {word, word + "s"}
    if word.endswith("s") and len(word) >= 4:
        forms.add(word[:-1])
    pattern = r"\b(?:" + "|".join(re.escape(form) for form in forms) + r")\b"
    return re.search(pattern, haystack) is not None


def _score(listing: dict, keywords: list[str]) -> int:
    """One point per keyword found anywhere, plus one more if it is in the title."""
    title = listing["title"].lower()
    everything = " ".join(
        [
            listing["title"],
            listing["description"],
            " ".join(listing["style_tags"]),
            listing["category"],
            " ".join(listing["colors"]),
        ]
    ).lower()

    score = 0
    for keyword in keywords:
        if _hits(keyword, everything):
            score += 1
            if _hits(keyword, title):
                score += 1
    return score


def search_listings(
    description: str,
    size: str | None = None,
    max_price: float | None = None,
) -> list[dict]:
    """
    Search the listings data for items matching a description, and optionally a
    size and a price ceiling.

    This is the tool that doesn't call the model, which makes it the easiest one
    to test and the one to move onto MCP in unit 4.

    Args:
        description: keywords describing what the user wants
                     (e.g. "vintage graphic tee").
        size:        a size string to filter by, or None to skip size filtering.
                     Matched token-for-token against the listing's size, so "M"
                     matches "M", "S/M" and "M/L" but "S" never matches "US 9".
                     See _size_tokens() for the rule.
        max_price:   maximum price, inclusive, or None to skip price filtering.

    Returns:
        A list of matching listing dicts, best match first, at most
        config.SEARCH_RESULT_LIMIT of them. Each dict is the unmodified record
        from data/listings.json with the fields:
            id, title, description, category, style_tags (list), size,
            condition, price (float), colors (list), brand (str or None), platform

        **Returns an empty list when nothing matches — an empty list, not None,
        and not an exception.** The loop branches on this. It is also empty
        when the description has no usable keywords.

    Test it from a terminal before you move on:
        python -c "from tools import search_listings; print(search_listings('graphic tee', max_price=30))"
    """
    keywords = _keywords(description or "")
    if not keywords:
        return []

    scored: list[tuple[int, dict]] = []
    for listing in load_listings():
        if max_price is not None and listing["price"] > float(max_price):
            continue
        if size and size.strip() and not _size_matches(listing["size"], size):
            continue
        score = _score(listing, keywords)
        if score > 0:
            scored.append((score, listing))

    # Best score first; among equal scores, the cheaper one first.
    scored.sort(key=lambda pair: (-pair[0], pair[1]["price"]))
    return [listing for _, listing in scored[: config.SEARCH_RESULT_LIMIT]]


# ── shared prompt pieces ──────────────────────────────────────────────────────

def _money(price) -> str:
    """38.0 -> '$38', 8.5 -> '$8.5'."""
    try:
        return f"${float(price):g}"
    except (TypeError, ValueError):
        return f"${price}"


def _describe_item(item: dict) -> str:
    """The listing, laid out for a prompt. Brand is often None in this data."""
    return "\n".join(
        [
            f"Item: {item.get('title')}",
            f"Category: {item.get('category')}; size {item.get('size')}; "
            f"condition {item.get('condition')}",
            f"Colors: {', '.join(item.get('colors') or []) or 'not listed'}",
            f"Style tags: {', '.join(item.get('style_tags') or []) or 'none'}",
            f"Brand: {item.get('brand') or 'no brand listed'}",
            f"Price: {_money(item.get('price'))} on {item.get('platform')}",
            f"Listing notes: {item.get('description')}",
        ]
    )


def _describe_wardrobe(items: list[dict]) -> str:
    lines = []
    for piece in items:
        details = [
            piece.get("category") or "",
            ", ".join(piece.get("colors") or []),
            ", ".join(piece.get("style_tags") or []),
        ]
        line = f"- {piece.get('name')} ({'; '.join(d for d in details if d)})"
        if piece.get("notes"):
            line += f" — {piece['notes']}"
        lines.append(line)
    return "\n".join(lines)


# ── Tool 2: suggest_outfit ────────────────────────────────────────────────────

_STYLIST_SYSTEM = (
    "You are a friendly personal stylist for secondhand fashion. Answer in plain "
    "text: no markdown headings, no bold, no numbered lists, at most 120 words. "
    "Suggest one or two complete outfits built around the new item. When the "
    "user's wardrobe is given, every outfit must name at least one piece from it "
    "exactly as written. When no wardrobe is given, build the outfits from common "
    "basics most people own."
)


def suggest_outfit(new_item: dict, wardrobe: dict) -> str:
    """
    Given a thrifted item and the user's wardrobe, suggest one or two outfits.

    This one calls the model, through `generate()`. You don't need to think
    about rate limits — the adapter handles pacing for you.

    Args:
        new_item: a listing dict — the item the user is considering.
        wardrobe: a wardrobe dict with an 'items' key holding a list of items.
                  **It may be empty.** An empty list, a missing key or None all
                  count as "nothing saved".

    Returns:
        A non-empty string with outfit suggestions. With a wardrobe, the
        outfits name pieces the user owns. With an empty wardrobe, general
        styling advice built around common basics. Never "" — if the model
        returns nothing, a fixed fallback sentence comes back instead.

    Test it from a terminal before you move on:
        python -c "from tools import suggest_outfit; from utils.data_loader import get_example_wardrobe, load_listings; print(suggest_outfit(load_listings()[0], get_example_wardrobe()))"
    """
    items = (wardrobe or {}).get("items") or []
    intro = (
        "A user is thinking about buying this secondhand item:\n\n"
        f"{_describe_item(new_item)}\n\n"
    )

    if items:
        prompt = intro + (
            "They already own these pieces:\n"
            f"{_describe_wardrobe(items)}\n\n"
            "Suggest one or two outfits that combine the new item with pieces "
            "they already own. Name the owned pieces exactly as listed, and say "
            "in a few words why each outfit works."
        )
    else:
        prompt = intro + (
            "They have not saved a wardrobe yet, so you do not know what they "
            "own. Give general styling advice: suggest one or two outfits built "
            "around common basics (for example jeans, a plain tee, a neutral "
            "jacket, white sneakers), and say in a few words why each works."
        )

    response = generate(prompt, system=_STYLIST_SYSTEM)
    if not response or not response.strip():
        return (
            f"No outfit suggestion could be generated for {new_item.get('title')}; "
            "pair it with neutral basics."
        )
    return response


# ── Tool 3: create_fit_card ───────────────────────────────────────────────────

_CAPTION_SYSTEM = (
    "You write short captions for social posts about secondhand fashion finds. "
    "Write two to four sentences in the first person, in plain text: no "
    "hashtags, no markdown, no list formatting. Mention the item's name, its "
    "price with a dollar sign, and the platform it was found on exactly once "
    "each. Be specific about the vibe and name the pieces it is styled with. "
    "It should read like a real post, not a product description."
)


def create_fit_card(outfit: str, new_item: dict) -> str:
    """
    Write a short caption someone would actually post about the find.

    This calls the model too.

    Args:
        outfit:   the outfit suggestion string from suggest_outfit().
        new_item: the listing dict for the item.

    Returns:
        A two-to-four sentence caption that mentions the item, its price and
        its platform once each. If `outfit` is empty or whitespace, the model
        is not called and a one-sentence message naming the item comes back
        instead of an exception.

    It should come out **differently for different inputs**. If you run this
    three times on the same item and get three word-for-word identical strings,
    it's one of two things, and both are near the top of `config.py`:

        • CACHE_ENABLED — the adapter handed back an answer it already had
        • TEMPERATURE   — at 0.0 the model gives the same words every time

    Test it from a terminal before you move on:
        python -c "from tools import create_fit_card; from utils.data_loader import load_listings; print(create_fit_card('jeans and white sneakers', load_listings()[0]))"
    """
    title = new_item.get("title")
    price = _money(new_item.get("price"))
    platform = new_item.get("platform")

    if not outfit or not outfit.strip():
        return f"No outfit suggestion was available for {title}, so no fit card was written."

    prompt = (
        "The find:\n"
        f"{_describe_item(new_item)}\n\n"
        "How it is being styled:\n"
        f"{outfit}\n\n"
        f'Write the caption. Mention "{title}", the price {price} and {platform} '
        "once each."
    )

    response = generate(prompt, system=_CAPTION_SYSTEM)
    if not response or not response.strip():
        return (
            f"Just found {title} for {price} on {platform}. "
            f"Styling it like this: {outfit.strip()[:120]}"
        )
    return response
