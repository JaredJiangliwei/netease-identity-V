import cv2
import numpy as np

_rembg_session = None


def _remove_background_with_rembg(image: np.ndarray) -> np.ndarray | None:
    global _rembg_session

    try:
        from rembg import new_session, remove
    except ImportError:
        return None

    if _rembg_session is None:
        _rembg_session = new_session("u2net_human_seg")

    ok, buffer = cv2.imencode(".png", image)
    if not ok:
        return None

    output_bytes = remove(buffer.tobytes(), session=_rembg_session)
    output_array = np.frombuffer(output_bytes, np.uint8)
    result = cv2.imdecode(output_array, cv2.IMREAD_UNCHANGED)
    if result is None:
        return None
    if result.ndim == 3 and result.shape[2] == 4:
        return result
    if result.ndim == 3 and result.shape[2] == 3:
        alpha = np.full(result.shape[:2], 255, dtype=np.uint8)
        return cv2.merge([result[:, :, 0], result[:, :, 1], result[:, :, 2], alpha])
    return None


def _largest_foreground_component(mask: np.ndarray) -> np.ndarray:
    labels_count, labels, stats, _ = cv2.connectedComponentsWithStats(mask, connectivity=8)
    if labels_count <= 1:
        return mask

    largest_label = 1 + int(np.argmax(stats[1:, cv2.CC_STAT_AREA]))
    return np.where(labels == largest_label, 255, 0).astype(np.uint8)


def _grabcut_with_rectangle(image: np.ndarray) -> np.ndarray:
    h, w = image.shape[:2]
    margin_x = max(2, int(w * 0.06))
    margin_y = max(2, int(h * 0.06))
    rect = (
        margin_x,
        margin_y,
        max(1, w - 2 * margin_x),
        max(1, h - 2 * margin_y),
    )
    mask = np.zeros((h, w), dtype=np.uint8)
    bg_model = np.zeros((1, 65), np.float64)
    fg_model = np.zeros((1, 65), np.float64)
    cv2.grabCut(image, mask, rect, bg_model, fg_model, 5, cv2.GC_INIT_WITH_RECT)
    return np.where(
        (mask == cv2.GC_FGD) | (mask == cv2.GC_PR_FGD),
        255,
        0,
    ).astype(np.uint8)


def _detect_main_face(image: np.ndarray) -> tuple[int, int, int, int] | None:
    gray = cv2.cvtColor(image, cv2.COLOR_BGR2GRAY)
    gray = cv2.equalizeHist(gray)

    cascade_path = cv2.data.haarcascades + "haarcascade_frontalface_default.xml"
    face_cascade = cv2.CascadeClassifier(cascade_path)
    if face_cascade.empty():
        return None

    faces = face_cascade.detectMultiScale(
        gray,
        scaleFactor=1.08,
        minNeighbors=4,
        minSize=(max(24, image.shape[1] // 14), max(24, image.shape[0] // 14)),
    )
    if len(faces) == 0:
        return None

    h, w = image.shape[:2]
    center_x = w / 2.0
    center_y = h / 2.0

    def score(face):
        x, y, fw, fh = face
        area = fw * fh
        face_cx = x + fw / 2.0
        face_cy = y + fh / 2.0
        center_distance = abs(face_cx - center_x) / max(w, 1) + abs(face_cy - center_y) / max(h, 1)
        return area - center_distance * area * 0.35

    return tuple(int(v) for v in max(faces, key=score))


def _portrait_prior_mask(image: np.ndarray) -> np.ndarray:
    h, w = image.shape[:2]
    prior = np.zeros((h, w), dtype=np.uint8)
    face = _detect_main_face(image)
    if face is None:
        return prior

    x, y, fw, fh = face
    cx = x + fw / 2.0
    cy = y + fh / 2.0

    head_center = (int(round(cx)), int(round(y + fh * 0.48)))
    head_axes = (int(round(fw * 0.92)), int(round(fh * 1.18)))
    cv2.ellipse(prior, head_center, head_axes, 0, 0, 360, 180, -1)

    body_top = int(round(y + fh * 0.72))
    body_bottom = min(h - 1, int(round(y + fh * 4.2)))
    shoulder_half_top = int(round(fw * 0.95))
    shoulder_half_bottom = int(round(fw * 2.0))
    body = np.array(
        [
            [max(0, int(round(cx - shoulder_half_top))), max(0, body_top)],
            [min(w - 1, int(round(cx + shoulder_half_top))), max(0, body_top)],
            [min(w - 1, int(round(cx + shoulder_half_bottom))), body_bottom],
            [max(0, int(round(cx - shoulder_half_bottom))), body_bottom],
        ],
        dtype=np.int32,
    )
    cv2.fillConvexPoly(prior, body, 140)

    face_center = (int(round(cx)), int(round(cy)))
    face_axes = (int(round(fw * 0.42)), int(round(fh * 0.50)))
    cv2.ellipse(prior, face_center, face_axes, 0, 0, 360, 255, -1)
    return prior


def _border_connected_background(image: np.ndarray) -> tuple[np.ndarray, np.ndarray]:
    h, w = image.shape[:2]
    lab = cv2.cvtColor(image, cv2.COLOR_BGR2LAB)

    strip = max(3, int(round(min(h, w) * 0.045)))
    border_pixels = np.concatenate(
        [
            lab[:strip, :, :].reshape(-1, 3),
            lab[-strip:, :, :].reshape(-1, 3),
            lab[:, :strip, :].reshape(-1, 3),
            lab[:, -strip:, :].reshape(-1, 3),
        ],
        axis=0,
    ).astype(np.float32)

    sample_count = min(5000, len(border_pixels))
    if sample_count < len(border_pixels):
        indices = np.linspace(0, len(border_pixels) - 1, sample_count).astype(np.int32)
        samples = border_pixels[indices]
    else:
        samples = border_pixels

    criteria = (cv2.TERM_CRITERIA_EPS + cv2.TERM_CRITERIA_MAX_ITER, 20, 0.2)
    clusters = min(3, max(1, len(samples)))
    _, _, centers = cv2.kmeans(
        samples,
        clusters,
        None,
        criteria,
        3,
        cv2.KMEANS_PP_CENTERS,
    )

    lab_f = lab.astype(np.float32)
    distances = np.stack(
        [np.linalg.norm(lab_f - center.reshape(1, 1, 3), axis=2) for center in centers],
        axis=0,
    )
    distance = distances.min(axis=0)

    border_distance = np.concatenate(
        [
            distance[:strip, :].reshape(-1),
            distance[-strip:, :].reshape(-1),
            distance[:, :strip].reshape(-1),
            distance[:, -strip:].reshape(-1),
        ]
    )
    threshold = float(np.clip(np.percentile(border_distance, 92) + 10.0, 18.0, 55.0))
    background_like = (distance <= threshold).astype(np.uint8)

    labels_count, labels = cv2.connectedComponents(background_like, connectivity=8)
    keep_labels = set()
    keep_labels.update(np.unique(labels[0, :]).tolist())
    keep_labels.update(np.unique(labels[-1, :]).tolist())
    keep_labels.update(np.unique(labels[:, 0]).tolist())
    keep_labels.update(np.unique(labels[:, -1]).tolist())
    keep_labels.discard(0)

    connected = np.isin(labels, list(keep_labels)).astype(np.uint8)
    kernel_size = max(3, int(round(min(h, w) * 0.01)))
    if kernel_size % 2 == 0:
        kernel_size += 1
    kernel = cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (kernel_size, kernel_size))
    connected = cv2.morphologyEx(connected, cv2.MORPH_CLOSE, kernel, iterations=1)
    return background_like * 255, connected * 255


def remove_background(image: np.ndarray) -> np.ndarray:
    """
    One-click foreground cutout with a transparent background.

    The method uses an automatic GrabCut rectangle and mask refinement. It is
    designed for photos where the main subject is near the center of the image.
    """
    if image is None:
        raise ValueError("Input image is None.")

    if image.ndim != 3 or image.shape[2] != 3:
        raise ValueError("Input image must be a BGR color image.")

    model_result = _remove_background_with_rembg(image)
    if model_result is not None:
        return model_result

    h, w = image.shape[:2]
    if h < 8 or w < 8:
        alpha = np.full((h, w), 255, dtype=np.uint8)
        return cv2.cvtColor(image, cv2.COLOR_BGR2BGRA) if image.shape[2] == 3 else image

    scale = min(1.0, 900.0 / max(h, w))
    work = image
    if scale < 1.0:
        work = cv2.resize(
            image,
            (max(1, int(w * scale)), max(1, int(h * scale))),
            interpolation=cv2.INTER_AREA,
        )

    wh, ww = work.shape[:2]
    background_like, connected_background = _border_connected_background(work)
    portrait_prior = _portrait_prior_mask(work)
    margin_x = max(2, int(ww * 0.06))
    margin_y = max(2, int(wh * 0.06))
    rect = (
        margin_x,
        margin_y,
        max(1, ww - 2 * margin_x),
        max(1, wh - 2 * margin_y),
    )

    mask = np.full((wh, ww), cv2.GC_PR_FGD, dtype=np.uint8)
    mask[background_like > 0] = cv2.GC_PR_BGD
    mask[connected_background > 0] = cv2.GC_BGD
    mask[(portrait_prior >= 140) & (connected_background == 0)] = cv2.GC_PR_FGD
    mask[portrait_prior >= 230] = cv2.GC_FGD

    center_margin_x = max(2, int(ww * 0.18))
    center_margin_y = max(2, int(wh * 0.18))
    mask[
        center_margin_y : wh - center_margin_y,
        center_margin_x : ww - center_margin_x,
    ] = cv2.GC_PR_FGD

    border = max(1, min(ww, wh) // 32)
    mask[:border, :] = cv2.GC_BGD
    mask[-border:, :] = cv2.GC_BGD
    mask[:, :border] = cv2.GC_BGD
    mask[:, -border:] = cv2.GC_BGD

    bg_model = np.zeros((1, 65), np.float64)
    fg_model = np.zeros((1, 65), np.float64)

    try:
        cv2.grabCut(work, mask, rect, bg_model, fg_model, 5, cv2.GC_INIT_WITH_MASK)
    except cv2.error:
        cv2.grabCut(work, mask, rect, bg_model, fg_model, 5, cv2.GC_INIT_WITH_RECT)

    fg_mask = np.where(
        (mask == cv2.GC_FGD) | (mask == cv2.GC_PR_FGD),
        255,
        0,
    ).astype(np.uint8)
    fg_mask[connected_background > 0] = 0
    if np.any(portrait_prior):
        portrait_keep = np.where(
            (portrait_prior >= 140) & (background_like == 0) & (connected_background == 0),
            255,
            0,
        ).astype(np.uint8)
        fg_mask = cv2.bitwise_or(fg_mask, portrait_keep)

    fg_mask = _largest_foreground_component(fg_mask)
    foreground_ratio = float((fg_mask > 0).mean())
    if foreground_ratio < 0.02:
        fg_mask = _largest_foreground_component(_grabcut_with_rectangle(work))

    kernel_size = max(3, int(round(min(ww, wh) * 0.012)))
    if kernel_size % 2 == 0:
        kernel_size += 1
    kernel = cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (kernel_size, kernel_size))
    fg_mask = cv2.morphologyEx(fg_mask, cv2.MORPH_CLOSE, kernel, iterations=2)
    fg_mask = cv2.morphologyEx(fg_mask, cv2.MORPH_OPEN, kernel, iterations=1)

    blur_size = max(3, int(round(min(ww, wh) * 0.01)))
    if blur_size % 2 == 0:
        blur_size += 1
    alpha = cv2.GaussianBlur(fg_mask, (blur_size, blur_size), 0)

    if scale < 1.0:
        alpha = cv2.resize(alpha, (w, h), interpolation=cv2.INTER_LINEAR)

    b, g, r = cv2.split(image)
    return cv2.merge([b, g, r, alpha])
