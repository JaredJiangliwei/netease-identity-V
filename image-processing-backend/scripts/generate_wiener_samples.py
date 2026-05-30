from __future__ import annotations

import json
import sys
import urllib.request
from pathlib import Path

import cv2
import numpy as np

ROOT = Path(__file__).resolve().parents[2]
BACKEND = ROOT / "image-processing-backend"
sys.path.insert(0, str(BACKEND))

from algorithms.wiener_deblur import _motion_psf, auto_wiener_motion_deblur  # noqa: E402


SOURCES = [
    (
        "eye_chart",
        "https://upload.wikimedia.org/wikipedia/commons/b/b8/Eye-chart.jpg",
        "Wikimedia Commons eye chart",
        17,
        0,
    ),
    (
        "opencv_sudoku",
        "https://raw.githubusercontent.com/opencv/opencv/master/samples/data/sudoku.png",
        "OpenCV sample sudoku grid",
        21,
        35,
    ),
    (
        "opencv_box",
        "https://raw.githubusercontent.com/opencv/opencv/master/samples/data/box.png",
        "OpenCV sample box image",
        15,
        0,
    ),
    (
        "opencv_fruits",
        "https://raw.githubusercontent.com/opencv/opencv/master/samples/data/fruits.jpg",
        "OpenCV sample fruits image",
        23,
        120,
    ),
]


def save_png(path: Path, image: np.ndarray) -> None:
    ok, buffer = cv2.imencode(".png", image)
    if not ok:
        raise RuntimeError(f"Failed to encode {path}")
    buffer.tofile(str(path))


def read_url_image(url: str) -> np.ndarray:
    request = urllib.request.Request(
        url,
        headers={"User-Agent": "Mozilla/5.0 image-processing-test-sample-generator"},
    )
    with urllib.request.urlopen(request, timeout=45) as response:
        data = np.frombuffer(response.read(), np.uint8)
    image = cv2.imdecode(data, cv2.IMREAD_COLOR)
    if image is None:
        raise RuntimeError(f"Failed to decode {url}")
    return image


def fit_for_preview(image: np.ndarray, max_side: int = 760) -> np.ndarray:
    h, w = image.shape[:2]
    scale = min(1.0, max_side / max(h, w))
    if scale == 1.0:
        return image
    return cv2.resize(image, (int(w * scale), int(h * scale)), interpolation=cv2.INTER_AREA)


def labeled(image: np.ndarray, title: str) -> np.ndarray:
    panel = image.copy()
    cv2.rectangle(panel, (0, 0), (panel.shape[1], 44), (255, 255, 255), -1)
    cv2.putText(panel, title, (12, 31), cv2.FONT_HERSHEY_SIMPLEX, 0.78, (0, 80, 220), 2, cv2.LINE_AA)
    return panel


def main() -> None:
    out_dir = ROOT / "test_img" / "wiener_web_samples"
    out_dir.mkdir(parents=True, exist_ok=True)

    metadata = []
    for index, (name, url, description, length, angle) in enumerate(SOURCES, start=1):
        print(f"Downloading {name}...")
        original = fit_for_preview(read_url_image(url))
        blurred = cv2.filter2D(original, -1, _motion_psf(length, angle), borderType=cv2.BORDER_REPLICATE)
        restored, params = auto_wiener_motion_deblur(blurred)

        prefix = f"{index:02d}_{name}"
        save_png(out_dir / f"{prefix}_original.png", original)
        save_png(out_dir / f"{prefix}_motion_blur.png", blurred)
        save_png(out_dir / f"{prefix}_restored.png", restored)

        panels = [
            labeled(original, "Original"),
            labeled(blurred, "Motion blur"),
            labeled(restored, "Auto restored"),
        ]
        min_h = min(panel.shape[0] for panel in panels)
        panels = [
            cv2.resize(panel, (int(panel.shape[1] * min_h / panel.shape[0]), min_h), interpolation=cv2.INTER_AREA)
            for panel in panels
        ]
        save_png(out_dir / f"{prefix}_comparison.png", cv2.hconcat(panels))

        metadata.append(
            {
                "name": name,
                "description": description,
                "source": url,
                "simulated_blur": {"length": length, "angle": angle},
                "auto_params": params,
            }
        )

    (out_dir / "sources.json").write_text(json.dumps(metadata, ensure_ascii=False, indent=2), encoding="utf-8")
    (out_dir / "README.txt").write_text(
        "\n".join(f"{item['name']}: {item['source']}" for item in metadata),
        encoding="utf-8",
    )

    print(f"Done: {out_dir}")
    for path in sorted(out_dir.iterdir()):
        print(path.name)


if __name__ == "__main__":
    main()
