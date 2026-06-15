"""
agent.py

The FitFindr planning loop. Orchestrates the three tools in response to a
natural language user query, passing state between them via a session dict.

Complete tools.py and test each tool in isolation before implementing this file.

Usage (once implemented):
    from agent import run_agent
    from utils.data_loader import get_example_wardrobe

    result = run_agent(
        query="vintage graphic tee under $30, size M",
        wardrobe=get_example_wardrobe(),
    )
    print(result["fit_card"])
    print(result["error"])   # None on success
"""

import logging
import re

from tools import search_listings, suggest_outfit, create_fit_card

TOOL_LOGGER = logging.getLogger("fitfindr.tools")


def setup_tool_logging() -> None:
    """Enable terminal output for the three FitFindr tool calls only."""
    if TOOL_LOGGER.handlers:
        return
    handler = logging.StreamHandler()
    handler.setFormatter(
        logging.Formatter("%(asctime)s %(message)s", datefmt="%H:%M:%S")
    )
    TOOL_LOGGER.addHandler(handler)
    TOOL_LOGGER.setLevel(logging.INFO)
    TOOL_LOGGER.propagate = False


# ── session state ─────────────────────────────────────────────────────────────

def _new_session(query: str, wardrobe: dict) -> dict:
    """
    Initialize and return a fresh session dict for one user interaction.

    The session dict is the single source of truth for everything that happens
    during a run — it stores the original query, parsed parameters, tool results,
    and any error that caused early termination.

    You may add fields to this dict as needed for your implementation.
    """
    return {
        "query": query,              # original user query
        "parsed": {},                # extracted description / size / max_price
        "search_results": [],        # list of matching listing dicts
        "selected_item": None,       # top result, passed into suggest_outfit
        "wardrobe": wardrobe,        # user's wardrobe dict
        "outfit_suggestion": None,   # string returned by suggest_outfit
        "fit_card": None,            # string returned by create_fit_card
        "error": None,               # set if the interaction ended early
    }


# ── query parsing ─────────────────────────────────────────────────────────────

def _parse_query(query: str) -> dict:
    """Extract description, size, and max_price from a natural language query."""
    text = query.strip()
    max_price = None
    size = None

    price_match = re.search(
        r"(?:under|below|max|less than)\s*\$?(\d+(?:\.\d+)?)",
        text,
        re.IGNORECASE,
    )
    if price_match:
        max_price = float(price_match.group(1))
        text = (text[: price_match.start()] + text[price_match.end() :]).strip()

    size_match = re.search(r"size[:\s]+([A-Za-z0-9/]+)", text, re.IGNORECASE)
    if size_match:
        size = size_match.group(1)
        text = (text[: size_match.start()] + text[size_match.end() :]).strip()

    text = re.sub(r"[,;]+$", "", text).strip()
    text = re.sub(
        r"^(?:looking for|i(?:'m| am) looking for|find(?: me)?)\s+",
        "",
        text,
        flags=re.IGNORECASE,
    ).strip()
    description = text if text else query.strip()

    return {"description": description, "size": size, "max_price": max_price}


def _no_results_message(parsed: dict) -> str:
    desc = parsed.get("description", "your search")
    msg = f"No listings found for '{desc}'"
    if parsed.get("max_price") is not None:
        msg += f" under ${parsed['max_price']:.0f}"
    if parsed.get("size"):
        msg += f" in size {parsed['size']}"
    return (
        msg + ". Try a broader search term, a higher budget, or drop the size filter."
    )


# ── planning loop ─────────────────────────────────────────────────────────────

def run_agent(query: str, wardrobe: dict) -> dict:
    """
    Main agent entry point. Runs the FitFindr planning loop for a single
    user interaction and returns the completed session dict.

    Args:
        query:    Natural language user request
                  (e.g., "vintage graphic tee under $30, size M")
        wardrobe: User's wardrobe dict — use get_example_wardrobe() or
                  get_empty_wardrobe() from utils/data_loader.py

    Returns:
        The session dict after the interaction completes. Check session["error"]
        first — if it is not None, the interaction ended early and the other
        output fields (outfit_suggestion, fit_card) will be None.

    TODO — implement this function using the planning loop you designed in planning.md:

        Step 1: Initialize the session with _new_session().

        Step 2: Parse the user's query to extract a description, size, and
                max_price. You can use regex, string splitting, or ask the LLM
                to parse it — document your choice in planning.md.
                Store the result in session["parsed"].

        Step 3: Call search_listings() with the parsed parameters.
                Store results in session["search_results"].
                If no results: set session["error"] to a helpful message and
                return the session early. Do NOT proceed to suggest_outfit
                with empty input.

        Step 4: Select the item to use (e.g., the top result).
                Store it in session["selected_item"].

        Step 5: Call suggest_outfit() with the selected item and wardrobe.
                Store the result in session["outfit_suggestion"].

        Step 6: Call create_fit_card() with the outfit suggestion and selected item.
                Store the result in session["fit_card"].

        Step 7: Return the session.

    Before writing code, complete the Planning Loop and State Management sections
    of planning.md — your implementation should match what you described there.
    """
    session = _new_session(query, wardrobe)

    parsed = _parse_query(query)
    session["parsed"] = parsed

    TOOL_LOGGER.info(
        "search_listings(description=%r, size=%r, max_price=%r)",
        parsed["description"],
        parsed.get("size"),
        parsed.get("max_price"),
    )
    session["search_results"] = search_listings(
        parsed["description"],
        parsed.get("size"),
        parsed.get("max_price"),
    )

    if not session["search_results"]:
        session["error"] = _no_results_message(parsed)
        return session

    session["selected_item"] = session["search_results"][0]

    wardrobe_count = len(session["wardrobe"].get("items", []))
    TOOL_LOGGER.info(
        "suggest_outfit(item=%r, wardrobe_items=%d)",
        session["selected_item"]["title"],
        wardrobe_count,
    )
    session["outfit_suggestion"] = suggest_outfit(
        session["selected_item"], session["wardrobe"]
    )
    if session["outfit_suggestion"].startswith("Couldn't generate outfit suggestions"):
        session["error"] = session["outfit_suggestion"]
        return session

    TOOL_LOGGER.info(
        "create_fit_card(item=%r)",
        session["selected_item"]["title"],
    )
    session["fit_card"] = create_fit_card(
        session["outfit_suggestion"], session["selected_item"]
    )
    if session["fit_card"].startswith("Can't create a fit card") or session[
        "fit_card"
    ].startswith("Fit card generation failed"):
        session["error"] = session["fit_card"]
        session["fit_card"] = None
        return session

    return session


# ── CLI test ──────────────────────────────────────────────────────────────────

if __name__ == "__main__":
    setup_tool_logging()
    from utils.data_loader import get_example_wardrobe, get_empty_wardrobe

    print("=== Happy path: graphic tee ===\n")
    session = run_agent(
        query="looking for a vintage graphic tee under $30",
        wardrobe=get_example_wardrobe(),
    )
    if session["error"]:
        print(f"Error: {session['error']}")
    else:
        print(f"Found: {session['selected_item']['title']}")
        print(f"\nOutfit: {session['outfit_suggestion']}")
        print(f"\nFit card: {session['fit_card']}")

    print("\n\n=== No-results path ===\n")
    session2 = run_agent(
        query="designer ballgown size XXS under $5",
        wardrobe=get_example_wardrobe(),
    )
    print(f"Error message: {session2['error']}")
