from fastapi import APIRouter
from pydantic import BaseModel
import base64

import cv2
import numpy as np

from algorithms.deskew import deskew
from algorithms.enhance_sharpen import enhance_sharpen
from algorithms.exposure import adjust_exposure

router = APIRouter(prefix="/api")


class ImageRequest(BaseModel):
    image: str
    angle: float = 0.0
    auto: bool = True
    brightness: float = 0.0
    intensity: float = 0.0
    sharpenMode: str = "unsharp"
    filterType: str = "none"


def base64_to_cv2(b64_str: str):
    if "," in b64_str:
        b64_str = b64_str.split(",", 1)[1]
    img_data = base64.b64decode(b64_str)
    img_array = np.frombuffer(img_data, np.uint8)
    return cv2.imdecode(img_array, cv2.IMREAD_COLOR)


def cv2_to_base64(cv2_img):
    ok, buffer = cv2.imencode(".png", cv2_img)
    if not ok:
        raise ValueError("Failed to encode image")
    b64_str = base64.b64encode(buffer).decode("utf-8")
    return f"data:image/png;base64,{b64_str}"


@router.post("/deskew")
async def handle_deskew(data: ImageRequest):
    cv_img = base64_to_cv2(data.image)
    processed_cv_img = deskew(cv_img)
    return {"processedImage": cv2_to_base64(processed_cv_img)}


@router.post("/exposure")
async def handle_exposure(data: ImageRequest):
    cv_img = base64_to_cv2(data.image)
    processed_cv_img = adjust_exposure(cv_img, data.brightness)
    return {"processedImage": cv2_to_base64(processed_cv_img)}


@router.post("/sharpen")
async def handle_sharpen(data: ImageRequest):
    cv_img = base64_to_cv2(data.image)
    processed_cv_img = enhance_sharpen(
        cv_img,
        strength=data.intensity,
        mode=data.sharpenMode,
    )
    return {"processedImage": cv2_to_base64(processed_cv_img)}


@router.post("/filter")
async def handle_filter(data: ImageRequest):
    cv_img = base64_to_cv2(data.image)
    filter_type = data.filterType

    if filter_type == "grayscale":
        gray = cv2.cvtColor(cv_img, cv2.COLOR_BGR2GRAY)
        processed_cv_img = cv2.cvtColor(gray, cv2.COLOR_GRAY2BGR)
    elif filter_type == "vintage":
        kernel = np.array(
            [
                [0.272, 0.534, 0.131],
                [0.349, 0.686, 0.168],
                [0.393, 0.769, 0.189],
            ]
        )
        processed_cv_img = cv2.transform(cv_img, kernel)
        processed_cv_img = np.clip(processed_cv_img, 0, 255).astype(np.uint8)
    elif filter_type == "high-contrast":
        processed_cv_img = cv2.convertScaleAbs(cv_img, alpha=1.35, beta=8)
    else:
        processed_cv_img = cv_img

    return {"processedImage": cv2_to_base64(processed_cv_img)}
