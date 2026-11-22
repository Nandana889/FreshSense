import numpy as np
from PIL import Image

from pytorch_grad_cam import GradCAM
from pytorch_grad_cam.utils.model_targets import ClassifierOutputTarget
from pytorch_grad_cam.utils.image import show_cam_on_image


def reshape_transform(tensor):
    result = tensor[:, 1:, :]
    result = result.reshape(
        tensor.size(0), 14, 14, 768
    )
    return result.permute(0, 3, 1, 2)


def generate_gradcam(model, input_tensor, predicted_class):

    target_layers = [model.blocks[-1].norm1]

    with GradCAM(
        model=model,
        target_layers=target_layers,
        reshape_transform=reshape_transform
    ) as cam:

        grayscale_cam = cam(
            input_tensor=input_tensor,
            targets=[
                ClassifierOutputTarget(predicted_class)
            ]
        )[0]

    return grayscale_cam