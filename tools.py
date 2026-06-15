"""
tools.py

The three required FitFindr tools. Each tool is a standalone function that
can be called and tested independently before being wired into the agent loop.

Complete and test each tool before moving to agent.py.

Tools:
    search_listings(description, size, max_price)  → list[dict]
    suggest_outfit(new_item, wardrobe)              → str
    create_fit_card(outfit, new_item)               → str
"""
import os
from dotenv import load_dotenv
from groq import Groq

from utils.data_loader import load_listings

load_dotenv()

MODEL = "llama-3.3-70b-versatile"


# ── Groq client ───────────────────────────────────────────────────────────────

def _get_groq_client():
    """Initialize and return a Groq client using GROQ_API_KEY from .env."""
    api_key = os.environ.get("GROQ_API_KEY")
    if not api_key:
        raise ValueError(
            "GROQ_API_KEY not set. Add it to a .env file in the project root."
        )
    return Groq(api_key=api_key)


def _call_groq(system_prompt: str, user_prompt: str, temperature: float = 0.7) -> str:
    """Call Groq and return the assistant message text, or empty string on failure."""
    try:
        client = _get_groq_client()
        response = client.chat.completions.create(
            model=MODEL,
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_prompt},
            ],
            temperature=temperature,
        )
        return (response.choices[0].message.content or "").strip()
    except Exception:
        return ""


def _format_new_item(new_item: dict) -> str:
    tags = ", ".join(new_item.get("style_tags", []))
    colors = ", ".join(new_item.get("colors", []))
    return (
        f"Title: {new_item.get('title', 'Unknown item')}\n"
        f"Category: {new_item.get('category', 'unknown')}\n"
        f"Description: {new_item.get('description', '')}\n"
        f"Style tags: {tags}\n"
        f"Colors: {colors}\n"
        f"Price: ${new_item.get('price', 0):.2f}"
    )


def _format_wardrobe_items(items: list[dict]) -> str:
    lines = []
    for item in items:
        tags = ", ".join(item.get("style_tags", []))
        colors = ", ".join(item.get("colors", []))
        notes = item.get("notes") or ""
        line = (
            f"- {item.get('name', 'Unnamed')} ({item.get('category', 'unknown')}, "
            f"colors: {colors}, tags: {tags})"
        )
        if notes:
            line += f" — {notes}"
        lines.append(line)
    return "\n".join(lines)


# ── Tool 1: search_listings ───────────────────────────────────────────────────

def search_listings(
    description: str,
    size: str | None = None,
    max_price: float | None = None,
) -> list[dict]:
    """
    Search the mock listings dataset for items matching the description,
    optional size, and optional price ceiling.

    Args:
        description: Keywords describing what the user is looking for
                     (e.g., "vintage graphic tee").
        size:        Size string to filter by, or None to skip size filtering.
                     Matching is case-insensitive (e.g., "M" matches "S/M").
        max_price:   Maximum price (inclusive), or None to skip price filtering.

    Returns:
        A list of matching listing dicts, sorted by relevance (best match first).
        Returns an empty list if nothing matches — does NOT raise an exception.

    Each listing dict has the following fields:
        id, title, description, category, style_tags (list), size,
        condition, price (float), colors (list), brand, platform

    TODO:
        1. Load all listings with load_listings().
        2. Filter by max_price and size (if provided).
        3. Score each remaining listing by keyword overlap with `description`.
        4. Drop any listings with a score of 0 (no relevant matches).
        5. Sort by score, highest first, and return the listing dicts.

    Before writing code, fill in the Tool 1 section of planning.md.
    """
    listings = load_listings()
    keywords = [word.lower() for word in description.split() if word.strip()]

    def _score_listing(listing: dict) -> int:
        searchable = " ".join(
            [
                listing.get("title", ""),
                listing.get("description", ""),
                " ".join(listing.get("style_tags", [])),
            ]
        ).lower()
        return sum(1 for keyword in keywords if keyword in searchable)

    results: list[tuple[int, dict]] = []
    for listing in listings:
        if max_price is not None and listing["price"] > max_price:
            continue
        if size is not None and size.lower() not in listing["size"].lower():
            continue

        score = _score_listing(listing)
        if score > 0:
            results.append((score, listing))

    results.sort(key=lambda pair: pair[0], reverse=True)
    return [listing for _, listing in results]


# ── Tool 2: suggest_outfit ────────────────────────────────────────────────────

def suggest_outfit(new_item: dict, wardrobe: dict) -> str:
    """
    Given a thrifted item and the user's wardrobe, suggest 1–2 complete outfits.

    Args:
        new_item: A listing dict (the item the user is considering buying).
        wardrobe: A wardrobe dict with an 'items' key containing a list of
                  wardrobe item dicts. May be empty — handle this gracefully.

    Returns:
        A non-empty string with outfit suggestions.
        If the wardrobe is empty, offer general styling advice for the item
        rather than raising an exception or returning an empty string.

    TODO:
        1. Check whether wardrobe['items'] is empty.
        2. If empty: call the LLM with a prompt for general styling ideas
           (what kinds of items pair well, what vibe it suits, etc.).
        3. If not empty: format the wardrobe items into a prompt and ask
           the LLM to suggest specific outfit combinations using the new item
           and named pieces from the wardrobe.
        4. Return the LLM's response as a string.

    Before writing code, fill in the Tool 2 section of planning.md.
    """
    item_details = _format_new_item(new_item)
    category = new_item.get("category", "item")
    items = wardrobe.get("items", [])

    if not items:
        system_prompt = (
            "You are a personal stylist helping someone style a thrifted find. "
            "The user has not added any wardrobe items yet. "
            "Give general styling advice: what categories, colors, and vibes pair well. "
            "Suggest 1–2 complete outfit ideas using generic pieces (not specific owned items). "
            "Keep it practical and conversational — 2–4 short paragraphs max."
        )
        user_prompt = (
            f"The user is considering buying this thrifted item:\n\n{item_details}\n\n"
            "Suggest how to style it without referencing specific items they already own."
        )
    else:
        wardrobe_text = _format_wardrobe_items(items)
        system_prompt = (
            "You are a personal stylist. Suggest 1–2 complete outfit combinations "
            "using the thrifted item plus specific pieces from the user's wardrobe. "
            "Name wardrobe pieces exactly as listed. Be specific and conversational — "
            "2–4 short paragraphs max."
        )
        user_prompt = (
            f"Thrifted item the user wants to buy:\n\n{item_details}\n\n"
            f"User's wardrobe:\n{wardrobe_text}\n\n"
            "Suggest 1–2 outfits using the new item and named wardrobe pieces."
        )

    result = _call_groq(system_prompt, user_prompt)
    if result:
        return result

    return (
        f"Couldn't generate outfit suggestions right now. Try again, or style this "
        f"as a {category} piece with neutral basics."
    )


# ── Tool 3: create_fit_card ───────────────────────────────────────────────────

def create_fit_card(outfit: str, new_item: dict) -> str:
    """
    Generate a short, shareable outfit caption for the thrifted find.

    Args:
        outfit:   The outfit suggestion string from suggest_outfit().
        new_item: The listing dict for the thrifted item.

    Returns:
        A 2–4 sentence string usable as an Instagram/TikTok caption.
        If outfit is empty or missing, return a descriptive error message
        string — do NOT raise an exception.

    The caption should:
    - Feel casual and authentic (like a real OOTD post, not a product description)
    - Mention the item name, price, and platform naturally (once each)
    - Capture the outfit vibe in specific terms
    - Sound different each time for different inputs (use higher LLM temperature)

    TODO:
        1. Guard against an empty or whitespace-only outfit string.
        2. Build a prompt that gives the LLM the item details and the outfit,
           and asks for a caption matching the style guidelines above.
        3. Call the LLM and return the response.

    Before writing code, fill in the Tool 3 section of planning.md.
    """
    if not outfit or not outfit.strip():
        return "Can't create a fit card without an outfit suggestion."

    item_details = _format_new_item(new_item)
    platform = new_item.get("platform", "depop")

    system_prompt = (
        "You write casual Instagram/TikTok outfit captions — like a real OOTD post, "
        "not a product description. Write 2–4 sentences. Mention the item name, price, "
        "and platform naturally once each. Capture the outfit vibe in specific terms. "
        "Use lowercase, emojis sparingly, and sound authentic."
    )
    user_prompt = (
        f"Thrifted item:\n{item_details}\n\n"
        f"Outfit suggestion:\n{outfit.strip()}\n\n"
        f"Write a shareable caption for this fit."
    )

    result = _call_groq(system_prompt, user_prompt, temperature=0.9)
    if result:
        return result

    return (
        "Fit card generation failed — your outfit suggestion is still available above."
    )
