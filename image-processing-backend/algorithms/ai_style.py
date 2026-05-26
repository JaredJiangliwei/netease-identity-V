"""
AI image-to-image 风格化滤镜（基于 SDXL-Turbo）。

依赖 torch + diffusers + transformers + accelerate + safetensors。
首次调用时会下载约 7GB 的模型权重，建议在 NVIDIA GPU 上运行。
CPU 也能跑，但单张图通常需要 1-3 分钟。

本版只保留 3 个针对人像/合照精调过的风格：
  webtoon / 3d_cartoon / cyberpunk_anime

并新增自动人像分析功能：
  - OpenCV Haar 级联自动检测可见人脸数量
  - CLIP 零样本估计每个人的 male-presenting / female-presenting
  - 根据检测结果动态拼接 prompt（人数、性别呈现、美化方向、负向 prompt），
    在保持身份的前提下做更自然的风格化与美化
CLIP 会在首次需要时懒加载；如果未安装 transformers，会自动降级为只做人数控制。
"""
from __future__ import annotations

import os
import threading

import cv2
import numpy as np

_MODEL_ID = "stabilityai/sdxl-turbo"
_GENDER_MODEL_ID = "openai/clip-vit-base-patch32"

_pipe = None
_pipe_lock = threading.Lock()
_load_error: str | None = None

_clip_processor = None
_clip_model = None
_clip_lock = threading.Lock()
_clip_load_error: str | None = None


STYLE_PRESETS = {
    "webtoon": {
        "prompt": (
            "webtoon style illustration based on the input photo, "
            "preserve each visible person's identity, facial identity, face shape, "
            "hairstyle, clothing, pose, expression and relative position, "
            "preserve glasses if present, preserve important objects in hand if present, "
            "preserve the original background layout and scene composition, "
            "clean smooth line art, bright natural colors, soft cel shading, "
            "modern Korean webtoon look, semi-realistic human face, "
            "clear normal human eyes, visible white sclera, natural eye whites, "
            "clear iris and pupils, realistic eye highlights, not fully black eyes, "
            "natural pupils, natural eyelids, natural mouth, "
            "more attractive but still recognizable, refined facial features, "
            "handsome if male-presenting, beautiful if female-presenting, "
            "clean skin, flattering lighting, do not overbeautify, "
            "do not change age, do not replace the people"
        ),
        "strength": 0.56,
        "guidance": 7.0,
        "steps": 28,
    },
    "3d_cartoon": {
        "prompt": (
            "soft 3D cartoon portrait based on the input photo, "
            "preserve each visible person's identity, facial identity, face shape, "
            "hairstyle, clothing, pose, expression and relative position, "
            "preserve glasses if present, preserve important foreground objects if present, "
            "preserve the original background layout and scene composition, "
            "cute stylized 3D animated movie look, smooth but natural skin, "
            "soft studio lighting, rounded friendly facial features, "
            "realistic human proportions, clear normal human eyes, "
            "visible white sclera, natural eye whites, clear iris and pupils, "
            "realistic eye highlights, not fully black eyes, natural pupils, "
            "natural eyelids, natural smile, "
            "more attractive but still recognizable, refined facial features, "
            "handsome if male-presenting, beautiful if female-presenting, "
            "polished 3D character look, flattering lighting, do not overbeautify, "
            "do not change age, do not replace the people"
        ),
        "strength": 0.54,
        "guidance": 7.0,
        "steps": 28,
    },
    "cyberpunk_anime": {
        "prompt": (
            "cyberpunk anime portrait based on the input photo, "
            "preserve each visible person's identity, facial identity, face shape, "
            "hairstyle, clothing, pose, expression and relative position, "
            "preserve glasses if present, preserve important foreground objects if present, "
            "preserve the original background layout and scene composition, "
            "futuristic neon lighting, cyan and magenta color grading, "
            "stylish anime illustration, cyberpunk atmosphere, urban night mood, "
            "high contrast lighting, sharp stylish linework, "
            "clear normal human eyes, visible white sclera, natural eye whites, "
            "clear iris and pupils, realistic eye highlights, not fully black eyes, "
            "natural pupils, natural eyelids, natural face structure, not scary, "
            "more attractive but still recognizable, refined facial features, "
            "handsome if male-presenting, beautiful if female-presenting, "
            "stylish and charismatic look, flattering neon lighting, do not overbeautify, "
            "do not change age, do not replace the people"
        ),
        "strength": 0.60,
        "guidance": 7.0,
        "steps": 28,
    },
}

NEGATIVE_PROMPT = (
    "different person, changed identity, unrecognizable face, "
    "changed gender presentation, gender swap, changed age, "
    "different hairstyle, different face shape, no glasses if glasses are present in input, "
    "extra person, additional person, added person, duplicate person, duplicated people, "
    "extra people, crowd, background people added, random person, stranger, "
    "missing person, removed person, fewer people, more people, "
    "merged people, fused people, overlapping people, two heads on one body, "
    "extra face, duplicate face, floating face, "
    "deformed face, distorted face, ugly face, scary face, creepy face, "
    "monster, demon, ghost, zombie, alien, non-human face, animal face, "
    "bad eyes, distorted eyes, asymmetrical eyes, crossed eyes, empty eyes, "
    "fully black eyes, all-black eyes, pitch black eyes, no eye whites, "
    "missing sclera, black sclera, dark sclera, empty black eyes, soulless eyes, "
    "glowing eyes, multiple eyes, missing eye, extra eye, malformed pupils, "
    "bad mouth, distorted mouth, bad teeth, "
    "bad anatomy, bad hands, extra fingers, missing fingers, extra limbs, "
    "changed background layout, missing important object, added unrelated object, "
    "overbeautified, plastic face, doll face, excessive makeup, fake face, "
    "low quality, blurry, noisy, oversaturated, watermark, logo, text artifacts"
)


_NUMBER_WORDS = {
    0: "zero", 1: "one", 2: "two", 3: "three", 4: "four", 5: "five",
    6: "six", 7: "seven", 8: "eight", 9: "nine", 10: "ten",
}


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
            from diffusers import StableDiffusionXLImg2ImgPipeline
            from huggingface_hub import snapshot_download
        except ImportError as e:
            _load_error = (
                "AI style filter requires torch + diffusers. "
                "Install with: pip install -r requirements-ai.txt"
            )
            raise RuntimeError(_load_error) from e

        device = "cuda" if torch.cuda.is_available() else "cpu"
        kwargs = {
            "use_safetensors": True,
            "low_cpu_mem_usage": True,
        }
        if device == "cuda":
            kwargs["torch_dtype"] = torch.float16
            kwargs["variant"] = "fp16"
        else:
            kwargs["torch_dtype"] = torch.float32

        model_dir = snapshot_download(
            _MODEL_ID,
            local_files_only=True,
            allow_patterns=[
                "model_index.json",
                "scheduler/*",
                "tokenizer/*",
                "tokenizer_2/*",
                "text_encoder/config.json",
                "text_encoder/model.fp16.safetensors",
                "text_encoder_2/config.json",
                "text_encoder_2/model.fp16.safetensors",
                "unet/config.json",
                "unet/diffusion_pytorch_model.fp16.safetensors",
                "vae/config.json",
                "vae/diffusion_pytorch_model.fp16.safetensors",
            ],
        )
        model_dir = os.path.realpath(model_dir)

        if device == "cuda":
            offload_folder = os.path.join(os.path.dirname(os.path.dirname(__file__)), ".model-offload")
            os.makedirs(offload_folder, exist_ok=True)
            kwargs.update(
                {
                    "device_map": "balanced",
                    "max_memory": {0: "6GiB", "cpu": "12GiB"},
                    "offload_folder": offload_folder,
                }
            )

        pipe = StableDiffusionXLImg2ImgPipeline.from_pretrained(model_dir, **kwargs)
        if device != "cuda" or "device_map" not in kwargs:
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


def _load_clip():
    """懒加载 CLIP（用于估计 male-presenting / female-presenting）。"""
    global _clip_processor, _clip_model, _clip_load_error

    if _clip_load_error is not None:
        return None, None
    if _clip_processor is not None and _clip_model is not None:
        return _clip_processor, _clip_model

    with _clip_lock:
        if _clip_processor is not None and _clip_model is not None:
            return _clip_processor, _clip_model
        try:
            import torch
            from transformers import CLIPModel, CLIPProcessor
        except ImportError as e:
            _clip_load_error = f"transformers/CLIP not available: {e}"
            return None, None

        device = "cuda" if torch.cuda.is_available() else "cpu"
        dtype = torch.float16 if device == "cuda" else torch.float32

        processor = CLIPProcessor.from_pretrained(_GENDER_MODEL_ID)
        model = CLIPModel.from_pretrained(_GENDER_MODEL_ID, torch_dtype=dtype).to(device)
        model.eval()
        model._sustech_device = device

        _clip_processor = processor
        _clip_model = model
        return _clip_processor, _clip_model


def _detect_faces_bgr(cv_img_bgr: np.ndarray, min_size: int = 40):
    gray = cv2.cvtColor(cv_img_bgr, cv2.COLOR_BGR2GRAY)
    cascade_path = cv2.data.haarcascades + "haarcascade_frontalface_default.xml"
    cascade = cv2.CascadeClassifier(cascade_path)
    faces = cascade.detectMultiScale(
        gray, scaleFactor=1.08, minNeighbors=4, minSize=(min_size, min_size)
    )
    boxes = [(int(x), int(y), int(w), int(h)) for (x, y, w, h) in faces]
    boxes.sort(key=lambda b: b[0])  # 左到右
    return boxes


def _crop_face_with_margin(cv_img_bgr: np.ndarray, box, margin: float = 0.45):
    x, y, w, h = box
    H, W = cv_img_bgr.shape[:2]
    cx, cy = x + w / 2, y + h / 2
    nw, nh = w * (1 + margin), h * (1 + margin)
    x1 = max(0, int(cx - nw / 2))
    y1 = max(0, int(cy - nh / 2))
    x2 = min(W, int(cx + nw / 2))
    y2 = min(H, int(cy + nh / 2))
    return cv_img_bgr[y1:y2, x1:x2].copy()


def _estimate_gender_presentation(face_bgr: np.ndarray):
    processor, model = _load_clip()
    if processor is None or model is None:
        return {"label": "unknown", "confidence": 0.0}

    import torch
    from PIL import Image

    pil_face = Image.fromarray(cv2.cvtColor(face_bgr, cv2.COLOR_BGR2RGB))
    labels = [
        "a portrait photo of a male-presenting person",
        "a portrait photo of a female-presenting person",
    ]
    device = getattr(model, "_sustech_device", "cpu")
    inputs = processor(text=labels, images=pil_face, return_tensors="pt", padding=True).to(device)

    with torch.no_grad():
        outputs = model(**inputs)
        probs = outputs.logits_per_image.softmax(dim=-1)[0].detach().float().cpu().numpy()

    male_p, female_p = float(probs[0]), float(probs[1])
    if max(male_p, female_p) < 0.58:
        return {"label": "unknown", "confidence": max(male_p, female_p)}
    if male_p >= female_p:
        return {"label": "male-presenting", "confidence": male_p}
    return {"label": "female-presenting", "confidence": female_p}


def analyze_people(cv_img_bgr: np.ndarray, detect_gender: bool = True):
    """检测人脸数量 + 每人男女呈现估计。"""
    faces = _detect_faces_bgr(cv_img_bgr)
    genders = []
    if detect_gender:
        for box in faces:
            face_crop = _crop_face_with_margin(cv_img_bgr, box)
            if face_crop.size == 0:
                genders.append({"label": "unknown", "confidence": 0.0})
            else:
                genders.append(_estimate_gender_presentation(face_crop))
    else:
        genders = [{"label": "unknown", "confidence": 0.0} for _ in faces]
    return {"count": len(faces), "faces": faces, "genders": genders}


def _build_people_count_prompt(analysis):
    count = analysis.get("count", 0)
    if not count:
        return (
            "preserve the exact same number of visible people as in the input photo, "
            "do not add any extra person, do not remove any person, "
            "do not duplicate any person, do not merge people together, "
            "preserve all visible people and their positions"
        )
    word = _NUMBER_WORDS.get(count, str(count))
    noun = "person" if count == 1 else "people"
    return (
        f"the input photo contains exactly {word} visible {noun}, "
        f"generate exactly {word} visible {noun}, "
        f"not more than {word}, not fewer than {word}, "
        "do not add any extra person, do not remove any person, "
        "do not duplicate any person, do not create background people, "
        "do not merge people together, preserve each visible person's position and spacing"
    )


def _build_gender_prompt(analysis):
    genders = analysis.get("genders", [])
    if not genders:
        return "preserve the same gender presentation as the input photo"
    desc = []
    for i, g in enumerate(genders, start=1):
        label = g.get("label", "unknown")
        if label == "male-presenting":
            desc.append(f"person {i} appears male-presenting")
        elif label == "female-presenting":
            desc.append(f"person {i} appears female-presenting")
        else:
            desc.append(f"person {i}'s gender presentation is unclear")
    return (
        "preserve each person's gender presentation, "
        + ", ".join(desc)
        + ", do not change male-presenting people into female-presenting people, "
        + "do not change female-presenting people into male-presenting people"
    )


def _build_beauty_prompt(analysis):
    genders = [g.get("label", "unknown") for g in analysis.get("genders", [])]
    base = (
        "make the visible people more attractive in a natural way, "
        "refined facial features, clean skin, flattering lighting, stylish appearance, "
        "aesthetic enhancement while preserving identity, not a different person"
    )
    if genders and all(g == "male-presenting" for g in genders):
        return base + ", make them handsome, charismatic, refined and natural"
    if genders and all(g == "female-presenting" for g in genders):
        return base + ", make them beautiful, elegant, refined and natural"
    if genders and ("male-presenting" in genders or "female-presenting" in genders):
        return base + ", make male-presenting people handsome and female-presenting people beautiful, natural and tasteful"
    return base + ", handsome or beautiful according to the original person, natural and tasteful"


def _build_dynamic_negative(analysis):
    count = analysis.get("count", 0)
    genders = [g.get("label", "unknown") for g in analysis.get("genders", [])]
    neg = (
        "extra person, additional person, added person, duplicate person, duplicated people, "
        "missing person, removed person, fewer people, more people, random background person, "
        "crowd added, stranger added, merged people, fused people"
    )
    if count == 1:
        neg += ", two people, three people, group photo, extra body, extra face"
    elif count and count > 1:
        neg += ", wrong number of people, missing group member, extra group member"
    if genders and all(g == "male-presenting" for g in genders):
        neg += ", female, woman, girl, changed to female, feminine face"
    elif genders and all(g == "female-presenting" for g in genders):
        neg += ", male, man, boy, changed to male, masculine face"
    return neg


def _build_auto_pack(cv_img_bgr: np.ndarray):
    analysis = analyze_people(cv_img_bgr)
    positive = (
        _build_people_count_prompt(analysis)
        + ", " + _build_gender_prompt(analysis)
        + ", " + _build_beauty_prompt(analysis)
    )
    return {
        "analysis": analysis,
        "positive": positive,
        "negative": _build_dynamic_negative(analysis),
    }


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
    use_auto_people_prompt: bool = True,
    extra_prompt: str = "",
) -> np.ndarray:
    if style_name not in STYLE_PRESETS:
        raise ValueError(f"Unknown AI style: {style_name}")

    cfg = STYLE_PRESETS[style_name]
    use_strength = float(strength) if strength is not None else cfg["strength"]
    guidance = float(cfg["guidance"])
    steps = int(cfg["steps"])

    if _is_turbo(_MODEL_ID):
        guidance = min(guidance, 2.0)
        steps = min(steps, 8)

    prompt = cfg["prompt"]
    final_negative = NEGATIVE_PROMPT
    if use_auto_people_prompt:
        try:
            pack = _build_auto_pack(cv_img_bgr)
            prompt = prompt + ", " + pack["positive"]
            final_negative = final_negative + ", " + pack["negative"]
        except Exception:
            # 人脸/CLIP 检测失败时降级，不影响主流程
            pass
    if extra_prompt and extra_prompt.strip():
        prompt = prompt + ", " + extra_prompt.strip()

    pipe = _load_pipeline()

    import torch
    from PIL import Image

    rgb = cv2.cvtColor(cv_img_bgr, cv2.COLOR_BGR2RGB)
    pil_in = Image.fromarray(rgb)
    pil_in = _resize_keep_aspect_to_multiple_of_8(pil_in, max_side=max_side)

    device = getattr(pipe, "_sustech_device", "cpu")
    generator = torch.Generator(device=device).manual_seed(int(seed))

    result = pipe(
        prompt=prompt,
        negative_prompt=final_negative,
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
