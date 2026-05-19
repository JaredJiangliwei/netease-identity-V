from fastapi import APIRouter
from pydantic import BaseModel
import cv2
import numpy as np
import base64

# 🚀 关键：跨文件导入队友写的算法函数
from algorithms.deskew import deskew 
from algorithms.exposure import adjust_exposure  # 假设队友写了

router = APIRouter(prefix="/api")

# 定义前端传参的格式
class ImageRequest(BaseModel):
    image: str      # 前端传来的 base64
    angle: float = 0.0
    brightness: float = 0.0

# --- 辅助工具函数：Base64 与 OpenCV 图片互转 ---
def base64_to_cv2(b64_str):
    if "," in b64_str:
        b64_str = b64_str.split(",")[1] # 切掉前端的 "data:image/png;base64," 前缀
    img_data = base64.b64decode(b64_str)
    img_array = np.frombuffer(img_data, np.uint8)
    return cv2.imdecode(img_array, cv2.IMREAD_COLOR)

def cv2_to_base64(cv2_img):
    _, buffer = cv2.imencode('.png', cv2.img)
    b64_str = base64.b64encode(buffer).decode('utf-8')
    return f"data:image/png;base64,{b64_str}" # 补上给前端直接显示的头


# --- 真正的 API 接口 ---

@router.post("/deskew")
async def handle_deskew(data: ImageRequest):
    # 1. 转换图片
    cv_img = base64_to_cv2(data.image)
    
    # 2. 🚀 调用导入的单独 .py 中的算法函数
    processed_cv_img = deskew(cv_img)
    
    # 3. 转回 base64 返回给前端
    result_b64 = cv2_to_base64(processed_cv_img)
    return {"processedImage": result_b64}

@router.post("/exposure")
async def handle_exposure(data: ImageRequest):
    cv_img = base64_to_cv2(data.image)
    
    # 🚀 调用另一个文件的算法函数
    processed_cv_img = adjust_exposure(cv_img, data.brightness)
    
    result_b64 = cv2_to_base64(processed_cv_img)
    return {"processedImage": result_b64}