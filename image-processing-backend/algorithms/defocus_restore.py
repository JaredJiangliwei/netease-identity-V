"""
失焦/模糊人脸恢复模块,基于 CodeFormer (https://github.com/sczhou/CodeFormer)。

针对模糊、低分辨率、失焦的人脸照片做修复。`w` (fidelity weight)
控制"画质 vs 保真"的权衡:
  - w 越小:画质优先,五官重建更激进、更清晰,但可能偏离原貌
  - w 越大:保真优先,更接近原图,但锐化幅度较小

实现采用 subprocess 调用 CodeFormer 自带的 inference 脚本,避免在本仓库
直接持有 CodeFormer 源码。用户需先按 README 提示把 CodeFormer 仓库
clone 到 `image-processing-backend/external/CodeFormer/` 下并装好依赖。
"""
from __future__ import annotations

import base64
import glob
import os
import subprocess
import sys
import tempfile
import threading

import cv2
import numpy as np


DEFAULT_WEIGHTS = [0.3, 0.4, 0.5, 0.6]

_THIS_DIR = os.path.dirname(os.path.abspath(__file__))
_CODEFORMER_DIR = os.path.normpath(
    os.path.join(_THIS_DIR, "..", "external", "CodeFormer")
)

# 同时只允许一次推理,避免显存抢占
_inference_lock = threading.Lock()


def codeformer_available() -> bool:
    return os.path.exists(os.path.join(_CODEFORMER_DIR, "inference_codeformer.py"))


def _ensure_available():
    if not codeformer_available():
        raise RuntimeError(
            "未检测到 CodeFormer。请先把 CodeFormer 仓库 clone 到 "
            f"`{_CODEFORMER_DIR}`,并按 README 装好其依赖。"
        )


def _imread_any(path: str):
    img = cv2.imread(path, cv2.IMREAD_COLOR)
    if img is None:
        img = cv2.imdecode(np.fromfile(path, dtype=np.uint8), cv2.IMREAD_COLOR)
    return img


def restore_with_weights(
    img_bgr,
    weights=None,
    upscale: int = 2,
    face_upsample: bool = True,
    bg_upsampler: str = "realesrgan",
):
    """
    对单张图分别用多个 w 跑 CodeFormer,返回每个 w 对应的修复图。

    返回: List[dict],每个 dict 形如 {"weight": float, "image": np.ndarray(BGR)}
    顺序与传入 weights 一致。
    """
    _ensure_available()

    if weights is None:
        weights = DEFAULT_WEIGHTS
    weights = [float(w) for w in weights if w is not None]
    if not weights:
        raise ValueError("weights 不能为空")
    # 简单去重 + clamp
    weights = sorted({round(max(0.0, min(1.0, w)), 3) for w in weights})

    upscale = int(max(1, min(8, upscale)))

    with _inference_lock, tempfile.TemporaryDirectory(prefix="codeformer_") as tmp_dir:
        input_dir = os.path.join(tmp_dir, "in")
        os.makedirs(input_dir, exist_ok=True)
        in_path = os.path.join(input_dir, "image.png")
        cv2.imwrite(in_path, img_bgr)

        results = []
        for w in weights:
            out_dir = os.path.join(tmp_dir, f"out_w{int(round(w * 100)):02d}")
            cmd = [
                sys.executable,
                "inference_codeformer.py",
                "-w", f"{w}",
                "--input_path", input_dir,
                "--upscale", str(upscale),
                "--output_path", out_dir,
            ]
            if face_upsample:
                cmd.append("--face_upsample")
            if bg_upsampler:
                cmd.extend(["--bg_upsampler", bg_upsampler])

            proc = subprocess.run(
                cmd,
                cwd=_CODEFORMER_DIR,
                capture_output=True,
                text=True,
                env={**os.environ, "PYTHONIOENCODING": "utf-8"},
            )
            if proc.returncode != 0:
                tail = (proc.stderr or proc.stdout or "")[-800:]
                raise RuntimeError(
                    f"CodeFormer 推理失败 (w={w}, exit={proc.returncode}):\n{tail}"
                )

            final_dir = os.path.join(out_dir, "final_results")
            candidates = sorted(glob.glob(os.path.join(final_dir, "*")))
            if not candidates:
                # 有些版本输出到 restored_imgs 目录
                alt_dir = os.path.join(out_dir, "restored_imgs")
                candidates = sorted(glob.glob(os.path.join(alt_dir, "*")))
            if not candidates:
                raise RuntimeError(f"CodeFormer 未生成输出 (w={w}),检查 {out_dir}")

            out_img = _imread_any(candidates[0])
            if out_img is None:
                raise RuntimeError(f"无法读取 CodeFormer 输出文件: {candidates[0]}")
            results.append({"weight": w, "image": out_img})

    return results
