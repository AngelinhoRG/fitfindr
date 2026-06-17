# FitFindr — Multi-Tool AI Agent

FitFindr is a three-tool AI agent that takes a natural language secondhand shopping query, finds matching listings in a mock dataset, generates outfit suggestions using the user's wardrobe, and produces a shareable fit-card caption. All three tools run in sequence through a planning loop that stops early and reports clearly if any stage produces nothing usable.

## Setup

**macOS / Linux:**
```bash
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
```

**Windows:**
```bash
python -m venv .venv
source .venv/Scripts/activate
pip install -r requirements.txt
```

Set your Groq API key in a `.env` file (get a free key at [console.groq.com](https://console.groq.com)):
```
GROQ_API_KEY=your_key_here
```

---

## Tool Inventory

### Tool 1: `search_listings`

**Purpose:** Loads all listings from `data/listings.json` and returns those that match the user's keywords, size, and price ceiling. No LLM call — pure data filtering.

**Inputs:**

| Parameter | Type | Description |
|-----------|------|-------------|
| `description` | `str` | Space-separated keywords matched case-insensitively against each listing's `title`, `description`, and `style_tags`. Example: `"vintage graphic tee"`. |
| `size` | `str \| None` | Exact size string for filtering (e.g. `"M"`, `"W30 L30"`). Matching is case-insensitive substring (so `"M"` matches `"S/M"`). Pass `None` to skip size filtering entirely. |
| `max_price` | `float \| None` | Maximum acceptable price, inclusive. Listings with `price > max_price` are excluded. Pass `None` to skip price filtering. |

**Output:** `list[dict]` — matching listing dicts sorted by relevance (keyword hit count) descending, then price ascending. Returns `[]` if nothing matches; never raises an exception.

Each dict contains: `id` (str), `title` (str), `description` (str), `category` (str), `style_tags` (list[str]), `size` (str), `condition` (str), `price` (float), `colors` (list[str]), `brand` (str | None), `platform` (str).

---

### Tool 2: `suggest_outfit`

**Purpose:** Calls the Groq LLM (llama-3.3-70b-versatile) to generate 1–2 outfit combinations pairing the new thrifted item with specific pieces from the user's wardrobe. Falls back to general styling advice when the wardrobe is empty.

**Inputs:**

| Parameter | Type | Description |
|-----------|------|-------------|
| `new_item` | `dict` | A full listing dict as returned by `search_listings`. Must include `title` (str), `category` (str), `style_tags` (list[str]), and `colors` (list[str]). |
| `wardrobe` | `dict` | A wardrobe dict with an `"items"` key containing a list of wardrobe item dicts. Pass `get_empty_wardrobe()` if the user has no wardrobe. |

**Output:** `str` — a non-empty string of outfit suggestions. When the wardrobe has items, each suggestion references specific wardrobe pieces by name. When the wardrobe is empty, the response gives general styling advice for the item's category and style tags. Never returns an empty string or raises an exception.

---

### Tool 3: `create_fit_card`

**Purpose:** Calls the Groq LLM at a higher temperature to produce a casual, voice-y Instagram/TikTok-style caption built around the thrifted find and the outfit from Tool 2.

**Inputs:**

| Parameter | Type | Description |
|-----------|------|-------------|
| `outfit` | `str` | The outfit suggestion string returned by `suggest_outfit`. Used as context for which pieces appear in the look. |
| `new_item` | `dict` | The listing dict for the thrifted find. The caption incorporates `title` (str), `price` (float), and `platform` (str) from this dict. |

**Output:** `str` — a 2–4 sentence caption that mentions the item name, platform, and price naturally. If `outfit` is an empty string, returns a descriptive error string built from `new_item` fields instead of crashing.

---

## Interaction Walkthrough

**User query:** `"looking for a vintage graphic tee under $30"`

**Step 1 — Tool called: `search_listings`**
- Input: `description="vintage graphic tee"`, `size=None`, `max_price=30.0`
- Why this tool: The agent needs real listings to work with before suggesting anything. The query contains keywords and a price ceiling but no size, so `size=None` is passed to search without that constraint.
- Output: A list of matching listings, top result is **lst_006 — "Graphic Tee — 2003 Tour Bootleg Style"** ($24.00, size L, condition good, on Depop, style tags: `graphic tee`, `vintage`, `grunge`, `streetwear`). The agent stores this as `session["selected_item"]`.

**Step 2 — Tool called: `suggest_outfit`**
- Input: `new_item=lst_006`, `wardrobe=get_example_wardrobe()`
- Why this tool: The agent now has a specific item and can ask the LLM to pair it with things the user already owns. The example wardrobe includes baggy straight-leg jeans, chunky white sneakers, and a vintage black denim jacket — all compatible with the graphic tee.
- Output: *"Pair the Graphic Tee — 2003 Tour Bootleg Style with your Straight-Leg Dark Wash Jeans and Chunky White Sneakers for a clean 90s streetwear look. For a more layered outfit, add your Vintage Black Denim Jacket over the top and leave it open — it gives the look some structure without overdoing it."* The agent stores this as `session["outfit_suggestion"]`.

**Step 3 — Tool called: `create_fit_card`**
- Input: `outfit=<suggestion from Step 2>`, `new_item=lst_006`
- Why this tool: The agent has both a listing and a styled outfit. This is the final step — turning the outfit into something postable.
- Output: *"finally found the perfect thrifted tee — grabbed this Graphic Tee — 2003 Tour Bootleg Style off depop for $24.00 and it just works. dark baggies, chunky sneakers, vintage denim jacket on top — low effort, high impact streetwear that actually fits the vibe."* The agent stores this as `session["fit_card"]`.

**Final output to user:**
The user sees three things: the listing details (title, price, platform, condition), the outfit suggestion with named wardrobe pieces, and the ready-to-post fit card caption. If Step 1 had returned no results, the agent would have responded with a helpful no-match message and stopped — Steps 2 and 3 would not have run.

---

## Planning Loop

The planning loop runs inside `run_agent(query, wardrobe)` in `agent.py`. It progresses through fixed stages and stops early if a stage produces nothing usable:

1. **Initialize** the session dict with all fields set to `None` / `[]`.
2. **Parse** the natural language query with regex to extract `description`, `size`, and `max_price`.
3. **Call `search_listings`** with the parsed parameters. If the result is `[]`, write a specific no-match message to `session["error"]` and return immediately — do not call the remaining tools.
4. **Select** `results[0]` as `session["selected_item"]`.
5. **Call `suggest_outfit`** with the selected item and wardrobe. Wrap in try/except — even if the LLM call fails, set `outfit_suggestion` to a fallback string and continue.
6. **Call `create_fit_card`** with the outfit suggestion and selected item. Wrap in try/except — if it fails, `fit_card` stays `None` and the agent continues without it.
7. **Return** the full session dict. Callers check `session["error"]` first; if it's `None`, all output fields are populated.

The agent never passes empty or `None` data forward. Each step gates on the previous one succeeding.

---

## State Management

All inter-tool state lives in a single `session` dict initialized at the start of `run_agent()`:

```python
session = {
    "query": query,              # original user query string
    "parsed": {},                # extracted description, size, max_price
    "search_results": [],        # list returned by search_listings
    "selected_item": None,       # results[0], passed to suggest_outfit
    "wardrobe": wardrobe,        # user's wardrobe; never mutated
    "outfit_suggestion": None,   # string returned by suggest_outfit
    "fit_card": None,            # string returned by create_fit_card
    "error": None,               # set on early termination
}
```

The tools themselves are stateless — they take explicit arguments and return values without reading from the session. The planning loop extracts what it needs from prior results and passes it forward explicitly. This makes each tool independently testable and keeps the data flow visible: `search_results[0]` → `selected_item` → `suggest_outfit` → `outfit_suggestion` → `create_fit_card` → `fit_card`.

---

## Error Handling and Fail Points

| Tool | Failure mode | Agent response |
|------|-------------|----------------|
| `search_listings` | No listings match the query, size, or price constraints | Sets `session["error"]` to: *"No listings matched "[description]" [in size X] [under $Y]. Try broader keywords, omit the size filter, or raise your budget."* Returns the session immediately without calling `suggest_outfit` or `create_fit_card`. |
| `suggest_outfit` | Wardrobe is empty (`wardrobe["items"] == []`) | Builds the LLM prompt without wardrobe context and returns general styling advice — e.g. *"No wardrobe on file. This piece typically works with straight-leg or wide-leg denim and chunky sneakers or boots."* Session continues normally to `create_fit_card`. |
| `create_fit_card` | `outfit` is an empty or whitespace-only string | Returns a descriptive error string built from `new_item` fields: *"Fit card couldn't be generated — no outfit suggestion was available. The item was: [title]."* Never raises an exception. |

**Concrete examples from testing (Milestone 5):**

- `search_listings('designer ballgown', size='XXS', max_price=5)` → `[]`, no exception raised. The agent set `session["error"]` to `"No listings matched \"ballgown\" in size XXS under $5..."` and returned without calling the remaining tools.
- `suggest_outfit(item, get_empty_wardrobe())` → returned a non-empty general styling advice string. No crash, no empty string, session continued to `create_fit_card`.
- `create_fit_card('', item)` → returned `"Fit card couldn't be generated — no outfit suggestion was available. The item was: Graphic Tee — 2003 Tour Bootleg Style."` No exception raised.

---

## Spec Reflection

**One way planning.md helped during implementation:**

Writing out the full session dict schema in planning.md before touching `agent.py` made the implementation almost mechanical. Because I had already named every key (`selected_item`, `outfit_suggestion`, `fit_card`, `error`) and described exactly when each one gets set, I never had to pause mid-implementation to decide how state should flow. The Architecture diagram was especially useful for verifying that the no-results branch actually stopped before calling `suggest_outfit` — I could trace it on paper before running a single test.

**One divergence from your spec, and why:**

The spec described `max_price` as `float` and stated that listings with `price > max_price` are excluded. In the actual implementation, `max_price` was changed to `float | None` (with `None` meaning no price ceiling) to match how the query parser works — if the user doesn't mention a price, there's no reason to default to `$100` and silently exclude items above that threshold. Making it `None`-able was a small but meaningful change: it meant I could skip the price filter entirely rather than applying an arbitrary default that the user never asked for.

---

## AI Usage

**Instance 1 — Implementing `search_listings`**

I gave Claude the Tool 1 section of `planning.md` in full (input params with types, return value description, failure mode) plus the `load_listings()` signature from `utils/data_loader.py`. I asked it to implement a function that filtered by keyword match across `title`, `description`, and `style_tags`, with optional size and price filters, returning results sorted by keyword-hit count descending then price ascending.

Claude produced a working implementation on the first try. The keyword scoring loop and the sort key (`(-score, price)`) matched my spec exactly. What I changed: the spec said `size` was `str or None` but Claude typed it as `str | None` with Python 3.10+ union syntax — I kept that since it was more precise. I also adjusted the size matching from an exact equality check (`listing["size"] == size`) to a case-insensitive substring match (`size.lower() in listing["size"].lower()`) so that `"M"` would match `"S/M"` listings, which Claude missed on the first pass.

**Instance 2 — Implementing `run_agent`**

I gave Claude the Planning Loop section, State Management section, and Architecture diagram from `planning.md` together in one prompt, and asked it to implement `run_agent(query, wardrobe)` matching the documented step-by-step flow. I specified that it should stop at the no-results branch and never call `suggest_outfit` with empty input.

Claude generated the full function including the `_parse_query` helper. The session initialization, the early-return on empty results, and the final assembly all matched my spec. What I overrode: Claude initially wrapped every tool call in a bare `except Exception: pass`, which would silently swallow real bugs. I changed `suggest_outfit`'s fallback to set a specific message string (`"No specific outfit could be suggested."`) rather than just passing, and I removed the silent pass on `create_fit_card`'s failure to instead set `fit_card = None` explicitly — making the failure state visible in the returned session.
