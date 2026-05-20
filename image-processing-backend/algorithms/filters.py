import cv2
import numpy as np


def _clip_uint8(img):
    return np.clip(img, 0, 255).astype(np.uint8)


def _make_odd(x, minimum=3):
    x = int(round(x))
    if x < minimum:
        x = minimum
    if x % 2 == 0:
        x += 1
    return x


def grayscale_filter(img_bgr):
    gray = cv2.cvtColor(img_bgr, cv2.COLOR_BGR2GRAY)
    return cv2.cvtColor(gray, cv2.COLOR_GRAY2BGR)


def negative_filter(img_bgr):
    return 255 - img_bgr


def sepia_filter(img_bgr):
    img_rgb = cv2.cvtColor(img_bgr, cv2.COLOR_BGR2RGB).astype(np.float32)
    sepia_matrix = np.array([
        [0.393, 0.769, 0.189],
        [0.349, 0.686, 0.168],
        [0.272, 0.534, 0.131],
    ], dtype=np.float32)
    sepia_rgb = _clip_uint8(img_rgb @ sepia_matrix.T)
    return cv2.cvtColor(sepia_rgb, cv2.COLOR_RGB2BGR)


def warm_filter(img_bgr, warm_strength=1.0):
    img = img_bgr.astype(np.float32)
    warm_strength = float(np.clip(warm_strength, 0.0, 2.0))
    b, g, r = cv2.split(img)
    r = r * (1.0 + 0.18 * warm_strength)
    g = g * (1.0 + 0.04 * warm_strength)
    b = b * (1.0 - 0.12 * warm_strength)
    return _clip_uint8(cv2.merge([b, g, r]))


def cool_filter(img_bgr, cool_strength=1.0):
    img = img_bgr.astype(np.float32)
    cool_strength = float(np.clip(cool_strength, 0.0, 2.0))
    b, g, r = cv2.split(img)
    b = b * (1.0 + 0.18 * cool_strength)
    g = g * (1.0 + 0.03 * cool_strength)
    r = r * (1.0 - 0.12 * cool_strength)
    return _clip_uint8(cv2.merge([b, g, r]))


def sketch_filter(img_bgr, blur_ksize=25, sketch_strength=0.92):
    blur_ksize = _make_odd(blur_ksize, minimum=3)
    sketch_strength = float(np.clip(sketch_strength, 0.0, 2.0))

    gray = cv2.cvtColor(img_bgr, cv2.COLOR_BGR2GRAY)
    inv_gray = 255 - gray
    blurred = cv2.GaussianBlur(inv_gray, (blur_ksize, blur_ksize), 0)
    denominator = np.clip(255 - blurred, 1, 255)

    sketch = cv2.divide(gray, denominator, scale=256)
    sketch = _clip_uint8(sketch.astype(np.float32) * sketch_strength)
    return cv2.cvtColor(sketch, cv2.COLOR_GRAY2BGR)


def high_contrast_filter(img_bgr):
    return cv2.convertScaleAbs(img_bgr, alpha=1.35, beta=8)


_FILTER_ALIASES = {
    "grayscale": "grayscale",
    "gray": "grayscale",
    "negative": "negative",
    "invert": "negative",
    "vintage": "sepia",
    "sepia": "sepia",
    "retro": "sepia",
    "warm": "warm",
    "cool": "cool",
    "sketch": "sketch",
    "pencil": "sketch",
    "high-contrast": "high_contrast",
    "high_contrast": "high_contrast",
}


def apply_filter(img_bgr, filter_type):
    name = _FILTER_ALIASES.get((filter_type or "").lower().strip())
    if name == "grayscale":
        return grayscale_filter(img_bgr)
    if name == "negative":
        return negative_filter(img_bgr)
    if name == "sepia":
        return sepia_filter(img_bgr)
    if name == "warm":
        return warm_filter(img_bgr)
    if name == "cool":
        return cool_filter(img_bgr)
    if name == "sketch":
        return sketch_filter(img_bgr)
    if name == "high_contrast":
        return high_contrast_filter(img_bgr)
    return img_bgr
