import cv2
import numpy as np


def _motion_psf(length: int, angle: float) -> np.ndarray:
    length = int(np.clip(length, 1, 99))
    size = max(3, length)
    if size % 2 == 0:
        size += 1

    kernel = np.zeros((size, size), dtype=np.float32)
    center = size // 2
    radius = max(1, length // 2)
    theta = np.deg2rad(angle)
    dx = int(round(np.cos(theta) * radius))
    dy = int(round(np.sin(theta) * radius))

    cv2.line(
        kernel,
        (center - dx, center - dy),
        (center + dx, center + dy),
        1.0,
        thickness=1,
        lineType=cv2.LINE_AA,
    )

    total = float(kernel.sum())
    if total <= 0:
        kernel[center, center] = 1.0
        return kernel
    return kernel / total


def _wiener_channel(channel: np.ndarray, psf: np.ndarray, noise: float) -> np.ndarray:
    channel_f = channel.astype(np.float32) / 255.0
    h, w = channel_f.shape

    # Frequency-domain deconvolution assumes circular convolution. Reflect padding
    # gives the FFT softer borders, which reduces the dark ringing that otherwise
    # overwhelms the restoration on real photos.
    pad = max(psf.shape) * 2
    channel_f = cv2.copyMakeBorder(
        channel_f,
        pad,
        pad,
        pad,
        pad,
        borderType=cv2.BORDER_REFLECT_101,
    )
    ph, pw = channel_f.shape

    padded = np.zeros((ph, pw), dtype=np.float32)
    kh, kw = psf.shape
    padded[:kh, :kw] = psf
    padded = np.roll(padded, -(kh // 2), axis=0)
    padded = np.roll(padded, -(kw // 2), axis=1)

    image_fft = np.fft.fft2(channel_f)
    psf_fft = np.fft.fft2(padded)
    psf_conj = np.conj(psf_fft)
    restored_fft = psf_conj / (np.abs(psf_fft) ** 2 + noise) * image_fft
    restored = np.real(np.fft.ifft2(restored_fft))

    restored = restored[pad:pad + h, pad:pad + w]
    restored = np.clip(restored, 0.0, 1.0)
    return (restored * 255.0).astype(np.uint8)


def _richardson_lucy_channel(channel: np.ndarray, psf: np.ndarray, iterations: int) -> np.ndarray:
    observed = channel.astype(np.float32) / 255.0
    estimate = np.maximum(observed, 1.0 / 255.0)
    psf_mirror = psf[::-1, ::-1]

    iterations = int(np.clip(iterations, 4, 40))
    for _ in range(iterations):
        blurred_estimate = cv2.filter2D(
            estimate,
            -1,
            psf,
            borderType=cv2.BORDER_REFLECT_101,
        )
        relative_blur = observed / np.maximum(blurred_estimate, 1e-4)
        correction = cv2.filter2D(
            relative_blur,
            -1,
            psf_mirror,
            borderType=cv2.BORDER_REFLECT_101,
        )
        estimate *= correction
        estimate = np.clip(estimate, 0.0, 1.0)

    return (estimate * 255.0).astype(np.uint8)


def _match_luminance_stats(source: np.ndarray, restored: np.ndarray, amount: float = 0.85) -> np.ndarray:
    source_f = source.astype(np.float32)
    restored_f = restored.astype(np.float32)
    source_mean, source_std = cv2.meanStdDev(source_f)
    restored_mean, restored_std = cv2.meanStdDev(restored_f)

    source_std_value = max(float(source_std[0][0]), 1.0)
    restored_std_value = max(float(restored_std[0][0]), 1.0)
    matched = (restored_f - float(restored_mean[0][0])) * (source_std_value / restored_std_value)
    matched += float(source_mean[0][0])
    blended = cv2.addWeighted(
        np.clip(matched, 0, 255).astype(np.uint8),
        float(np.clip(amount, 0.0, 1.0)),
        restored,
        1.0 - float(np.clip(amount, 0.0, 1.0)),
        0,
    )
    return blended


def _dering_luminance(original: np.ndarray, restored: np.ndarray, denoise: float = 5.0) -> np.ndarray:
    if denoise <= 0:
        return _match_luminance_stats(original, restored, amount=0.65)

    if denoise > 0:
        restored = cv2.fastNlMeansDenoising(
            restored,
            None,
            h=float(denoise),
            templateWindowSize=7,
            searchWindowSize=21,
        )

    restored = _match_luminance_stats(original, restored)

    # A small CLAHE pass restores local contrast after denoising without creating
    # the strong halos that a second sharpening pass would introduce.
    clahe = cv2.createCLAHE(clipLimit=1.35, tileGridSize=(8, 8))
    enhanced = clahe.apply(restored)
    return cv2.addWeighted(enhanced, 0.25, restored, 0.75, 0)


def clarity_restore(image: np.ndarray) -> np.ndarray:
    """
    Conservative non-blind clarity enhancement for mild defocus or low contrast.

    It does not try to invert a motion blur kernel, so it is safer when the input
    is generally soft instead of having clear linear motion trails.
    """
    if image is None:
        raise ValueError("Input image is None.")

    if image.ndim == 2:
        denoised = cv2.fastNlMeansDenoising(image, None, h=4.0, templateWindowSize=7, searchWindowSize=21)
        clahe = cv2.createCLAHE(clipLimit=1.5, tileGridSize=(8, 8))
        enhanced = clahe.apply(denoised)
        soft = cv2.GaussianBlur(enhanced, (0, 0), sigmaX=1.0)
        sharpened = cv2.addWeighted(enhanced, 1.28, soft, -0.28, 0)
        return _match_luminance_stats(image, sharpened)

    if image.ndim == 3 and image.shape[2] == 3:
        ycrcb = cv2.cvtColor(image, cv2.COLOR_BGR2YCrCb)
        y, cr, cb = cv2.split(ycrcb)
        restored_y = clarity_restore(y)
        return cv2.cvtColor(cv2.merge([restored_y, cr, cb]), cv2.COLOR_YCrCb2BGR)

    raise ValueError("Input image must be grayscale or BGR color image.")


def richardson_lucy_motion_deblur(
    image: np.ndarray,
    length: int = 15,
    angle: float = 0.0,
    iterations: int = 12,
    strength: float = 0.72,
    denoise: float = 4.0,
) -> np.ndarray:
    if image is None:
        raise ValueError("Input image is None.")

    length = int(np.clip(length, 1, 99))
    strength = float(np.clip(strength, 0.0, 1.0))
    psf = _motion_psf(length, angle)

    if image.ndim == 2:
        restored = _richardson_lucy_channel(image, psf, iterations)
        blended = cv2.addWeighted(restored, strength, image, 1.0 - strength, 0)
        return cv2.fastNlMeansDenoising(blended, None, h=denoise, templateWindowSize=7, searchWindowSize=21)

    if image.ndim == 3 and image.shape[2] == 3:
        ycrcb = cv2.cvtColor(image, cv2.COLOR_BGR2YCrCb)
        y, cr, cb = cv2.split(ycrcb)
        restored_y = _richardson_lucy_channel(y, psf, iterations)
        restored_y = cv2.addWeighted(restored_y, strength, y, 1.0 - strength, 0)
        restored_y = cv2.fastNlMeansDenoising(
            restored_y,
            None,
            h=denoise,
            templateWindowSize=7,
            searchWindowSize=21,
        )
        merged = cv2.merge([restored_y, cr, cb])
        return cv2.cvtColor(merged, cv2.COLOR_YCrCb2BGR)

    raise ValueError("Input image must be grayscale or BGR color image.")


def wiener_motion_deblur(
    image: np.ndarray,
    length: int = 15,
    angle: float = 0.0,
    noise: float = 0.01,
    strength: float = 0.72,
    post_sharpen: float = 0.12,
    dering: float = 5.0,
) -> np.ndarray:
    """
    Restore mild linear motion blur with Wiener deconvolution.

    length: estimated motion blur length in pixels.
    angle: motion direction in degrees.
    noise: Wiener regularization. Higher values reduce ringing/noise but restore less.
    """
    if image is None:
        raise ValueError("Input image is None.")

    length = int(np.clip(length, 1, 99))
    noise = float(np.clip(noise, 0.0001, 0.2))
    strength = float(np.clip(strength, 0.0, 1.0))
    post_sharpen = float(np.clip(post_sharpen, 0.0, 0.35))
    psf = _motion_psf(length, angle)

    if image.ndim == 2:
        restored = _wiener_channel(image, psf, noise)
        blended = cv2.addWeighted(restored, strength, image, 1.0 - strength, 0)
        if post_sharpen > 0:
            soft = cv2.GaussianBlur(blended, (0, 0), sigmaX=0.8)
            blended = cv2.addWeighted(blended, 1.0 + post_sharpen, soft, -post_sharpen, 0)
        return _dering_luminance(image, blended, denoise=dering)

    if image.ndim == 3 and image.shape[2] == 3:
        ycrcb = cv2.cvtColor(image, cv2.COLOR_BGR2YCrCb)
        y, cr, cb = cv2.split(ycrcb)
        restored_y = _wiener_channel(y, psf, noise)
        restored_y = cv2.addWeighted(restored_y, strength, y, 1.0 - strength, 0)
        if post_sharpen > 0:
            soft = cv2.GaussianBlur(restored_y, (0, 0), sigmaX=0.8)
            restored_y = cv2.addWeighted(restored_y, 1.0 + post_sharpen, soft, -post_sharpen, 0)
        restored_y = _dering_luminance(y, restored_y, denoise=dering)
        merged = cv2.merge([restored_y, cr, cb])
        return cv2.cvtColor(merged, cv2.COLOR_YCrCb2BGR)

    raise ValueError("Input image must be grayscale or BGR color image.")


def _quality_score(image: np.ndarray) -> float:
    if image.ndim == 3:
        gray = cv2.cvtColor(image, cv2.COLOR_BGR2GRAY)
    else:
        gray = image

    gray_f = gray.astype(np.float32)
    lap_var = cv2.Laplacian(gray_f, cv2.CV_32F).var()
    gx = cv2.Sobel(gray_f, cv2.CV_32F, 1, 0, ksize=3)
    gy = cv2.Sobel(gray_f, cv2.CV_32F, 0, 1, ksize=3)
    tenengrad = float(np.mean(gx * gx + gy * gy))
    saturated = float(np.mean((gray <= 2) | (gray >= 253)))

    # Prefer clear edges, but avoid candidates that create clipped ringing.
    return tenengrad + 0.35 * lap_var - saturated * 6000.0


def _sharpness(image: np.ndarray) -> float:
    if image.ndim == 3:
        gray = cv2.cvtColor(image, cv2.COLOR_BGR2GRAY)
    else:
        gray = image
    return float(cv2.Laplacian(gray.astype(np.float32), cv2.CV_32F).var())


def _candidate_score(input_image: np.ndarray, restored: np.ndarray, psf: np.ndarray) -> float:
    input_sharpness = max(_sharpness(input_image), 1.0)
    restored_sharpness = _sharpness(restored)
    reblurred = cv2.filter2D(restored, -1, psf, borderType=cv2.BORDER_REPLICATE)

    fidelity = float(np.mean((reblurred.astype(np.float32) - input_image.astype(np.float32)) ** 2))
    change = float(np.mean((restored.astype(np.float32) - input_image.astype(np.float32)) ** 2))
    input_saturated = float(np.mean((input_image <= 2) | (input_image >= 253)))
    restored_saturated = float(np.mean((restored <= 2) | (restored >= 253)))
    extra_saturated = max(0.0, restored_saturated - input_saturated)
    sharpness_cap = input_sharpness * (8.5 if input_sharpness < 40.0 else 1.8)
    sharpness_reward = min(restored_sharpness, sharpness_cap)
    excessive_sharpness = max(0.0, restored_sharpness - sharpness_cap)
    mean_shift = abs(float(restored.mean()) - float(input_image.mean()))

    return (
        sharpness_reward
        - 2.2 * fidelity
        - 0.22 * change
        - 900.0 * restored_saturated
        - 12000.0 * extra_saturated
        - 0.7 * excessive_sharpness
        - 35.0 * mean_shift
    )


def _low_detail_candidate_score(input_image: np.ndarray, restored: np.ndarray, psf: np.ndarray) -> float:
    input_sharpness = max(_sharpness(input_image), 1.0)
    restored_sharpness = _sharpness(restored)
    reblurred = cv2.filter2D(restored, -1, psf, borderType=cv2.BORDER_REPLICATE)

    fidelity = float(np.mean((reblurred.astype(np.float32) - input_image.astype(np.float32)) ** 2))
    change = float(np.mean((restored.astype(np.float32) - input_image.astype(np.float32)) ** 2))
    input_saturated = float(np.mean((input_image <= 2) | (input_image >= 253)))
    restored_saturated = float(np.mean((restored <= 2) | (restored >= 253)))
    extra_saturated = max(0.0, restored_saturated - input_saturated)
    mean_shift = abs(float(restored.mean()) - float(input_image.mean()))

    sharpness_cap = input_sharpness * 5.5
    target_change = 80.0
    return (
        min(restored_sharpness, sharpness_cap)
        - 1.25 * fidelity
        - 0.34 * abs(change - target_change)
        - 0.9 * max(0.0, restored_sharpness - sharpness_cap)
        - 2500.0 * extra_saturated
        - 22.0 * mean_shift
    )


def _estimate_motion_angles(image: np.ndarray, count: int = 5) -> list[int]:
    if image.ndim == 3:
        gray = cv2.cvtColor(image, cv2.COLOR_BGR2GRAY)
    else:
        gray = image

    gray = cv2.resize(gray, (0, 0), fx=0.5, fy=0.5, interpolation=cv2.INTER_AREA)
    gray_f = gray.astype(np.float32)
    gray_f = (gray_f - float(gray_f.mean())) / (float(gray_f.std()) + 1e-6)

    ranked = []
    for angle in range(0, 180, 15):
        theta = np.deg2rad(angle)
        correlations = []
        for distance in (3, 5, 7, 9, 12, 15):
            dx = int(round(np.cos(theta) * distance))
            dy = int(round(np.sin(theta) * distance))
            transform = np.float32([[1, 0, dx], [0, 1, dy]])
            shifted = cv2.warpAffine(
                gray_f,
                transform,
                (gray_f.shape[1], gray_f.shape[0]),
                flags=cv2.INTER_LINEAR,
                borderMode=cv2.BORDER_REFLECT,
            )
            correlations.append(float(np.mean(gray_f * shifted)))
        ranked.append((sum(correlations), angle))

    angles: list[int] = []
    for _, angle in sorted(ranked, reverse=True)[:count]:
        for candidate in (angle, angle + 5, angle - 5):
            normalized = int(candidate % 180)
            if normalized not in angles:
                angles.append(normalized)

    return angles


def _angle_correlation_ranks(image: np.ndarray, angles: list[int]) -> dict[int, int]:
    if image.ndim == 3:
        gray = cv2.cvtColor(image, cv2.COLOR_BGR2GRAY)
    else:
        gray = image

    gray = cv2.resize(gray, (0, 0), fx=0.5, fy=0.5, interpolation=cv2.INTER_AREA)
    gray_f = gray.astype(np.float32)
    gray_f = (gray_f - float(gray_f.mean())) / (float(gray_f.std()) + 1e-6)

    ranked = []
    for angle in angles:
        theta = np.deg2rad(angle)
        correlations = []
        for distance in (3, 5, 7, 9, 12, 15):
            dx = int(round(np.cos(theta) * distance))
            dy = int(round(np.sin(theta) * distance))
            transform = np.float32([[1, 0, dx], [0, 1, dy]])
            shifted = cv2.warpAffine(
                gray_f,
                transform,
                (gray_f.shape[1], gray_f.shape[0]),
                flags=cv2.INTER_LINEAR,
                borderMode=cv2.BORDER_REFLECT,
            )
            correlations.append(float(np.mean(gray_f * shifted)))
        ranked.append((sum(correlations), angle))

    return {angle: rank for rank, (_, angle) in enumerate(sorted(ranked, reverse=True))}


def _resize_for_search(image: np.ndarray, max_side: int = 420) -> tuple[np.ndarray, float]:
    h, w = image.shape[:2]
    longest = max(h, w)
    if longest <= max_side:
        return image, 1.0

    scale = max_side / longest
    resized = cv2.resize(
        image,
        (max(1, int(w * scale)), max(1, int(h * scale))),
        interpolation=cv2.INTER_AREA,
    )
    return resized, scale


def auto_wiener_motion_deblur(image: np.ndarray) -> tuple[np.ndarray, dict]:
    """
    Try several common motion blur kernels and choose a conservative restoration.

    The search is intentionally small so it stays usable from the web UI. It first
    scores candidates on a resized copy, then applies the best parameters once to
    the full-resolution image.
    """
    if image is None:
        raise ValueError("Input image is None.")

    work_img, scale = _resize_for_search(image)
    base_score = _sharpness(work_img)
    best = {
        "score": -1.0e18,
        "length": 1,
        "angle": 0.0,
        "noise": 0.035,
        "strength": 0.58,
        "method": "none",
        "iterations": 0,
    }

    low_detail = base_score < 40.0
    if low_detail:
        lengths = [15, 17, 21, 23, 27]
        angles = [0, 15, 30, 35, 45, 60, 75, 90, 105, 120, 135, 150, 165]
        angle_ranks = _angle_correlation_ranks(work_img, angles)
        noises = [0.005, 0.01, 0.02]
        strengths = [0.8, 0.92]
        score_candidate = _low_detail_candidate_score
    else:
        lengths = [7, 11, 15, 17, 21, 23, 27, 35]
        angles = [0, 15, 30, 35, 45, 60, 75, 90, 105, 120, 135, 150, 165]
        angle_ranks = {}
        noises = [0.005, 0.01, 0.02, 0.05]
        strengths = [0.8, 0.92]
        score_candidate = _candidate_score

    for length in lengths:
        scaled_length = max(1, int(round(length * scale)))
        for angle in angles:
            for noise in noises:
                for strength in strengths:
                    candidate = wiener_motion_deblur(
                        work_img,
                        scaled_length,
                        angle,
                        noise,
                        strength=strength,
                        post_sharpen=0.03,
                        dering=0.0,
                    )
                    score = score_candidate(work_img, candidate, _motion_psf(scaled_length, angle))
                    if low_detail:
                        score += 0.55 * length
                        score -= 1.2 * min(angle_ranks.get(angle, 6), 6)
                    if score > best["score"]:
                        best = {
                            "score": score,
                            "length": length,
                            "angle": float(angle),
                            "noise": noise,
                            "strength": strength,
                            "method": "wiener",
                            "iterations": 0,
                        }

    if best["method"] == "wiener":
        scaled_length = max(1, int(round(best["length"] * scale)))
        for iterations in [8, 12]:
            candidate = richardson_lucy_motion_deblur(
                work_img,
                scaled_length,
                best["angle"],
                iterations=iterations,
                strength=0.65,
                denoise=3.0,
            )
            score = _candidate_score(work_img, candidate, _motion_psf(scaled_length, best["angle"]))
            if score > best["score"]:
                best = {
                    "score": score,
                    "length": best["length"],
                    "angle": float(best["angle"]),
                    "noise": 0.0,
                    "strength": 0.65,
                    "method": "richardson_lucy",
                    "iterations": iterations,
                }

    minimum_score = max(6.0, base_score * 0.7)
    if best["length"] <= 1 or best["score"] < minimum_score:
        restored = clarity_restore(image)
        return restored, {
            "length": 0,
            "angle": 0.0,
            "noise": 0.0,
            "strength": 1.0,
            "method": "clarity",
            "iterations": 0,
            "scoreGain": 0.0,
        }

    if best["method"] == "richardson_lucy":
        restored = richardson_lucy_motion_deblur(
            image,
            int(best["length"]),
            float(best["angle"]),
            iterations=int(best["iterations"]),
            strength=float(best["strength"]),
            denoise=3.0,
        )
    else:
        restored = wiener_motion_deblur(
            image,
            int(best["length"]),
            float(best["angle"]),
            float(best["noise"]),
            strength=float(best["strength"]),
            post_sharpen=0.015 if low_detail else 0.03,
            dering=8.0 if low_detail else 5.0,
        )
    return restored, {
        "length": int(best["length"]),
        "angle": float(best["angle"]),
        "noise": float(best["noise"]),
        "strength": float(best["strength"]),
        "method": best["method"],
        "iterations": int(best["iterations"]),
        "scoreGain": float(best["score"] - base_score),
    }
