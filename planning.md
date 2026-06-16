# FitFindr — planning.md

> Complete this document before writing any implementation code.
> Your spec and agent diagram are what you'll use to direct AI tools (Claude, Copilot, etc.) to generate your implementation — the more specific they are, the more useful the generated code will be.
> Your planning.md will be reviewed as part of your submission.
> Update it before starting any stretch features.

---

## Tools

List every tool your agent will use. For each tool, fill in all four fields.
You must have at least 3 tools. The three required tools are listed — add any additional tools below them.

### Tool 1: search_listings

**What it does:**
Searches the mock listings dataset for items matching a text description, optional size, and optional max price. Returns matching listings sorted by relevance (best match first), or an empty list if nothing matches.

**Input parameters:**
- `description` (str): Keywords describing what the user wants (e.g., `"vintage graphic tee"`). Matched against each listing's `title`, `description`, and `style_tags` via keyword overlap scoring.
- `size` (str | None): Size to filter by, or `None` to skip size filtering. Case-insensitive substring match (e.g., `"M"` matches `"S/M"` or `"M"`).
- `max_price` (float | None): Maximum price inclusive, or `None` to skip price filtering. Only listings where `price <= max_price` are kept.

**What it returns:**
A `list[dict]` of matching listing dicts, sorted by relevance score (highest first). Each dict contains:
`id`, `title`, `description`, `category`, `style_tags` (list[str]), `size`, `condition`, `price` (float), `colors` (list[str]), `brand` (str or None), `platform` (str: depop, thredUp, or poshmark).

Returns `[]` if no listings match — does not raise an exception.

**What happens if it fails or returns nothing:**
The function returns an empty list. The agent sets `session["error"]` to a specific message (e.g., *"No listings matched your search. Try broadening your description, removing the size filter, or raising your max price."*), leaves `selected_item`, `outfit_suggestion`, and `fit_card` as `None`, and returns early. It does **not** call `suggest_outfit` or `create_fit_card`.

---

### Tool 2: suggest_outfit

**What it does:**
Given a thrifted listing the user is considering and their existing wardrobe, suggests 1–2 complete outfit combinations using Groq (llama-3.3-70b-versatile). If the wardrobe is empty, returns general styling advice for the item instead of wardrobe-specific pairings.

**Input parameters:**
- `new_item` (dict): A listing dict from `search_listings` — must include at least `title`, `description`, `category`, `style_tags`, `colors`, and `price`.
- `wardrobe` (dict): User's wardrobe with an `items` key containing a list of wardrobe item dicts. Each item has `id`, `name`, `category`, `colors`, `style_tags`, and optional `notes`. May be empty (`items: []`).

**What it returns:**
A non-empty `str` with 1–2 outfit suggestions written in plain language (e.g., *"Pair this with your baggy straight-leg jeans and chunky sneakers for a classic streetwear look."*). If the wardrobe is empty, returns general styling advice (what categories/colors/vibes pair well) rather than naming specific wardrobe pieces.

**What happens if it fails or returns nothing:**
If `wardrobe["items"]` is empty, the tool still returns a useful string (general styling ideas) — this is not a hard failure. If the LLM call fails or returns empty text, the tool returns a fallback message string (e.g., *"Couldn't generate outfit suggestions right now. Try again, or style this as a [category] piece with neutral basics."*). The agent stores whatever string is returned in `session["outfit_suggestion"]` and proceeds to `create_fit_card` unless the string is clearly an error — in that case, set `session["error"]` and stop.

---

### Tool 3: create_fit_card

**What it does:**
Generates a short, casual, shareable outfit caption (2–4 sentences) for the thrifted find and suggested outfit — the kind of caption someone would post on Instagram or TikTok. Uses Groq (llama-3.3-70b-versatile) with higher temperature so outputs vary for different inputs.

**Input parameters:**
- `outfit` (str): The outfit suggestion string from `suggest_outfit()`.
- `new_item` (dict): The listing dict for the thrifted item — used for `title`, `price`, and `platform` in the caption.

**What it returns:**
A `str` caption (2–4 sentences) that mentions the item name, price, and platform naturally once each, captures the outfit vibe, and sounds authentic — not like a product listing. If `outfit` is empty or whitespace-only, returns a descriptive error message string instead of raising an exception.

**What happens if it fails or returns nothing:**
If `outfit` is missing or empty, the tool returns an error message string (e.g., *"Can't create a fit card without an outfit suggestion."*). The agent checks whether the return value looks like an error; if so, sets `session["error"]` and leaves `session["fit_card"]` as `None`. If the LLM call fails, the agent sets `session["error"]` to *"Fit card generation failed — your outfit suggestion is still available above."* and does not crash.

---

### Additional Tools (if any)

None — retry logic is implemented in the planning loop, not as a separate tool.

---

## Stretch Feature: Retry Logic with Fallback

**What it does:**
If the initial `search_listings` call returns no results, the agent automatically retries with loosened constraints before giving up.

**Retry order:**
1. Original search with all parsed filters (`description`, `size`, `max_price`).
2. If empty and `size` was set → retry with `size=None`, same `max_price`.
3. If still empty and `max_price` was set → retry with `size=None`, `max_price=None`.

**User notification:**
If a retry succeeds, store a note in `session["search_adjustment"]` (e.g., *"No exact matches in size XXS — retried without the size filter."*). `handle_query()` prepends this to the listing panel so the user knows what changed.

**If all retries fail:**
Same error path as before — set `session["error"]` and return early.

---

## Planning Loop

**How does your agent decide which tool to call next?**

`run_agent(query, wardrobe)` in `agent.py` runs a linear planning loop with conditional early exits — not a fixed blind sequence.

1. **Initialize:** Create session via `_new_session(query, wardrobe)`.

2. **Parse query:** Extract `description`, `size`, and `max_price` from the natural language query using regex (e.g., `under $30` → `max_price=30.0`, `size M` → `size="M"`). Store in `session["parsed"]`. If no description can be extracted, default description to the full query string.

3. **Search branch:** Call `search_listings(parsed["description"], parsed.get("size"), parsed.get("max_price"))`. Store result in `session["search_results"]`.
   - **If `search_results` is empty:** Retry with loosened constraints (stretch feature): drop size filter first, then drop price limit. Store any adjustment note in `session["search_adjustment"]` so the UI can tell the user what changed.
   - **If still empty after retries:** Set `session["error"]` with actionable advice, return session immediately. Do **not** call `suggest_outfit` or `create_fit_card`.
   - **If results exist:** Set `session["selected_item"] = search_results[0]` (top match by relevance).

4. **Suggest branch:** Call `suggest_outfit(session["selected_item"], session["wardrobe"])`. Store in `session["outfit_suggestion"]`. Always proceed — empty wardrobe is handled inside the tool, not by skipping this step.

5. **Fit card branch:** Call `create_fit_card(session["outfit_suggestion"], session["selected_item"])`. Store in `session["fit_card"]`. If the tool returns an error message string, set `session["error"]` accordingly.

6. **Done:** Return session. Success = `session["error"]` is `None` and all three outputs are populated.

The agent knows it's done when either (a) an error was set and the loop returned early, or (b) all three tools ran and `fit_card` is set.

---

## State Management

**How does information from one tool get passed to the next?**

All state lives in a single `session` dict returned by `run_agent()`. No re-prompting the user between steps.

| Field | Set when | Used by |
|-------|----------|---------|
| `query` | Session init | Reference / display |
| `parsed` | After query parsing | Input to `search_listings` |
| `search_results` | After `search_listings` | Source for `selected_item` |
| `selected_item` | After search succeeds (`results[0]`) | Passed to `suggest_outfit` and `create_fit_card` |
| `wardrobe` | Session init (from caller) | Passed to `suggest_outfit` |
| `outfit_suggestion` | After `suggest_outfit` | Passed to `create_fit_card` |
| `fit_card` | After `create_fit_card` | Final user-facing output |
| `search_adjustment` | After a successful retry with loosened filters | Shown in listing panel so user knows what changed |
| `error` | On early exit or tool failure | Checked first in UI; other outputs may be `None` |

The same `selected_item` dict object flows from search → suggest → fit card without the user re-entering it. `app.py`'s `handle_query()` reads the session dict and maps fields to the three Gradio output panels.

---

## Error Handling

For each tool, describe the specific failure mode you're handling and what the agent does in response.

| Tool | Failure mode | Agent response |
|------|-------------|----------------|
| search_listings | No results match the query (even after retry — see Stretch Feature) | Set `session["error"]` to: *"No listings found for '[description]' under $[max_price] in size [size]. Try a broader search term, a higher budget, or drop the size filter."* Return session early with `fit_card=None`. Tell the user in the UI error panel — do not call downstream tools. |
| suggest_outfit | Wardrobe is empty | Tool returns general styling advice (not an error). Agent proceeds normally and notes in the outfit panel that suggestions are general since no wardrobe items were provided. |
| suggest_outfit | LLM call fails or returns empty text | Tool returns fallback: *"Couldn't generate outfit suggestions right now. Try again, or style this as a [category] piece with neutral basics."* Agent sets `session["error"]` to that message and returns early — does not call `create_fit_card`. |
| create_fit_card | Outfit input is missing or incomplete | Tool returns error string. Agent sets `session["error"]` to that message, keeps `outfit_suggestion` visible, and shows the user: *"Couldn't generate a fit card — here's your outfit suggestion instead."* |

---

## Architecture

### Components

| Component | File | Role |
|-----------|------|------|
| **UI** | `app.py` | Gradio interface — user types a query, picks a wardrobe, sees 3 output panels |
| **Planning loop** | `agent.py` | `run_agent()` orchestrates tools, owns the `session` dict, branches on results |
| **Tools** | `tools.py` | `search_listings`, `suggest_outfit`, `create_fit_card` — each standalone and testable |
| **Data** | `utils/data_loader.py` | `load_listings()`, `get_example_wardrobe()`, `get_empty_wardrobe()` |
| **Datasets** | `data/listings.json`, `data/wardrobe_schema.json` | Mock listings + wardrobe schema |

### End-to-end flow (happy path)

1. **User input (app.py)**  
   User types a natural language query (e.g. *"vintage graphic tee under $30, size M"*) and selects a wardrobe ("Example wardrobe" or "Empty wardrobe"). Gradio calls `handle_query(user_query, wardrobe_choice)`.

2. **Wardrobe selection (app.py → agent.py)**  
   `handle_query` loads the wardrobe dict via `get_example_wardrobe()` or `get_empty_wardrobe()`, then calls `run_agent(query, wardrobe)`.

3. **Session init (agent.py)**  
   `run_agent` creates a fresh `session` dict via `_new_session()`. All fields start empty/`None` except `query`, `wardrobe`, and `error=None`.

4. **Query parsing (agent.py)**  
   Regex extracts search params from the query string:
   - `under $30` / `max $30` → `max_price: 30.0`
   - `size M` / `size: M` → `size: "M"`
   - Remaining text → `description` (falls back to full query if nothing else matches)  
   Stored in `session["parsed"]` = `{"description": "...", "size": "M" or None, "max_price": 30.0 or None}`.

5. **Tool 1 — search_listings (tools.py ← data/listings.json)**  
   Agent calls `search_listings(parsed["description"], parsed.get("size"), parsed.get("max_price"))`.  
   Inside the tool: `load_listings()` → filter by price/size → score by keyword overlap → sort by relevance.  
   Result stored in `session["search_results"]` (list of listing dicts).

6. **Branch: search succeeded**  
   Agent sets `session["selected_item"] = search_results[0]` — the **same dict object** passed to later tools. No user re-entry.

7. **Tool 2 — suggest_outfit (tools.py ← Groq LLM)**  
   Agent calls `suggest_outfit(selected_item, wardrobe)`.  
   Tool formats the listing + full wardrobe into prompt text, calls Groq (`llama-3.3-70b-versatile`).  
   If wardrobe is empty → general styling advice; otherwise → names specific wardrobe pieces.  
   Result stored in `session["outfit_suggestion"]` (string).

8. **Tool 3 — create_fit_card (tools.py ← Groq LLM)**  
   Agent calls `create_fit_card(outfit_suggestion, selected_item)`.  
   Tool builds a caption prompt from the outfit string + listing details, calls Groq at higher temperature.  
   Result stored in `session["fit_card"]` (string).

9. **Return to UI (agent.py → app.py)**  
   `run_agent` returns the completed `session`. `handle_query` maps:
   - `selected_item` → formatted listing text (title, price, platform, condition)
   - `outfit_suggestion` → outfit panel
   - `fit_card` → fit card panel

### Error path (search returns nothing)

Steps 1–5 run the same. At step 6, if `search_results == []`:
- Agent sets `session["error"]` with actionable message (broaden search, raise budget, drop size filter)
- Returns session **immediately** — `suggest_outfit` and `create_fit_card` are **never called**
- `selected_item`, `outfit_suggestion`, `fit_card` stay `None`
- UI shows error in the first panel; other two panels empty

This is the key adaptive behavior: the agent does **not** run all three tools unconditionally.

### Diagram

User (Gradio UI — app.py)
    │  query: "vintage graphic tee under $30, size M"
    │  wardrobe: "Example wardrobe"
    ▼
handle_query()
    │  loads get_example_wardrobe() → wardrobe dict
    ▼
run_agent(query, wardrobe)                    ← agent.py
    │
    ├─► _new_session()                        session = { query, wardrobe, parsed:{}, ... }
    │
    ├─► Parse query (regex)                   session["parsed"] = { description, size, max_price }
    │
    ├─► search_listings(desc, size, max_price)    ← tools.py ← load_listings() ← listings.json
    │       │
    │       ├─► session["search_results"] = [listing, listing, ...]
    │       │
    │       ├── results = []  ──────────────────► session["error"] = "No listings found..."
    │       │                                      RETURN (suggest_outfit + create_fit_card SKIPPED)
    │       │
    │       └── results found ──────────────────► session["selected_item"] = results[0]
    │                                                  │
    ├─► suggest_outfit(selected_item, wardrobe)   ← tools.py ← Groq LLM
    │       │  formats listing dict + wardrobe items into prompt
    │       └─► session["outfit_suggestion"] = "Pair with your baggy jeans..."
    │                                                  │
    └─► create_fit_card(outfit_suggestion, selected_item)  ← tools.py ← Groq LLM
            └─► session["fit_card"] = "scored this tee off depop for $24..."
    │
    ▼
return session
    │
    ▼
handle_query() maps session → 3 UI panels
    ├─► Panel 1: selected_item formatted (title, $price, platform, condition)
    ├─► Panel 2: outfit_suggestion
    └─► Panel 3: fit_card
```

## AI Tool Plan

**Milestone 3 — Individual tool implementations:**

Use **Claude** (Cursor) for each tool, one at a time.

1. **search_listings:** Give Claude the Tool 1 block above (what it does, inputs, return value, failure mode) plus the TODO steps from `tools.py`. Ask it to implement using `load_listings()` from `utils/data_loader.py`. Verify before running: filters on all three params, keyword scoring on title/description/style_tags, sorts by score, returns `[]` not an exception on no match. Test with:
   - `search_listings("vintage graphic tee", size=None, max_price=50)` → non-empty list
   - `search_listings("designer ballgown", size="XXS", max_price=5)` → `[]`
   - `search_listings("jacket", size=None, max_price=10)` → all prices ≤ 10

2. **suggest_outfit:** Give Claude Tool 2 spec + wardrobe schema fields. Verify: handles empty `wardrobe["items"]` with general advice, uses Groq llama-3.3-70b-versatile, returns non-empty string. Test with `get_example_wardrobe()` and `get_empty_wardrobe()`.

3. **create_fit_card:** Give Claude Tool 3 spec + caption style guidelines from `tools.py` docstring. Verify: guards empty outfit string, uses temperature ≥ 0.8, outputs differ on repeated calls. Test with valid outfit string and with `outfit=""`.

Write pytest tests in `tests/test_tools.py` (one test per failure mode) and run `pytest tests/` before Milestone 4.

**Milestone 4 — Planning loop and state management:**

Use **Claude** with the Architecture diagram, Planning Loop section, and State Management section from this file. Ask it to implement `run_agent()` in `agent.py` matching the conditional branches above. Review generated code for:
- Early return when `search_results` is empty (no call to `suggest_outfit`)
- `selected_item` is exactly `search_results[0]`, not hardcoded
- Same dict passed through suggest → fit card
- `session["error"]` set on failure paths

Verify by running `python agent.py` (happy path + no-results path) and `python app.py` end-to-end. Print `session["selected_item"]` mid-run to confirm state flow.

---

## A Complete Interaction (Step by Step)

Write out what a full user interaction looks like from start to finish — tool call by tool call. Use a specific example query.

**Example user query:** "I'm looking for a vintage graphic tee under $30. I mostly wear baggy jeans and chunky sneakers. What's out there and how would I style it?"

**Step 1:**
Agent parses the query → `parsed = {"description": "vintage graphic tee", "size": None, "max_price": 30.0}`. Calls `search_listings("vintage graphic tee", size=None, max_price=30.0)`. Returns ~3 matching listings; top result is *"Graphic Tee — 2003 Tour Bootleg Style"* ($24, Depop, size L, good condition). Agent sets `session["selected_item"]` to that listing dict.

**Step 2:**
Agent calls `suggest_outfit(selected_item, get_example_wardrobe())`. Returns something like: *"Pair this vintage tee with your baggy straight-leg jeans and chunky white sneakers. Roll the sleeves once and let the tee hang slightly oversized for a 90s grunge vibe."* Stored in `session["outfit_suggestion"]`.

**Step 3:**
Agent calls `create_fit_card(outfit_suggestion, selected_item)`. Returns a casual caption like: *"scored this faded tour tee off depop for $24 and it's giving exactly the grunge energy i needed 🖤 baggy jeans + chunky sneakers = full fit."* Stored in `session["fit_card"]`. `session["error"]` remains `None`.

**Final output to user:**
Three panels in the Gradio UI:
1. **Search results:** Top match — Graphic Tee, $24, Depop, Good condition (+ other matches if shown)
2. **Outfit suggestion:** The pairing advice referencing baggy jeans and sneakers from the example wardrobe
3. **Fit card:** The shareable Instagram-style caption

**Error path (same query, impossible filters):** If the user had said *"designer ballgown size XXS under $5"*, Step 1 returns `[]`, agent sets error *"No listings found..."*, and the user sees only the error message — no outfit or fit card panels.
