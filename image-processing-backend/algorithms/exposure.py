import cv2
import numpy as np


# =====================================
# Gamma 校正
# =====================================
def gamma_correction(
    image: np.ndarray,
    gamma: float = 1.0
) -> np.ndarray:

    if gamma <= 0:
        raise ValueError(
            "gamma must be > 0"
        )

    inv_gamma = 1.0 / gamma

    table = np.array([
        ((i / 255.0) ** inv_gamma) * 255
        for i in np.arange(256)
    ]).astype("uint8")

    return cv2.LUT(image, table)


# =====================================
# 线性亮度/对比度调整
# =====================================
def linear_adjust(
    image: np.ndarray,
    alpha: float = 1.0,
    beta: float = 0
) -> np.ndarray:

    if alpha <= 0:
        raise ValueError(
            "alpha must be > 0"
        )

    return cv2.convertScaleAbs(
        image,
        alpha=alpha,
        beta=beta
    )


# =====================================
# 主曝光校正函数
# =====================================
def adjust_exposure(
    image: np.ndarray,
    gamma: float = 1.0,
    alpha: float = 1.0,
    beta: float = 0
) -> np.ndarray:

    gamma_img = gamma_correction(
        image,
        gamma
    )

    final_img = linear_adjust(
        gamma_img,
        alpha,
        beta
    )

    return final_img
