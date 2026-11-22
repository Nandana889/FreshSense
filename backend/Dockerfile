# Container image for the FreshSense API, targeting Hugging Face Spaces.
#
# The 328 MB checkpoint is deliberately NOT baked into this image. It lives in
# a separate Hugging Face model repository and is fetched on first boot; see
# HF_MODEL_REPO in model.py. That keeps the image small and the weights out of
# version control.
#
# Build context is this directory, not the repository root.

FROM python:3.13-slim

# OpenCV's wheels link against these system libraries but do not bundle them.
# Without them, `import cv2` fails with a libGL.so.1 error at startup.
RUN apt-get update && apt-get install -y --no-install-recommends \
        libgl1 \
        libglib2.0-0 \
    && rm -rf /var/lib/apt/lists/*

# Spaces runs containers as uid 1000. Creating the user ourselves keeps file
# ownership and the pip cache consistent whether or not that applies.
RUN useradd --create-home --uid 1000 user
USER user

ENV HOME=/home/user \
    PATH=/home/user/.local/bin:$PATH \
    PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    HF_HOME=/home/user/.cache/huggingface

WORKDIR $HOME/app

COPY --chown=user requirements.txt ./

# torch is pinned to the CPU build (+cpu), which is published on PyTorch's own
# index rather than PyPI.
RUN pip install --no-cache-dir --upgrade pip \
    && pip install --no-cache-dir -r requirements.txt \
        --extra-index-url https://download.pytorch.org/whl/cpu

COPY --chown=user . ./

# Spaces routes external traffic to 7860; app_port in README.md must match.
EXPOSE 7860

CMD ["uvicorn", "app:app", "--host", "0.0.0.0", "--port", "7860"]
