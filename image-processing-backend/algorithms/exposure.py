import cv2
import numpy as np


def adjust_exposure(image: np.ndarray, brightness: float) -> np.ndarray:
    beta = max(-100.0, min(float(brightness), 100.0))
    return cv2.convertScaleAbs(image, alpha=1.0, beta=beta)
