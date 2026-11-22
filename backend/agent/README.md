# Agentic shopkeeper advisor

Turns the classifier's freshness grade into an action a shopkeeper can take:
how long to keep selling the item, whether to trim it, or whether to throw it
away.

The classifier answers *how spoiled does this look*. This layer answers *so
what do I do with it*.

## Why it needs an agent

The decision is not a lookup. The same grade means opposite things depending on
the vegetable:

| Grade | Carrot, potato, bell pepper (dense) | Tomato, cucumber (high moisture) |
|---|---|---|
| Fresh | Sell normally | Sell normally |
| Mildly_Spoiled | **Trim 1 inch clear, sell at a discount** | **Discard whole — do not trim** |
| Spoiled | Discard | Discard |

Mould travels easily through watery flesh and poorly through dense flesh, so
cutting the bad part off a tomato and selling the rest is unsafe while doing the
same to a bell pepper is standard practice. Getting that branch wrong is the
failure this layer exists to prevent.

The classifier does not identify the vegetable, only the grade. When no
vegetable has been selected the advisor still answers, using deliberately
conservative generic figures (see `GENERIC_RETAIL_WINDOWS` in `knowledge.py`)
so there is always an action on screen straight after Grad-CAM, and it keeps
asking for the vegetable so the answer can be sharpened. The generic window is
the shortest in the table, so naming the vegetable can only ever extend a
window, never shorten one. A `Spoiled` grade needs no vegetable at all: it is a
discard whatever the produce. A `Mildly_Spoiled` grade of unknown type falls
back to the published shallow-versus-deep damage test rather than guessing at
the dense-versus-watery one.

## How the numbers stay honest

The agent is not trusted with arithmetic or recall. It has four tools:

| Tool | Returns |
|---|---|
| `lookup_shelf_life` | Cited storage figures plus the shop selling window |
| `lookup_safety_rule` | The mould-handling rule for this vegetable |
| `compute_selling_window` | The decision, the days remaining and the sell-by date |
| `submit_recommendation` | How the agent hands back its wording |

On submission, `action`, `sell_within_days`, `sell_by_date` and `references` are
taken from `compute_selling_window`; only the wording comes from the model. So a
bad generation can phrase advice poorly but **cannot** invent a shelf life or
overturn a discard. If the agent never calls `compute_selling_window`, the
response falls back to the rules engine entirely.

`verify_agent.py` asserts this invariant against the live API.

## Files

| File | Role |
|---|---|
| `knowledge.py` | The grounded tables, with provenance for every figure |
| `decide.py` | Deterministic engine: all arithmetic and safety branching |
| `advisor.py` | The LLM agent, vision input, and follow-up questions |
| `env.py` | Dependency-free `.env` loader |
| `__init__.py` | `get_advice()` / `ask_followup()` entry points and fallback logic |

## Running without an API key

`get_advice()` falls back to `decide.assess()` when no credentials are
configured, when the `anthropic` package is missing, or when the API call fails
for any reason. The app stays fully usable; the advice is just blunter and the
UI shows a grey "Rule-based" badge instead of "AI agent".

Follow-up questions are the exception — there is no rule-based way to answer an
open question, so `/advise/followup` returns **503** and the frontend hides the
question box.

## Configuration

Put the key in `backend/.env`:

```
ANTHROPIC_API_KEY=sk-ant-...
```

A real environment variable overrides the file. Then:

```bash
cd backend
python verify_agent.py                     # confirm it works, ~6 API calls
python verify_agent.py --image some.jpg    # also check the vision path
```

`GET /health` reports `advisor.agent_available` so you can see which backend is
live without reading logs.

## Endpoints

| Endpoint | Purpose |
|---|---|
| `POST /advise` | Grade in, decision out. Optional base64 image pair enables `where_to_look`. |
| `POST /advise/followup` | A question about advice already given. Needs a key. |
| `GET /vegetables` | Selector options, so the frontend cannot drift from the backend. |

`/advise` is deliberately separate from `/predict`: changing the vegetable or
the storage condition re-asks the advisor without re-running the ViT, which on
CPU is the slow part.

## Known limitation: the selling windows

`RETAIL_WINDOWS` in `knowledge.py` holds **operational estimates, not published
figures.** The published data available (USDA Handbook 66 via UMaine Extension)
assumes a cold chain — carrots at 0 °C and 98–100% RH for 7–9 months — which a
produce shop does not have, so those numbers would mislead a shopkeeper badly.

The cited figures are kept and shown as provenance; the shop windows next to
them are conservative working defaults, labelled as estimates everywhere they
surface. **Calibrate them against real stock records before any commercial
use.** They are in one dict for exactly that reason.

The safety rules (the trim-vs-discard branch) *are* grounded in published
guidance, and matter more than the day counts.

## Sources

- [UMaine Extension Bulletin #4135](https://extension.umaine.edu/publications/4135e/) — storage conditions, reproducing USDA Agriculture Handbook 66
- [UConn Extension, "Handling Food with Mold"](https://extension.uconn.edu/publication/handling-food-with-mold/)
- [NC State Extension, "Moldy Foods: Use or Pitch"](https://brunswick.ces.ncsu.edu/news/moldy-foods-use-or-pitch/)
