import cv2
import numpy as np


def _clip_uint8(img: np.ndarray) -> np.ndarray:
    """
    将浮点图像裁剪到 [0,255] 并转成 uint8
    """
    return np.clip(img, 0, 255).astype(np.uint8)


def _process_luminance(image: np.ndarray, process_func):
    """
    彩色图像只处理亮度通道，避免直接锐化 RGB 导致颜色失真。
    输入/输出均为 OpenCV 格式：
    - 灰度图: H x W
    - 彩色图: H x W x 3, BGR
    """
    if image.ndim == 2:
        gray = image.astype(np.float32)
        result = process_func(gray)
        return _clip_uint8(result)

    if image.ndim == 3 and image.shape[2] == 3:
        ycrcb = cv2.cvtColor(image, cv2.COLOR_BGR2YCrCb)
        y, cr, cb = cv2.split(ycrcb)

        y_f = y.astype(np.float32)
        y_result = process_func(y_f)
        y_result = _clip_uint8(y_result)

        merged = cv2.merge([y_result, cr, cb])
        return cv2.cvtColor(merged, cv2.COLOR_YCrCb2BGR)

    raise ValueError("Input image must be grayscale or BGR color image.")


def unsharp_sharpen(image: np.ndarray, strength: float = 1.0) -> np.ndarray:
    """
    Unsharp Masking / Highboost Sharpening

    原理：
    1. blur = GaussianBlur(image)
    2. mask = image - blur
    3. result = image + strength * mask

    strength:
    - 0   : 不锐化
    - 1.0 : 普通 unsharp masking
    - >1  : highboost filtering
    """

    strength = max(0.0, float(strength))

    if strength == 0:
        return image.copy()

    def process(channel: np.ndarray) -> np.ndarray:
        blur = cv2.GaussianBlur(channel, (0, 0), sigmaX=1.2)
        mask = channel - blur
        result = channel + strength * mask
        return result

    return _process_luminance(image, process)


def laplacian_sharpen(image: np.ndarray, strength: float = 0.5) -> np.ndarray:
    """
    Laplacian 二阶微分锐化

    result = image - strength * Laplacian(image)

    使用二阶导数突出灰度突变区域，适合强调边缘和细节。
    """

    strength = max(0.0, float(strength))

    if strength == 0:
        return image.copy()

    def process(channel: np.ndarray) -> np.ndarray:
        lap = cv2.Laplacian(channel, cv2.CV_32F, ksize=3)
        result = channel - strength * lap
        return result

    return _process_luminance(image, process)


def sobel_detail_enhance(image: np.ndarray, strength: float = 0.4) -> np.ndarray:
    """
    Sobel 一阶梯度细节增强

    先计算 x/y 方向梯度，再把梯度幅值按一定比例加回原亮度通道。
    """

    strength = max(0.0, float(strength))

    if strength == 0:
        return image.copy()

    def process(channel: np.ndarray) -> np.ndarray:
        gx = cv2.Sobel(channel, cv2.CV_32F, 1, 0, ksize=3)
        gy = cv2.Sobel(channel, cv2.CV_32F, 0, 1, ksize=3)

        grad = cv2.magnitude(gx, gy)
        grad = cv2.normalize(grad, None, 0, 255, cv2.NORM_MINMAX)

        result = channel + strength * grad
        return result

    return _process_luminance(image, process)


def enhance_sharpen(
    image: np.ndarray,
    strength: float = 50,
    mode: str = "unsharp"
) -> np.ndarray:
    """
    给前端调用的统一接口。

    参数：
    image    : OpenCV 图像矩阵，BGR 或灰度
    strength : 前端滑杆值，建议范围 0~100
    mode     :
        - "unsharp"   : 推荐默认，效果自然
        - "laplacian" : 边缘更明显，但噪声也可能增强
        - "sobel"     : 强调边缘轮廓

    返回：
    OpenCV 图像矩阵，uint8
    """

    if image is None:
        raise ValueError("Input image is None.")

    strength = float(strength)
    strength = np.clip(strength, 0, 100)

    if mode == "unsharp":
        # 0~100 映射到 0~2.0
        k = strength / 50.0
        return unsharp_sharpen(image, k)

    elif mode == "laplacian":
        # Laplacian 不宜太强，0~100 映射到 0~1.0
        k = strength / 100.0
        return laplacian_sharpen(image, k)

    elif mode == "sobel":
        # Sobel 梯度增强也不宜过强
        k = strength / 150.0
        return sobel_detail_enhance(image, k)

    else:
        raise ValueError("mode must be 'unsharp', 'laplacian', or 'sobel'.")