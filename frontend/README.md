# FreshSense — frontend

React + Vite single-page app for the FreshSense vegetable freshness grader. It
uploads one produce photo, shows the Vision Transformer's grade, the Grad-CAM
explanation, and the shopkeeper advice that follows from them.

## Running it

```bash
npm install
npm run dev              # http://localhost:5173
```

The dev server is pinned to `localhost:5173` with `strictPort: true` in
[`vite.config.js`](vite.config.js). That is deliberate: the backend's CORS
policy allows exactly that origin, so a silent move to port 5174 would fail in
a confusing way. If the port is taken, free it rather than changing it.

The backend must be running separately — see the [root README](../README.md).

## Configuration

| Variable | Default | Purpose |
|---|---|---|
| `VITE_API_BASE_URL` | `http://127.0.0.1:8000` | Where the FastAPI backend lives |

Set it in `frontend/.env` or inline:

```bash
VITE_API_BASE_URL=http://127.0.0.1:8001 npm run dev
```

Vite only exposes variables prefixed `VITE_`, and inlines them at **build**
time — changing it means rebuilding, not just restarting.

## How the screen is built

`App.jsx` owns all the state and renders the sections in the order a shopkeeper
reads them:

| Component | Shows |
|---|---|
| `Navbar`, `Hero` | Header; `PatchGrid` draws the decorative 14×14 patch graphic |
| `ImageUpload` | Drag-and-drop or file picker, with client-side validation |
| `PredictionResults` | The grade, the confidence, and all three class scores |
| `GradCAMResults` | Original / heatmap / overlay, and what the highlighting means |
| `ShopkeeperAdvice` | The action, the selling window, cautions, sources, follow-up box |
| `HowItWorks`, `About`, `Footer` | Explanation of the pipeline and its limits |
| `ApiStatus` | Whether the backend is up, and which advisor backend is live |

### `services/api.js`

One module wraps every call, so no component touches `fetch` directly. Each
endpoint gets its own timeout, because the costs are wildly different — 120 s
for `/predict` (Grad-CAM on CPU), 90 s for `/advise` (an agent loop), 5 s for
`/health`. Errors are converted to messages that are safe to put on screen, and
`AbortError` is re-thrown untouched so a cancelled upload is not reported as a
failure.

`/predict` responses are checked for all six required fields before being
accepted, so a partial response surfaces as an error instead of a half-drawn
result.

### `utils/`

- `validateImage.js` — rejects non-JPG/PNG/WEBP, empty files and anything over
  10 MB **before** upload, and returns the message to display rather than
  throwing.
- `freshnessClasses.js` — pairs every class with both a colour and its own
  icon, so a result never depends on colour alone.

## Notes

- No router. The app is one page with anchor navigation, which is why there is
  no SPA rewrite rule in the deployment config.
- `lucide-react` supplies the icons; there is no UI framework or CSS library.
  Styling is plain CSS in `App.css` and `index.css`.
- The vegetable selector is populated from `GET /vegetables` so the frontend
  cannot drift out of step with what the advisor actually understands.

## Deploying

Live at **https://freshsense-self.vercel.app**.

This directory is the Vercel root directory for the project; Vite is
auto-detected (`npm run build` → `dist/`). Deploys are run from here with
`vercel deploy --prod`, not triggered by Git pushes. Set `VITE_API_BASE_URL` to a
publicly reachable HTTPS backend URL before the deployed page will work — see
**Deployment** in the [root README](../README.md) for why the backend cannot go
on Vercel alongside it.
