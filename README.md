# FreshSense

Three-class vegetable freshness classification with a Vision Transformer,
Grad-CAM visual explanations, and an agentic advisor that turns the grade into
a decision a shopkeeper can act on.

The model answers *how spoiled does this look*. The advisor answers *so what do
I do with it*.

| Stage | Output |
|---|---|
| ViT classifier | `Fresh` / `Mildly_Spoiled` / `Spoiled` + confidence |
| Grad-CAM | Heatmap and overlay showing which regions drove the grade |
| Shopkeeper advisor | An action, a selling window and a sell-by date |

## The decision layer

The grade alone is not actionable. The same grade means opposite things
depending on the produce:

| Grade | Carrot, potato, bell pepper (dense) | Tomato, cucumber (high moisture) |
|---|---|---|
| Fresh | Sell normally | Sell normally |
| Mildly_Spoiled | **Trim 1 inch clear, sell at a discount** | **Discard whole — do not trim** |
| Spoiled | Discard | Discard |

Mould travels easily through watery flesh and poorly through dense flesh, so
trimming a bell pepper is standard practice while doing the same to a tomato is
not. Getting that branch wrong is the failure this layer exists to prevent.

Every shelf-life figure and handling rule is cited in
[`backend/agent/knowledge.py`](backend/agent/knowledge.py) — USDA Agriculture
Handbook 66 storage data via UMaine Extension Bulletin #4135, and USDA-derived
extension guidance on mould in produce. Retail selling windows are labelled as
operational estimates, not published figures, everywhere they surface.

## Architecture

The advisor runs as an LLM agent over a deterministic rules engine, not as a
free-text prompt:

```
      ViT grade  ──►  LLM agent  ──►  advice
                          │  ▲
                   tools  │  │  grounded results
                          ▼  │
                   rules engine (decide.py)
                   knowledge base (knowledge.py)
```

The agent has four tools: `lookup_shelf_life`, `lookup_safety_rule`,
`compute_selling_window` and `submit_recommendation`. It is not trusted with
arithmetic or recall — on submission, `action`, `sell_within_days`,
`sell_by_date`, `cautions` and `references` are taken from the rules engine and
only the wording comes from the model. The agent can explain a decision; it
cannot overturn one, and it cannot state a number that no tool returned.

Details in [`backend/agent/README.md`](backend/agent/README.md).

### Running without an API key

The rules engine is the same code path the agent's tools call, so the app is
fully functional with no credentials configured: it returns the same decisions
and the same numbers, in plainer wording. The UI labels which of the two
produced the advice, and the follow-up question box appears only when the agent
is available.

Set a key to enable the agent, the Grad-CAM-aware "where to look" note, and
free-form follow-up questions:

```bash
cd backend
cp .env.example .env     # then add ANTHROPIC_API_KEY=sk-ant-...
python verify_agent.py   # checks the agent end to end, including the safety invariant
```

## Setup

```bash
# Backend
cd backend
python -m venv ../.venv
../.venv/Scripts/pip install -r requirements.txt
../.venv/Scripts/python -m uvicorn app:app --port 8000

# Frontend
cd frontend
npm install
npm run dev              # http://localhost:5173
```

The trained checkpoint (`backend/checkpoints/standard_vit_finetuned_best.pth`,
328 MB) is excluded from version control — it exceeds GitHub's file size limit.
Obtain it separately and place it in that directory.

## API

| Endpoint | Purpose |
|---|---|
| `POST /predict` | Grade an uploaded image, return probabilities + Grad-CAM |
| `POST /advise` | Turn a grade into an action and a selling window |
| `POST /advise/followup` | Answer a question about advice already given (requires a key) |
| `GET /health` | Model status and which advisor backend is active |
| `GET /vegetables` | Options the advisor understands |

`/advise` is separate from `/predict` so the shopkeeper can correct the
vegetable or the storage condition and get fresh advice without re-running the
model on CPU.

## Deployment

The frontend and the backend cannot be deployed to the same place, and the
reason is worth stating plainly rather than discovering at build time.

**Frontend — Vercel.** Live at **https://freshsense-self.vercel.app**.

`frontend/` is the Vercel root directory. Vite is auto-detected, so there is no
build configuration to maintain. The project is deployed from the CLI
(`vercel deploy --prod` from `frontend/`) rather than from a Git connection, so
**a push to this repository does not redeploy the site** — run the command, or
run `vercel git connect` once the Vercel GitHub App has access to this
repository.

Set one environment variable on the project:

| Variable | Value |
|---|---|
| `VITE_API_BASE_URL` | `https://<your-backend-host>` |

Vite inlines `VITE_*` variables at build time, so changing it requires a
redeploy, not just a restart.

**Backend — not Vercel.** A Vercel serverless function is capped at 250 MB
unzipped. The CPU build of `torch` alone is roughly 200 MB, and the fine-tuned
checkpoint is a further 328 MB, which puts this backend over the limit several
times over before any other dependency is counted. There is no configuration
that fits it; it needs a host that runs a persistent container with disk:

- Render, Railway or Fly.io — a container with the checkpoint baked in or
  mounted
- Hugging Face Spaces — suits the model-plus-API shape well
- Any VM running `uvicorn app:app` behind HTTPS

Until that is set, the live site loads and every analysis fails with a
connection error. That is expected: there is no backend behind it yet.

The deployed page is served over HTTPS, so the API it calls must be HTTPS too:
a browser blocks an HTTPS page from calling `http://127.0.0.1:8000` as mixed
content. **A Vercel-hosted frontend cannot talk to a backend running on your
own machine** — the UI will load and every request will fail. For local work,
run both locally.

Once the backend is hosted, tell it which origin may call it:

```bash
ALLOWED_ORIGINS=https://<your-project>.vercel.app
```

`http://localhost:5173` and `http://127.0.0.1:5173` stay allowed either way, so
local development keeps working unchanged.

## Limitations

- Selling windows are estimates for typical shop conditions, not a food-safety
  certification.
- The model grades appearance only. It does not detect greening or sprouting in
  potatoes, which is why that check is surfaced to the shopkeeper separately.
- Confidence is the model's own probability, not a measure of correctness.
  Gradings below 65% confidence, or where the top two classes are within 15
  points, are downgraded to a manual check rather than acted on.
