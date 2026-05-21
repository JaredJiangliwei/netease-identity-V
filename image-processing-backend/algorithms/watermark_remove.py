import cv2
import numpy as np


def remove_watermark_by_mask(
    image: np.ndarray,
    mask: np.ndarray,
    radius: int = 3,
    method: str = "telea"
) -> np.ndarray:

    if image is None:
        raise ValueError("Input image is None.")

    if mask is None:
        raise ValueError("Mask is None.")

    if mask.ndim == 3:
        mask = cv2.cvtColor(mask, cv2.COLOR_BGR2GRAY)

    mask = np.where(mask > 0, 255, 0).astype(np.uint8)
    radius = max(1, int(radius))

    if method == "telea":
        flag = cv2.INPAINT_TELEA
    elif method == "ns":
        flag = cv2.INPAINT_NS
    else:
        raise ValueError("method must be 'telea' or 'ns'.")

    return cv2.inpaint(image, mask, radius, flag)


def generate_smart_watermark_mask(
    image: np.ndarray,
    x: int,
    y: int,
    w: int,
    h: int,
    watermark_type: str = "white",
    white_threshold: int = 180,
    black_threshold: int = 80,
    dilate_iter: int = 1
) -> np.ndarray:
    """
    生成智能水印 mask。

    watermark_type:
    - "white": 白色/浅色水印
    - "black": 黑色/深色水印
    """

    if image is None:
        raise ValueError("Input image is None.")

    H, W = image.shape[:2]

    x = max(0, int(x))
    y = max(0, int(y))
    w = max(1, int(w))
    h = max(1, int(h))

    x2 = min(W, x + w)
    y2 = min(H, y + h)

    roi = image[y:y2, x:x2]

    if roi.size == 0:
        raise ValueError("Selected ROI is empty.")

    if image.ndim == 2:
        gray = roi
    else:
        gray = cv2.cvtColor(roi, cv2.COLOR_BGR2GRAY)

    watermark_type = watermark_type.lower()

    if watermark_type == "white":
        _, local_mask = cv2.threshold(
            gray,
            white_threshold,
            255,
            cv2.THRESH_BINARY
        )

    elif watermark_type == "black":
        _, local_mask = cv2.threshold(
            gray,
            black_threshold,
            255,
            cv2.THRESH_BINARY_INV
        )

    else:
        raise ValueError("watermark_type must be 'white' or 'black'.")

    kernel = np.ones((3, 3), np.uint8)

    local_mask = cv2.morphologyEx(
        local_mask,
        cv2.MORPH_CLOSE,
        kernel,
        iterations=1
    )

    local_mask = cv2.dilate(
        local_mask,
        kernel,
        iterations=max(0, int(dilate_iter))
    )

    mask = np.zeros((H, W), dtype=np.uint8)
    mask[y:y2, x:x2] = local_mask

    return mask


def remove_watermark_by_smart_rect(
    image: np.ndarray,
    x: int,
    y: int,
    w: int,
    h: int,
    watermark_type: str = "white",
    radius: int = 3,
    method: str = "telea",
    white_threshold: int = 180,
    black_threshold: int = 80,
    dilate_iter: int = 1
) -> np.ndarray:
    """
    智能矩形去水印。
    用户框选大致水印区域，算法根据水印颜色生成 mask。
    """

    mask = generate_smart_watermark_mask(
        image=image,
        x=x,
        y=y,
        w=w,
        h=h,
        watermark_type=watermark_type,
        white_threshold=white_threshold,
        black_threshold=black_threshold,
        dilate_iter=dilate_iter
    )

    return remove_watermark_by_mask(
        image=image,
        mask=mask,
        radius=radius,
        method=method
    )