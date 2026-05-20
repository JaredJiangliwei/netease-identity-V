"""
AI image-to-image 风格化滤镜（基于 SDXL-Turbo）。

依赖 torch + diffusers + transformers + accelerate + safetensors。
首次调用时会下载约 7GB 的模型权重，建议在 NVIDIA GPU 上运行。
CPU 也能跑，但单张图通常需要 1-3 分钟。
"""
from __future__ import annotations

import io
import threading

import cv2
import numpy as np

_MODEL_ID = "stabilityai/sdxl-turbo"

_pipe = None
_pipe_lock = threading.Lock()
_load_error: str | None = None


STYLE_PRESETS = {
    "webtoon": {
        "prompt": (
            "webtoon style illustration, clean smooth line art, bright colors, "
            "soft cel shading, modern webtoon look"
        ),
        "strength": 0.58,
        "guidance": 7.0,
        "steps": 28,
    },
    "3d_cartoon": {
        "prompt": (
            "3D cartoon style portrait, cute stylized 3D animated movie look, "
            "smooth skin, soft lighting"
        ),
        "strength": 0.56,
        "guidance": 7.0,
        "steps": 28,
    },
    "manga_color": {
        "prompt": (
            "colored manga style illustration, clean manga line art, "
            "flat but natural colors, soft shading"
        ),
        "strength": 0.60,
        "guidance": 7.0,
        "steps": 28,
    },
    "anime_key_visual": {
        "prompt": (
            "anime key visual illustration, clean anime line art, cel shading, "
            "vibrant but natural colors, professional anime poster style"
        ),
        "strength": 0.55,
        "guidance": 7.0,
        "steps": 28,
    },
    "anime_strong": {
        "prompt": (
            "strong anime illustration style, expressive anime aesthetics, "
            "clean black line art, cel shaded rendering, colorful anime style"
        ),
        "strength": 0.62,
        "guidance": 7.5,
        "steps": 30,
    },
    "comic_book": {
        "prompt": (
            "American comic book style illustration, bold ink outlines, "
            "graphic novel shading, vivid colors, strong but controlled contrast"
        ),
        "strength": 0.58,
        "guidance": 7.0,
        "steps": 28,
    },
    "watercolor": {
        "prompt": (
            "watercolor illustration, soft color bleeding, hand-painted texture, "
            "gentle brush strokes, artistic painting style"
        ),
        "strength": 0.50,
        "guidance": 7.0,
        "steps": 28,
    },
    "pastel_illustration": {
        "prompt": (
            "soft pastel illustration, gentle colors, dreamy lighting, "
            "soft cartoon style"
        ),
        "strength": 0.50,
        "guidance": 7.0,
        "steps": 28,
    },
    "cyberpunk_anime": {
        "prompt": (
            "cyberpunk anime style illustration, subtle neon blue and magenta lighting, "
            "futuristic atmosphere, stylized anime aesthetic"
        ),
        "strength": 0.62,
        "guidance": 7.5,
        "steps": 30,
    },
    "fantasy_storybook": {
        "prompt": (
            "fantasy storybook illustration, magical soft lighting, "
            "whimsical colors, storybook painting style"
        ),
        "strength": 0.56,
        "guidance": 7.0,
        "steps": 28,
    },
    "black_white_manga": {
        "prompt": (
            "black and white manga style drawing, clean ink line art, "
            "screentone shading, high contrast manga page style"
        ),
        "strength": 0.55,
        "guidance": 7.0,
        "steps": 28,
    },
    "oil_painting": {
        "prompt": (
            "oil painting portrait, expressive brush strokes, rich colors, "
            "painterly texture, artistic lighting"
        ),
        "strength": 0.50,
        "guidance": 7.0,
        "steps": 28,
    },
    "lineart_flat_color": {
        "prompt": (
            "clean digital line art and flat color illustration, "
            "bold clean outlines, flat colors, minimal shading, poster-like cartoon design"
        ),
        "strength": 0.55,
        "guidance": 7.0,
        "steps": 28,
    },
}

NEGATIVE_PROMPT = (
    "deformed face, distorted eyes, bad anatomy, extra fingers, missing fingers, "
    "extra limbs, duplicate person, ugly, low quality, blurry, watermark, "
    "logo, text artifacts"
)


def list_styles():
    return list(STYLE_PRESETS.keys())


def _is_turbo(model_id: str) -> bool:
    return "turbo" in model_id.lower()


def _load_pipeline():
    global _pipe, _load_error

    if _pipe is not None:
        return _pipe
    if _load_error is not None:
        raise RuntimeError(_load_error)

    with _pipe_lock:
        if _pipe is not None:
            return _pipe
        try:
            import torch
            from diffusers import AutoPipelineForImage2Image
        except ImportError as e:
            _load_error = (
                "AI style filter requires torch + diffusers. "
                "Install with: pip install -r requirements-ai.txt"
            )
            raise RuntimeError(_load_error) from e

        device = "cuda" if torch.cuda.is_available() else "cpu"
        kwargs = {"use_safetensors": True}
        if device == "cuda":
            kwargs["torch_dtype"] = torch.float16
            kwargs["variant"] = "fp16"
        else:
            kwargs["torch_dtype"] = torch.float32

        pipe = AutoPipelineForImage2Image.from_pretrained(_MODEL_ID, **kwargs)
        pipe = pipe.to(device)

        if device == "cuda":
            try:
                pipe.enable_attention_slicing()
            except Exception:
                pass
            try:
                pipe.vae.enable_slicing()
            except Exception:
                pass

        pipe._sustech_device = device
        _pipe = pipe
        return _pipe


def _resize_keep_aspect_to_multiple_of_8(pil_img, max_side=1024):
    w, h = pil_img.size
    scale = min(max_side / max(w, h), 1.0)
    new_w = max(64, (int(w * scale) // 8) * 8)
    new_h = max(64, (int(h * scale) // 8) * 8)
    if (new_w, new_h) == (w, h):
        return pil_img
    from PIL import Image
    return pil_img.resize((new_w, new_h), Image.LANCZOS)


def apply_ai_style(
    cv_img_bgr: np.ndarray,
    style_name: str,
    strength: float | None = None,
    seed: int = 42,
    max_side: int = 1024,
) -> np.ndarray:
    if style_name not in STYLE_PRESETS:
        raise ValueError(f"Unknown AI style: {style_name}")

    cfg = STYLE_PRESETS[style_name]
    use_strength = float(strength) if strength is not None else cfg["strength"]
    guidance = float(cfg["guidance"])
    steps = int(cfg["steps"])

    if _is_turbo(_MODEL_ID):
        guidance = min(guidance, 2.0)
        steps = min(steps, 6)

    pipe = _load_pipeline()

    import torch
    from PIL import Image

    rgb = cv2.cvtColor(cv_img_bgr, cv2.COLOR_BGR2RGB)
    pil_in = Image.fromarray(rgb)
    pil_in = _resize_keep_aspect_to_multiple_of_8(pil_in, max_side=max_side)

    device = getattr(pipe, "_sustech_device", "cpu")
    generator = torch.Generator(device=device).manual_seed(int(seed))

    result = pipe(
        prompt=cfg["prompt"],
        negative_prompt=NEGATIVE_PROMPT,
        image=pil_in,
        strength=use_strength,
        guidance_scale=guidance,
        num_inference_steps=steps,
        generator=generator,
    ).images[0]

    out_rgb = np.array(result)
    out_bgr = cv2.cvtColor(out_rgb, cv2.COLOR_RGB2BGR)

    if out_bgr.shape[:2] != cv_img_bgr.shape[:2]:
        out_bgr = cv2.resize(
            out_bgr,
            (cv_img_bgr.shape[1], cv_img_bgr.shape[0]),
            interpolation=cv2.INTER_LANCZOS4,
        )
    return out_bgr
