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
Loads all listings from `data/listings.json` via `load_listings()`, then filters them against the query. Keyword matching checks whether any word from `description` appears (case-insensitive) in the listing's `title`, `description`, or `style_tags`. Results are also filtered by `size` and `max_price`.

**Input parameters:**
- `description` (str): one or more space-separated keywords to match against a listing's title, description field, and style_tags list. Example: `"vintage graphic tee"`.
- `size` (str or None): exact string to match against the listing's `size` field (e.g. `"M"`, `"W30 L30"`). Pass `None` to skip size filtering entirely.
- `max_price` (float): maximum acceptable price. Listings with `price > max_price` are excluded. Example: `30.0`.

**What it returns:**
A list of listing dicts, each containing all fields from the dataset: `id` (str), `title` (str), `description` (str), `category` (str), `style_tags` (list[str]), `size` (str), `condition` (str — one of `excellent`, `good`, `fair`), `price` (float), `colors` (list[str]), `brand` (str or None), `platform` (str — one of `depop`, `thredUp`, `poshmark`). The list is sorted by relevance (count of matched keywords) descending, then by price ascending. Returns an empty list `[]` if nothing matches.

**What happens if it fails or returns nothing:**
If the returned list is empty, the agent immediately responds to the user: *"No listings matched '[description]' in size [size] under $[max_price]. Try using broader keywords (e.g. 'tee' instead of 'graphic tee'), omitting the size filter, or raising your budget."* The agent sets `session["error"] = "no_listings"` and returns without calling `suggest_outfit` or `create_fit_card`.

---

### Tool 2: suggest_outfit

**What it does:**
Given a new thrifted item and the user's current wardrobe, calls the Claude API to generate 1–2 complete outfit combinations that pair the new item with specific pieces already owned. If the wardrobe is empty it still returns styling advice — just generic rather than wardrobe-specific.

**Input parameters:**
- `new_item` (dict): a full listing dict as returned by `search_listings`. Must include at minimum `title` (str), `category` (str), `style_tags` (list[str]), and `colors` (list[str]).
- `wardrobe` (dict): a wardrobe dict with an `"items"` key containing a list of wardrobe item dicts. Each item has `id` (str), `name` (str), `category` (str), `colors` (list[str]), `style_tags` (list[str]), and optional `notes` (str or None). Pass `get_empty_wardrobe()` if the user has no wardrobe.

**What it returns:**
A plain string containing 1–2 outfit suggestions. When the wardrobe has items, each suggestion references specific pieces by name (e.g. *"your dark baggy jeans"*, *"your chunky white sneakers"*) and includes a one-sentence style rationale. Example: *"Pair this tee with your dark baggy jeans and chunky white sneakers — clean 90s streetwear. For a more layered look, add your vintage black denim jacket and leave it open."*

**What happens if it fails or returns nothing:**
If `wardrobe["items"]` is empty, the tool builds a prompt without wardrobe context and returns generic styling advice based solely on the new item's `category`, `style_tags`, and `colors` — e.g. *"No wardrobe on file. This piece typically works with straight-leg or wide-leg denim and chunky sneakers or boots."* The session continues normally to `create_fit_card` with this generic suggestion; the tool never returns an empty string or raises an exception.

---

### Tool 3: create_fit_card

**What it does:**
Generates a short (1–2 sentence), casual, social-media-style caption describing the complete outfit centered on the thrifted find. The output should read like something a real person would post — voice-y and specific, not a template — and it must vary meaningfully across different inputs.

**Input parameters:**
- `outfit` (str): the outfit suggestion string returned by `suggest_outfit`. Used to extract which specific wardrobe pieces appear in the look.
- `new_item` (dict): the listing dict for the thrifted find. The caption must incorporate at minimum `platform` (str), `price` (float), and enough of `title`/`style_tags` to make the caption feel specific to this item rather than generic.

**What it returns:**
A plain string of 1–2 sentences suitable for an Instagram caption. The string always names the platform and price (e.g. *"off depop for $24"*) and weaves in 1–2 key outfit pieces. Example: *"grabbed this faded bootleg tee off depop for $24 and it literally goes with everything — dark baggies, chunky sneakers, denim jacket on top 🖤"*

**What happens if it fails or returns nothing:**
If `outfit` is an empty string, the tool builds the caption from `new_item` alone (title, price, platform, style_tags) and notes the outfit details weren't available. If `new_item` is missing `price` or `platform`, those fields are omitted from the caption rather than crashing — the tool substitutes `"thrifted"` for platform and omits the price. If both `outfit` and `new_item` are unusable, the agent skips `create_fit_card` entirely and tells the user: *"Fit card couldn't be generated — not enough outfit information was available."*

---

### Additional Tools (if any)

<!-- Copy the block above for any tools beyond the required three -->

---

## Planning Loop

**How does your agent decide which tool to call next?**

The loop runs inside a single function `run_agent(user_input, wardrobe)` and progresses through fixed stages, stopping early if a stage fails. Here is the exact conditional logic:

1. **Parse user input.** Extract `description` (str), `size` (str or None), and `max_price` (float, default `100.0`) from `user_input`. Store them in local variables.

2. **Call `search_listings(description, size, max_price)`.**
   - If `results == []`: set `session["error"] = "no_listings"`, return the message *"No listings matched '[description]' in size [size] under $[max_price]. Try broader keywords or raise your budget."* **Stop — do not call subsequent tools.**
   - If `len(results) > 0`: set `session["selected_item"] = results[0]` and continue.

3. **Call `suggest_outfit(new_item=session["selected_item"], wardrobe=wardrobe)`.**
   - If return value is a non-empty string: set `session["outfit_suggestion"] = result` and continue.
   - If return value is empty or an exception is raised: set `session["outfit_suggestion"] = "No specific outfit could be suggested."`, log the error, and continue to step 4 anyway (the fit card can still be generated from the item alone).

4. **Call `create_fit_card(outfit=session["outfit_suggestion"], new_item=session["selected_item"])`.**
   - If return value is a non-empty string: set `session["fit_card"] = result` and continue.
   - If return value is empty: set `session["fit_card"] = None` and skip including it in the final response.

5. **Assemble and return the final response.** Combine: (a) the selected listing's title, price, platform, and condition; (b) the outfit suggestion; (c) the fit card if it exists. The loop knows it is done when it reaches this step without an early return.

---

## State Management

**How does information from one tool get passed to the next?**

The planning loop maintains a single `session` dict for the duration of one interaction. It is initialized at the start of `run_agent()` and updated after each tool call:

```python
session = {
    "wardrobe": wardrobe,         # passed in at start; never mutated
    "selected_item": None,        # set to results[0] after search_listings succeeds
    "outfit_suggestion": None,    # set to the string returned by suggest_outfit
    "fit_card": None,             # set to the string returned by create_fit_card
    "error": None                 # set to an error key if the loop terminates early
}
```

Tools themselves do not read from the session — the planning loop extracts the values it needs and passes them as explicit arguments. This keeps tools stateless and independently testable. The loop reads back from the session only to decide what to do next (e.g. checking `session["selected_item"] is not None` before calling `suggest_outfit`). At the end of the interaction the full session dict is returned so callers can inspect intermediate state for debugging.

---

## Error Handling

For each tool, describe the specific failure mode you're handling and what the agent does in response.

| Tool | Failure mode | Agent response |
|------|-------------|----------------|
| search_listings | No results match the query | Respond: *"No listings matched '[description]' in size [size] under $[max_price]. Try broader keywords (e.g. 'tee' instead of 'vintage graphic tee'), omit the size filter, or raise your budget."* Set `session["error"] = "no_listings"` and stop — do not call the remaining tools. |
| suggest_outfit | Wardrobe is empty (`wardrobe["items"] == []`) | Return generic styling advice based on the item's category, style_tags, and colors instead of referencing specific owned pieces. Continue to `create_fit_card` — the session does not terminate early. |
| create_fit_card | `outfit` is an empty string | Build the caption from `new_item` fields alone (title, price, platform). If `new_item` is also missing critical fields, skip the fit card and tell the user: *"Fit card couldn't be generated — not enough outfit information was available."* |

---

## Architecture

```
User query ("vintage graphic tee under $30, size M")
    │
    ▼
┌──────────────────────────── Planning Loop (run_agent) ────────────────────────────┐
│                                                                                   │
│  Parse input → description="vintage graphic tee", size="M", max_price=30.0       │
│      │                                                                            │
│      ▼                                                                            │
│  search_listings(description, size, max_price)                                    │
│      │                          │                                                 │
│      │ results == []            │ results = [lst_006, ...]                        │
│      ▼                          ▼                                                 │
│  session["error"]         session["selected_item"] = results[0]                  │
│  = "no_listings"               │                                                 │
│      │                          ▼                                                 │
│      ▼                    suggest_outfit(selected_item, wardrobe)                 │
│  "No listings found.           │                         │                        │
│   Try broader terms."    wardrobe empty            wardrobe has items             │
│      │                         │                         │                        │
│      ▼                         ▼                         ▼                        │
│    STOP ◄──────── session["outfit_suggestion"] = generic OR specific string       │
│                                │                                                 │
│                                ▼                                                 │
│                   create_fit_card(outfit_suggestion, selected_item)               │
│                                │                         │                        │
│                          outfit empty              outfit present                 │
│                                │                         │                        │
│                                ▼                         ▼                        │
│                    caption from item only    session["fit_card"] = caption string │
│                                │                         │                        │
│                                └──────────┬──────────────┘                       │
│                                           ▼                                      │
│                              Assemble final response:                             │
│                                · Listing: title, price, platform, condition      │
│                                · Outfit suggestion                               │
│                                · Fit card (if available)                         │
│                                           │                                      │
└───────────────────────────────────────────┼──────────────────────────────────────┘
                                            │
                                            ▼
                                   Return to user
```

**Session state** (shared across all steps, never passed into tools directly):
```
session = {
    "wardrobe": {...},          ← initialized at start
    "selected_item": None,      ← set after search_listings
    "outfit_suggestion": None,  ← set after suggest_outfit
    "fit_card": None,           ← set after create_fit_card
    "error": None               ← set on early termination
}
```

---

## AI Tool Plan

**Milestone 3 — Individual tool implementations:**

- **`search_listings`:** Give Claude the Tool 1 block from this file (input params, return value, failure mode) plus the `load_listings()` signature from `utils/data_loader.py`. Ask it to implement a function that filters by keyword match across `title`, `description`, and `style_tags` (case-insensitive), exact `size` match (skipped if `None`), and `price <= max_price`, returning results sorted by keyword-hit count descending then price ascending. Verify by running 3 test cases before trusting: (1) `"vintage tee"` with no size filter — expect 2+ results; (2) `"silk dress"` — expect empty list; (3) `"jacket"` with `size="S"` — expect only size-S jackets.

- **`suggest_outfit`:** Give Claude the Tool 2 block plus the `wardrobe_schema.json` example wardrobe. Ask it to build a prompt that lists the new item's `title`, `category`, `style_tags`, and `colors`, then lists each wardrobe item's `name`, `category`, and `style_tags`, and sends that to the Claude API requesting 1–2 outfit combinations. Verify that: (1) with the example wardrobe, the response references specific piece names; (2) with `get_empty_wardrobe()`, the response gives generic advice without crashing.

- **`create_fit_card`:** Give Claude the Tool 3 block. Ask it to build a prompt from `new_item["title"]`, `new_item["price"]`, `new_item["platform"]`, and the `outfit` string, requesting a 1–2 sentence casual caption. Verify that: (1) two different outfits produce meaningfully different captions; (2) the platform name and price appear in the output; (3) passing `outfit=""` produces a caption from the item fields rather than crashing.

**Milestone 4 — Planning loop and state management:**

Give Claude the Planning Loop section, the State Management section, and the Architecture diagram from this file. Ask it to implement `run_agent(user_input, wardrobe)` that: parses `user_input` for `description`, `size`, and `max_price`; calls tools in the documented sequence; stores results in the `session` dict as shown; returns early with the documented error message if `search_listings` returns `[]`; and returns the assembled final response string on success. Verify by running the complete interaction trace from "A Complete Interaction" below — check that (1) a no-match search stops before calling `suggest_outfit`, (2) `session["selected_item"]` from step 1 is what flows into step 2, and (3) the final response includes all three pieces (listing summary, outfit, fit card).

---

## A Complete Interaction (Step by Step)

FitFindr takes a natural language request and orchestrates up to three tools in sequence: it first searches secondhand listings by keyword, size, and budget (`search_listings`), then uses the top result alongside the user's wardrobe to suggest a complete outfit (`suggest_outfit`), and finally generates a shareable caption-style fit card (`create_fit_card`). Each tool is called only when the previous one succeeds — if `search_listings` returns nothing, the agent reports back and stops rather than passing empty data to the next tool. When any tool fails or returns an incomplete result, the agent communicates what went wrong and either asks the user to refine their search or falls back to a generic suggestion (e.g., styling tips when the wardrobe is empty).

**Example user query:** "I'm looking for a vintage graphic tee under $30. I mostly wear baggy jeans and chunky sneakers. What's out there and how would I style it?"

**Step 1:**
The agent calls `search_listings("vintage graphic tee", size=None, max_price=30.0)` — size is not specified in the query so it searches without a size filter. The dataset returns a match: **lst_006, "Graphic Tee — 2003 Tour Bootleg Style"** — $24, size L, condition good, on Depop. Style tags include `graphic tee`, `vintage`, `grunge`, `streetwear`, `band tee`. The agent selects this as the top result and stores it in session state.

**Step 2:**
With lst_006 stored as `new_item`, the agent calls `suggest_outfit(new_item=lst_006, wardrobe=example_wardrobe)`. The example wardrobe contains baggy straight-leg dark-wash jeans (w_001), chunky white sneakers (w_007), and a vintage black denim jacket (w_006) — all compatible with the boxy graphic tee. The tool returns: *"Pair this faded bootleg tee with your dark baggy jeans and chunky white sneakers for a clean 90s streetwear look. Throw the vintage black denim jacket over the top for structure — leave it open."*

**Step 3:**
The agent calls `create_fit_card(outfit=<suggestion from Step 2>, new_item=lst_006)`. It generates: *"grabbed this faded bootleg tee off depop for $24 and it literally goes with everything — dark baggies, chunky sneakers, denim jacket on top 🖤 thrift win of the week"*

**Final output to user:**
The user sees three things in one response: the listing found (title, price, platform, condition), the outfit suggestion with specific pieces from their wardrobe, and the ready-to-post fit card caption. If Step 1 had returned no results, the agent would have told the user to try broader keywords or raise the price limit — and Steps 2 and 3 would not have run.
