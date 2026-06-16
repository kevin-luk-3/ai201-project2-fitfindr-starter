# FitFindr

FitFindr is a multi-tool AI agent that helps users find secondhand clothing and figure out how to wear it. You describe what you want in plain English; the agent searches mock listings, suggests outfits using your wardrobe, and writes a shareable fit card caption.

## Setup

```bash
python -m venv .venv
.venv\Scripts\activate          # Windows PowerShell
pip install -r requirements.txt
```

Create a `.env` file in the project root:

```
GROQ_API_KEY=your_key_here
```

Get a free key at [console.groq.com](https://console.groq.com).

## Run

```bash
python app.py
```

Open the URL shown in your terminal (usually `http://localhost:7860`). Type a query, pick a wardrobe, and click **Find it**.

CLI test (no UI):

```bash
python agent.py
pytest tests/
```

---

## Tool Inventory

### `search_listings(description, size, max_price)` — `tools.py`

| | |
|---|---|
| **Purpose** | Search the mock listings dataset and return the best matches. |
| **Inputs** | `description` (str) — keywords to match against title, description, and style tags. `size` (str \| None) — case-insensitive substring filter (e.g. `"M"` matches `"S/M"`). `max_price` (float \| None) — inclusive price ceiling. |
| **Output** | `list[dict]` — matching listings sorted by relevance (keyword overlap score). Each dict has `id`, `title`, `description`, `category`, `style_tags`, `size`, `condition`, `price`, `colors`, `brand`, `platform`. Returns `[]` if nothing matches. |

### `suggest_outfit(new_item, wardrobe)` — `tools.py`

| | |
|---|---|
| **Purpose** | Suggest 1–2 complete outfits pairing a thrifted find with the user's wardrobe. |
| **Inputs** | `new_item` (dict) — listing dict from `search_listings`. `wardrobe` (dict) — wardrobe with an `items` list; may be empty. |
| **Output** | `str` — outfit suggestions in plain language. Uses Groq `llama-3.3-70b-versatile`. |

### `create_fit_card(outfit, new_item)` — `tools.py`

| | |
|---|---|
| **Purpose** | Generate a short, casual Instagram/TikTok-style caption for the outfit. |
| **Inputs** | `outfit` (str) — suggestion from `suggest_outfit`. `new_item` (dict) — listing dict for item name, price, and platform. |
| **Output** | `str` — 2–4 sentence shareable caption. Uses Groq at temperature 0.9 so outputs vary per run. |

---

## Planning Loop

`run_agent()` in `agent.py` runs a **conditional linear loop** — not a fixed sequence of all three tools.

1. **Init** — Create a fresh `session` dict via `_new_session(query, wardrobe)`.
2. **Parse** — Regex extracts `description`, `size`, and `max_price` from the user's query (e.g. `under $30` → `max_price=30.0`, `size M` → `size="M"`). Stored in `session["parsed"]`.
3. **Search** — Call `search_listings()` with parsed params.
   - **If results are empty:** Retry with loosened constraints (stretch feature): drop size filter first, then drop price limit. Store adjustment note in `session["search_adjustment"]`.
   - **If still empty after retries:** set `session["error"]` with actionable advice and **return immediately**. `suggest_outfit` and `create_fit_card` are never called.
   - **If results exist:** set `session["selected_item"] = search_results[0]` (top match by relevance score).
4. **Suggest** — Call `suggest_outfit(selected_item, wardrobe)`. If the LLM fails, store a fallback message and stop.
5. **Fit card** — Call `create_fit_card(outfit_suggestion, selected_item)`. If the tool returns an error string, set `session["error"]` and stop.
6. **Return** — Return the completed session to `app.py`.

The key decision: the agent **branches on search results**. A no-results query never reaches the LLM tools.

---

## State Management

All state lives in one `session` dict returned by `run_agent()`. The user never re-enters data between steps.

| Field | When set | Passed to |
|-------|----------|-----------|
| `parsed` | After regex parse | `search_listings` |
| `search_results` | After search | Source for `selected_item` |
| `selected_item` | After search succeeds | `suggest_outfit`, `create_fit_card` |
| `wardrobe` | Session init (from UI) | `suggest_outfit` |
| `outfit_suggestion` | After suggest | `create_fit_card` |
| `fit_card` | After fit card | UI panel 3 |
| `search_adjustment` | After successful retry | Prepended to listing panel |
| `error` | On failure / early exit | UI error panel |

The same `selected_item` dict object flows search → suggest → fit card. `handle_query()` in `app.py` maps session fields to the three Gradio output panels.

---

## Error Handling

| Tool | Failure mode | What happens |
|------|-------------|--------------|
| `search_listings` | No matches | Returns `[]`. Agent sets error: *"No listings found for '[description]' under $[price] in size [size]. Try a broader search term, a higher budget, or drop the size filter."* Returns early — downstream tools skipped. |
| `suggest_outfit` | Empty wardrobe | Not a failure — tool returns general styling advice. UI prefixes with *(General styling advice — no wardrobe items on file)*. |
| `suggest_outfit` | LLM call fails | Returns fallback: *"Couldn't generate outfit suggestions right now..."* Agent sets `session["error"]` and stops — does not call `create_fit_card`. |
| `create_fit_card` | Empty outfit string | Returns *"Can't create a fit card without an outfit suggestion."* Agent sets `session["error"]`, keeps outfit visible. |
| `create_fit_card` | LLM call fails | Returns *"Fit card generation failed — your outfit suggestion is still available above."* |

### Tested examples

**No search results** — query `"designer ballgown size XXS under $5"`:
```
No listings found for 'designer ballgown' under $5 in size XXS. Try a broader search term, a higher budget, or drop the size filter.
```
Outfit and fit card panels stay empty.

**Empty outfit input** — `create_fit_card("", item)`:
```
Can't create a fit card without an outfit suggestion.
```

**Empty wardrobe** — `suggest_outfit(item, get_empty_wardrobe())` returns general styling advice (e.g. pair with baggy jeans and sneakers) instead of crashing.

**Search retry** — query `"vintage graphic tee size XXS under $50"` returns no matches in XXS, but retry without the size filter finds results. Listing panel shows: *"No exact matches in size XXS — retried without the size filter."*

---

## Stretch Feature: Retry Logic with Fallback

If the initial search returns nothing, the agent automatically retries before giving up:

1. Original search with all parsed filters
2. Drop size filter (if one was set)
3. Drop price limit too (if still no results)

When a retry succeeds, `session["search_adjustment"]` tells the user what changed. Example: `"vintage graphic tee size XXS"` finds items after dropping the size filter.

---

## Spec Reflection

**How the spec helped:** Writing `planning.md` first forced me to define exact inputs, return types, and failure branches before coding. The architecture diagram made it obvious that search failure must short-circuit the loop — that became the first thing I verified in `run_agent()`.

**Where implementation diverged:** The spec said the agent should always proceed to `create_fit_card` after `suggest_outfit`, even on LLM failure. In practice, I added an early exit when `suggest_outfit` returns its error prefix (`"Couldn't generate outfit suggestions..."`) so the user doesn't get a fit card built from a broken outfit string. The empty-wardrobe case still proceeds as planned.

---

## AI Usage

### Instance 1 — Tool implementations (Milestone 3)

**Input given:** Tool 1–3 spec blocks from `planning.md` (inputs, return values, failure modes) plus the TODO steps in `tools.py`.

**What it produced:** Implementations of `search_listings` (keyword scoring + filters), `suggest_outfit` (Groq prompts for empty vs. populated wardrobe), and `create_fit_card` (caption prompt with temperature 0.9).

**What I changed:** Verified `search_listings` filters on all three params and returns `[]` not exceptions. Added `_format_new_item` and `_format_wardrobe_items` helpers to keep prompts readable. Wrote `tests/test_tools.py` with one test per failure mode before wiring the agent.

### Instance 2 — Planning loop (Milestone 4)

**Input given:** Architecture diagram, Planning Loop section, and State Management table from `planning.md`.

**What it produced:** `run_agent()` with `_parse_query()` regex, conditional early return on empty search, and session field wiring. `handle_query()` in `app.py` mapping session to three UI panels.

**What I changed:** Added `_no_results_message()` to include the parsed description, price, and size in the error text. Added tool-call logging via `setup_tool_logging()` so state passing is visible in the terminal during demos. Reviewed that `selected_item` is always `search_results[0]`, never hardcoded.

---

## Project Structure

```
├── agent.py              # Planning loop and session state
├── app.py                # Gradio UI
├── tools.py              # search_listings, suggest_outfit, create_fit_card
├── planning.md           # Pre-implementation spec
├── data/
│   ├── listings.json
│   └── wardrobe_schema.json
├── utils/data_loader.py
└── tests/test_tools.py
```

## Demo Video Checklist

Record a 3–5 minute video showing:

1. **Happy path** — full query through all 3 tools (search → outfit → fit card)
2. **State passing** — narrate or show terminal logs: `selected_item` from search flows into suggest and fit card
3. **Failure** — run `"designer ballgown size XXS under $5"` and show the agent's helpful error message
