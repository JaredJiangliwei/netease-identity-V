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


def sepia_filter(img_bgr, strength=1.0):
    strength = float(np.clip(strength, 0.0, 1.5))
    img_rgb = cv2.cvtColor(img_bgr, cv2.COLOR_BGR2RGB).astype(np.float32)
    sepia_matrix = np.array([
        [0.393, 0.769, 0.189],
        [0.349, 0.686, 0.168],
        [0.272, 0.534, 0.131],
    ], dtype=np.float32)
    sepia_rgb = img_rgb @ sepia_matrix.T
    blended = img_rgb * (1.0 - strength) + sepia_rgb * strength
    return cv2.cvtColor(_clip_uint8(blended), cv2.COLOR_RGB2BGR)


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


def high_contrast_filter(img_bgr, alpha=1.35, beta=8):
    alpha = float(np.clip(alpha, 0.1, 3.0))
    beta = int(np.clip(beta, -100, 100))
    return cv2.convertScaleAbs(img_bgr, alpha=alpha, beta=beta)


_EMBOSS_KERNELS = {
    "NW": np.array([[-2, -1, 0], [-1, 1, 1], [0, 1, 2]], dtype=np.float32),
    "N":  np.array([[-1, -1, -1], [0, 1, 0], [1, 1, 1]], dtype=np.float32),
    "NE": np.array([[0, -1, -2], [1, 1, -1], [2, 1, 0]], dtype=np.float32),
    "E":  np.array([[-1, 0, 1], [-1, 1, 1], [-1, 0, 1]], dtype=np.float32),
    "SE": np.array([[2, 1, 0], [1, 1, -1], [0, -1, -2]], dtype=np.float32),
    "S":  np.array([[1, 1, 1], [0, 1, 0], [-1, -1, -1]], dtype=np.float32),
    "SW": np.array([[0, 1, 2], [-1, 1, 1], [-2, -1, 0]], dtype=np.float32),
    "W":  np.array([[1, 0, -1], [1, 1, -1], [1, 0, -1]], dtype=np.float32),
}


def emboss_filter(img_bgr, direction="NW", strength=1.0, mono=True):
    kernel = _EMBOSS_KERNELS.get(str(direction).upper(), _EMBOSS_KERNELS["NW"])
    strength = float(np.clip(strength, 0.1, 3.0))
    kernel = kernel * strength
    src = cv2.cvtColor(img_bgr, cv2.COLOR_BGR2GRAY) if mono else img_bgr
    out = cv2.filter2D(src.astype(np.float32), -1, kernel) + 128.0
    out = _clip_uint8(out)
    if mono:
        out = cv2.cvtColor(out, cv2.COLOR_GRAY2BGR)
    return out


def mosaic_filter(img_bgr, block=12):
    block = max(2, int(block))
    h, w = img_bgr.shape[:2]
    small = cv2.resize(img_bgr, (max(1, w // block), max(1, h // block)),
                       interpolation=cv2.INTER_AREA)
    return cv2.resize(small, (w, h), interpolation=cv2.INTER_NEAREST)


def vignette_filter(img_bgr, sigma_scale=0.5, darkness=0.85,
                    center_x=0.5, center_y=0.5):
    h, w = img_bgr.shape[:2]
    sigma_scale = float(np.clip(sigma_scale, 0.05, 2.0))
    darkness = float(np.clip(darkness, 0.0, 1.0))
    cx = float(np.clip(center_x, 0.0, 1.0)) * w
    cy = float(np.clip(center_y, 0.0, 1.0)) * h
    sigma = min(w, h) * sigma_scale
    yy, xx = np.mgrid[0:h, 0:w].astype(np.float32)
    mask = np.exp(-((xx - cx) ** 2 + (yy - cy) ** 2) / (2.0 * sigma ** 2))
    mask = mask / mask.max()
    mask = 1.0 - darkness * (1.0 - mask)
    return _clip_uint8(img_bgr.astype(np.float32) * mask[..., None])


def motion_blur_filter(img_bgr, ksize=21, angle=0.0):
    ksize = _make_odd(ksize, minimum=3)
    angle = float(angle)
    kernel = np.zeros((ksize, ksize), dtype=np.float32)
    kernel[ksize // 2, :] = 1.0
    M = cv2.getRotationMatrix2D((ksize / 2, ksize / 2), angle, 1.0)
    kernel = cv2.warpAffine(kernel, M, (ksize, ksize))
    s = kernel.sum()
    if s > 0:
        kernel /= s
    return cv2.filter2D(img_bgr, -1, kernel)


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
    "emboss": "emboss",
    "mosaic": "mosaic",
    "pixelate": "mosaic",
    "vignette": "vignette",
    "motion-blur": "motion_blur",
    "motion_blur": "motion_blur",
}


def _coerce(params, key, cast, default):
    if not params or key not in params or params[key] is None:
        return default
    try:
        return cast(params[key])
    except (TypeError, ValueError):
        return default


def apply_filter(img_bgr, filter_type, params=None):
    name = _FILTER_ALIASES.get((filter_type or "").lower().strip())
    params = params or {}

    if name == "grayscale":
        return grayscale_filter(img_bgr)
    if name == "negative":
        return negative_filter(img_bgr)
    if name == "sepia":
        return sepia_filter(
            img_bgr,
            strength=_coerce(params, "strength", float, 1.0),
        )
    if name == "warm":
        return warm_filter(
            img_bgr,
            warm_strength=_coerce(params, "warmStrength", float, 1.0),
        )
    if name == "cool":
        return cool_filter(
            img_bgr,
            cool_strength=_coerce(params, "coolStrength", float, 1.0),
        )
    if name == "sketch":
        return sketch_filter(
            img_bgr,
            blur_ksize=_coerce(params, "blurKsize", int, 25),
            sketch_strength=_coerce(params, "sketchStrength", float, 0.92),
        )
    if name == "high_contrast":
        return high_contrast_filter(
            img_bgr,
            alpha=_coerce(params, "alpha", float, 1.35),
            beta=_coerce(params, "beta", int, 8),
        )
    if name == "emboss":
        return emboss_filter(
            img_bgr,
            direction=_coerce(params, "direction", str, "NW"),
            strength=_coerce(params, "strength", float, 1.0),
            mono=bool(params.get("mono", True)) if params else True,
        )
    if name == "mosaic":
        return mosaic_filter(
            img_bgr,
            block=_coerce(params, "block", int, 12),
        )
    if name == "vignette":
        return vignette_filter(
            img_bgr,
            sigma_scale=_coerce(params, "sigmaScale", float, 0.5),
            darkness=_coerce(params, "darkness", float, 0.85),
            center_x=_coerce(params, "centerX", float, 0.5),
            center_y=_coerce(params, "centerY", float, 0.5),
        )
    if name == "motion_blur":
        return motion_blur_filter(
            img_bgr,
            ksize=_coerce(params, "ksize", int, 21),
            angle=_coerce(params, "angle", float, 0.0),
        )
    return img_bgr
