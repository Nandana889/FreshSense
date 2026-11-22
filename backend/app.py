
import io
import os
import base64

from typing import Any, Dict, Optional

import torch
import numpy as np

from PIL import Image
from fastapi import FastAPI, File, UploadFile, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field
from pytorch_grad_cam.utils.image import show_cam_on_image

from model import load_model, DEVICE, CLASS_NAMES
from preprocessing import eval_transform
from gradcam import generate_gradcam

from agent import (
    AssessmentError,
    KNOWN_VEGETABLES,
    STORAGE_CONDITIONS,
    advisor_status,
    ask_followup,
    get_advice,
)
from agent.advisor import AgentUnavailable


# Initialize FastAPI
app = FastAPI(
    title="FreshSense API",
    description="Standard ViT classification with Grad-CAM explanations",
    version="1.0"
)

# Origins allowed to call this API.
#
# The Vite dev server is always allowed, because that is where the setup
# instructions serve the page from. A deployed frontend lives on a different
# origin, so add it via ALLOWED_ORIGINS (comma-separated) rather than editing
# this file:
#
#   ALLOWED_ORIGINS=https://freshsense.vercel.app
#
# Browsers reject a wildcard origin when credentials are allowed, so the list
# is explicit by design.
DEV_ORIGINS = [
    "http://localhost:5173",
    "http://127.0.0.1:5173"
]

ALLOWED_ORIGINS = DEV_ORIGINS + [
    origin.strip()
    for origin in os.environ.get("ALLOWED_ORIGINS", "").split(",")
    if origin.strip()
]

# Allow React frontend communication
app.add_middleware(
    CORSMiddleware,
    allow_origins=ALLOWED_ORIGINS,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"]
)


# Load trained model only once
model = load_model()


def image_to_base64(image_array):
    image = Image.fromarray(
        image_array.astype(np.uint8)
    )

    buffer = io.BytesIO()
    image.save(buffer, format="PNG")

    return base64.b64encode(
        buffer.getvalue()
    ).decode("utf-8")


@app.get("/")
def home():
    return {
        "message": "FreshSense API is running",
        "classes": CLASS_NAMES
    }


@app.get("/health")
def health():
    return {
        "status": "healthy",
        "model": "Standard ViT",
        "device": str(DEVICE),
        "advisor": advisor_status()
    }


@app.get("/vegetables")
def vegetables():
    """Options the advisor understands, for the frontend's selectors."""
    return {
        "vegetables": list(KNOWN_VEGETABLES),
        "storage_conditions": list(STORAGE_CONDITIONS)
    }


class AdviceRequest(BaseModel):
    """A classified item the shopkeeper wants a decision about."""

    freshness_class: str = Field(
        ...,
        description="Fresh, Mildly_Spoiled or Spoiled."
    )
    confidence: float = Field(
        ...,
        ge=0,
        le=100,
        description="Classifier confidence as a percentage."
    )
    class_probabilities: Optional[Dict[str, float]] = Field(
        default=None,
        description="All class scores, used to spot borderline gradings."
    )
    vegetable: Optional[str] = Field(
        default=None,
        description="Which vegetable this is; the advisor asks if omitted."
    )
    storage: str = Field(
        default="ambient",
        description="'ambient' for an open shelf, 'refrigerated' for a chiller."
    )
    use_agent: bool = Field(
        default=True,
        description="Set false to force the deterministic rules engine."
    )
    original_image: Optional[str] = Field(
        default=None,
        description=(
            "Base64 PNG from /predict. Supplied with gradcam_overlay, the "
            "agent can say which part of the item to inspect."
        )
    )
    gradcam_overlay: Optional[str] = Field(
        default=None,
        description="Base64 Grad-CAM overlay from /predict."
    )


@app.post("/advise")
def advise(request: AdviceRequest):
    """
    Turn a classification into a decision the shopkeeper can act on.

    Kept separate from /predict so the shopkeeper can change the vegetable or
    the storage condition and get fresh advice without re-running the model.
    """
    try:
        return get_advice(
            freshness_class=request.freshness_class,
            confidence=request.confidence,
            class_probabilities=request.class_probabilities,
            vegetable=request.vegetable,
            storage=request.storage,
            images={
                "original_image": request.original_image,
                "gradcam_overlay": request.gradcam_overlay
            },
            use_agent=request.use_agent
        )

    except AssessmentError as e:
        raise HTTPException(status_code=400, detail=str(e))

    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


class FollowupTurn(BaseModel):
    """One earlier message in this question thread."""

    role: str = Field(..., pattern="^(user|assistant)$")
    content: str


class FollowupRequest(BaseModel):
    """A shopkeeper's question about advice they were already given."""

    question: str = Field(..., min_length=1, max_length=2000)
    freshness_class: str
    confidence: float = Field(..., ge=0, le=100)
    decision: Dict[str, Any] = Field(
        ...,
        description="The advice object previously returned by /advise."
    )
    class_probabilities: Optional[Dict[str, float]] = None
    vegetable: Optional[str] = None
    storage: str = "ambient"
    history: list[FollowupTurn] = Field(default_factory=list)


@app.post("/advise/followup")
def advise_followup(request: FollowupRequest):
    """
    Answer a question about advice already given.

    This one genuinely needs the language model -- there is no rule-based way
    to answer an open question -- so it returns 503 rather than a fake answer
    when no API key is configured.
    """
    try:
        return ask_followup(
            question=request.question,
            freshness_class=request.freshness_class,
            confidence=request.confidence,
            decision=request.decision,
            class_probabilities=request.class_probabilities,
            vegetable=request.vegetable,
            storage=request.storage,
            history=[turn.model_dump() for turn in request.history]
        )

    except AssessmentError as e:
        raise HTTPException(status_code=400, detail=str(e))

    except AgentUnavailable as e:
        raise HTTPException(status_code=503, detail=str(e))

    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/predict")
async def predict(file: UploadFile = File(...)):

    if file.content_type not in [
        "image/jpeg",
        "image/png",
        "image/jpg",
        "image/webp"
    ]:
        raise HTTPException(
            status_code=400,
            detail="Please upload a valid image."
        )

    try:
        contents = await file.read()

        if not contents:
            raise HTTPException(
                status_code=400,
                detail="Uploaded image is empty."
            )

        original_image = Image.open(
            io.BytesIO(contents)
        ).convert("RGB")

        # Resize and preprocess
        resized_image = original_image.resize((224, 224))

        rgb_image = np.asarray(
            resized_image,
            dtype=np.float32
        ) / 255.0

        input_tensor = eval_transform(
            original_image
        ).unsqueeze(0).to(DEVICE)

        # Model prediction
        model.eval()

        with torch.no_grad():
            outputs = model(input_tensor)
            probabilities = torch.softmax(
                outputs, dim=1
            )[0]

            predicted_class = int(
                torch.argmax(probabilities).item()
            )

        confidence = float(
            probabilities[predicted_class].item() * 100
        )

        # Generate Grad-CAM
        grayscale_cam = generate_gradcam(
            model,
            input_tensor,
            predicted_class
        )

        # Generate overlay
        overlay = show_cam_on_image(
            rgb_image,
            grayscale_cam,
            use_rgb=True
        )

        # Generate colored heatmap
        import cv2

        heatmap = cv2.applyColorMap(
            np.uint8(255 * grayscale_cam),
            cv2.COLORMAP_JET
        )

        heatmap = cv2.cvtColor(
            heatmap,
            cv2.COLOR_BGR2RGB
        )

        return {
            "predicted_class": CLASS_NAMES[predicted_class],
            "confidence": round(confidence, 2),
            "class_probabilities": {
                CLASS_NAMES[i]: round(
                    float(probabilities[i].item() * 100), 2
                )
                for i in range(len(CLASS_NAMES))
            },
            "original_image": image_to_base64(
                np.asarray(resized_image)
            ),
            "heatmap": image_to_base64(heatmap),
            "gradcam_overlay": image_to_base64(overlay)
        }

    except HTTPException:
        raise

    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=str(e)
        )
