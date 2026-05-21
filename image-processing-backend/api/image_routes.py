from fastapi import APIRouter, HTTPException
from fastapi.concurrency import run_in_threadpool
from pydantic import BaseModel
from typing import Optional
import base64

import cv2
import numpy as np

from algorithms.deskew import deskew
from algorithms.rotate import rotate_image_without_borders
from algorithms.enhance_sharpen import enhance_sharpen
from algorithms.exposure import adjust_exposure
from algorithms.filters import apply_filter
from algorithms.ai_style import apply_ai_style, list_styles
from algorithms.auto_rotate import auto_smart_deskew

router = APIRouter(prefix="/api")


class ImageRequest(BaseModel):
    image: str
    angle: float = 0.0
    auto: bool = True
    
    gamma: float = 1.0
    alpha: float = 1.0
    beta: float = 0.0
    
    intensity: float = 0.0
    sharpenMode: str = "unsharp"
    filterType: str = "none"
    aiStyle: str = "none"
    aiStrength: Optional[float] = None
    aiSeed: int = 42


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
    processed_cv_img = adjust_exposure(
        cv_img,
        gamma=data.gamma,
        alpha=data.alpha,
        beta=data.beta
    )
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
    processed_cv_img = apply_filter(cv_img, data.filterType)
    return {"processedImage": cv2_to_base64(processed_cv_img)}


@router.get("/ai-style/list")
async def handle_list_ai_styles():
    return {"styles": list_styles()}


@router.post("/ai-style")
async def handle_ai_style(data: ImageRequest):
    if data.aiStyle in ("", "none"):
        return {"processedImage": data.image}

    cv_img = base64_to_cv2(data.image)
    try:
        processed_cv_img = await run_in_threadpool(
            apply_ai_style,
            cv_img,
            data.aiStyle,
            data.aiStrength,
            data.aiSeed,
        )
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except RuntimeError as e:
        raise HTTPException(status_code=503, detail=str(e))
    return {"processedImage": cv2_to_base64(processed_cv_img)}
