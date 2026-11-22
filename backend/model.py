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

# Class names
CLASS_NAMES = [
    "Fresh",
    "Mildly_Spoiled",
    "Spoiled"
]

# Load trained Standard ViT
def load_model():

    if not os.path.exists(CHECKPOINT_PATH):
        raise FileNotFoundError(
            f"Checkpoint not found: {CHECKPOINT_PATH}"
        )

    model = timm.create_model(
        "vit_base_patch16_224",
        pretrained=False,
        num_classes=3
    )

    checkpoint = torch.load(
        CHECKPOINT_PATH,
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