import torch
import timm
import os

# Device configuration
DEVICE = torch.device(
    "cuda" if torch.cuda.is_available() else "cpu"
)

# Checkpoint location
CHECKPOINT_PATH = os.path.join(
    os.path.dirname(__file__),
    "checkpoints",
    "standard_vit_finetuned_best.pth"
)

# The checkpoint is 343 MB, so it is not in version control and not baked into
# the container image. In a deployed container there is no local copy, and it
# is pulled from a Hugging Face model repository instead:
#
#   HF_MODEL_REPO=your-username/freshsense-vit
#
# A local file always wins, so development is unaffected by these settings.
HF_MODEL_REPO = os.environ.get("HF_MODEL_REPO", "").strip()

HF_MODEL_FILENAME = os.environ.get(
    "HF_MODEL_FILENAME",
    "standard_vit_finetuned_best.pth"
).strip()


def resolve_checkpoint():
    """Return a local path to the checkpoint, downloading it if necessary."""
    if os.path.exists(CHECKPOINT_PATH):
        return CHECKPOINT_PATH

    if not HF_MODEL_REPO:
        raise FileNotFoundError(
            f"Checkpoint not found: {CHECKPOINT_PATH}. "
            "Place the file there, or set HF_MODEL_REPO to a Hugging Face "
            "model repository holding it."
        )

    try:
        from huggingface_hub import hf_hub_download
    except ImportError as exc:
        raise RuntimeError(
            "HF_MODEL_REPO is set but `huggingface_hub` is not installed. "
            "Run: pip install huggingface_hub"
        ) from exc

    print(f"Downloading checkpoint from {HF_MODEL_REPO} ...")

    # Cached under HF_HOME, so this is a first-boot cost, not a per-request
    # one. A private repository needs HF_TOKEN in the environment.
    path = hf_hub_download(
        repo_id=HF_MODEL_REPO,
        filename=HF_MODEL_FILENAME,
        token=os.environ.get("HF_TOKEN") or None
    )

    print("Checkpoint downloaded.")

    return path


# Class names
CLASS_NAMES = [
    "Fresh",
    "Mildly_Spoiled",
    "Spoiled"
]

# Load trained Standard ViT
def load_model():

    checkpoint_path = resolve_checkpoint()

    model = timm.create_model(
        "vit_base_patch16_224",
        pretrained=False,
        num_classes=3
    )

    checkpoint = torch.load(
        checkpoint_path,
        map_location=DEVICE,
        weights_only=False
    )

    model.load_state_dict(
        checkpoint["model_state_dict"]
    )

    model.to(DEVICE)
    model.eval()

    print("Standard ViT loaded successfully!")
    print("Classes:", CLASS_NAMES)
    print("Device:", DEVICE)
    print("Checkpoint epoch:", checkpoint["epoch"])

    return model


if __name__ == "__main__":
    model = load_model()