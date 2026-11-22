---
title: FreshSense API
emoji: 🥕
colorFrom: green
colorTo: yellow
sdk: docker
app_port: 7860
pinned: false
short_description: Vegetable freshness grading with ViT, Grad-CAM and an advisor
---

# FreshSense API

FastAPI backend for [FreshSense](https://freshsense-self.vercel.app): grades a
vegetable photo as `Fresh`, `Mildly_Spoiled` or `Spoiled` with a fine-tuned
Vision Transformer, explains the grade with Grad-CAM, and turns it into a
shopkeeper decision.

> The YAML block above configures this as a Hugging Face **Docker Space**. Keep
> `app_port` and the `EXPOSE`/`CMD` port in the `Dockerfile` in step.

## Endpoints

| Endpoint | Purpose |
|---|---|
| `POST /predict` | Grade an uploaded image, return probabilities + Grad-CAM |
| `POST /advise` | Turn a grade into an action and a selling window |
| `POST /advise/followup` | Answer a question about advice already given (needs a key) |
| `GET /health` | Model status and which advisor backend is active |
| `GET /vegetables` | Options the advisor understands |

## Configuration

| Variable | Required | Purpose |
|---|---|---|
| `HF_MODEL_REPO` | In a container | Model repo holding the checkpoint, e.g. `user/freshsense-vit` |
| `HF_MODEL_FILENAME` | No | Defaults to `standard_vit_finetuned_best.pth` |
| `HF_TOKEN` | Only if the model repo is private | Read token for the download |
| `ALLOWED_ORIGINS` | For a deployed frontend | Comma-separated origins allowed to call this API |
| `ANTHROPIC_API_KEY` | No | Enables the agent; without it the rules engine answers |

`http://localhost:5173` and `http://127.0.0.1:5173` are always allowed, so
local development needs no CORS configuration.

## The checkpoint

The trained weights are 343 MB — too large for git and deliberately not baked
into the image. `model.py` resolves them in this order:

1. `backend/checkpoints/standard_vit_finetuned_best.pth` if it exists locally
2. otherwise `HF_MODEL_REPO`, downloaded via `huggingface_hub` and cached

A local file always wins, so development behaves exactly as before. In a
container there is no local copy, so the first boot downloads the checkpoint
and later boots read it from the `HF_HOME` cache.

## Running the container locally

```bash
docker build -t freshsense-api .
docker run --rm -p 7860:7860 \
  -e HF_MODEL_REPO=your-username/freshsense-vit \
  freshsense-api
```

Then `curl http://localhost:7860/health`.

## Notes on cost and cold starts

Inference is CPU-only. A free Space sleeps after 48 hours idle and takes
roughly 30 seconds to wake; the first request after a cold start also pays for
the checkpoint download if the cache was cleared. Grad-CAM on CPU is the slow
part of `/predict`, which is why `/advise` is a separate endpoint — changing
the vegetable or storage condition re-asks the advisor without re-running the
model.

## Source

[github.com/Nandana889/FreshSense](https://github.com/Nandana889/FreshSense) —
see `backend/agent/README.md` for how the advisor stays grounded.
