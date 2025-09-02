from pathlib import Path
import cv2
import numpy as np

def apply_grayscale(frame: np.ndarray) -> np.ndarray:
    gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
    return cv2.cvtColor(gray, cv2.COLOR_GRAY2BGR)

def apply_pixelate(frame: np.ndarray, block_size: int = 16) -> np.ndarray:
    height, width = frame.shape[:2]
    small = cv2.resize(frame, (width // block_size, height // block_size))
    return cv2.resize(small, (width, height), interpolation=cv2.INTER_NEAREST)

def apply_edges(frame: np.ndarray) -> np.ndarray:
    gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
    edges = cv2.Canny(gray, 100, 200)
    return cv2.cvtColor(edges, cv2.COLOR_GRAY2BGR)

FILTERS = {
    'grayscale': apply_grayscale,
    'gray': apply_grayscale,
    'pixelate': apply_pixelate,
    'edges': apply_edges,
}

def process_video(src_path: Path, dst_path: Path, filter_name: str, thumb_jpg: Path, preview_gif: Path | None = None):
    if filter_name not in FILTERS:
        raise ValueError(f"Filtro inválido: {filter_name}")

    cap = cv2.VideoCapture(str(src_path))
    if not cap.isOpened():
        raise RuntimeError("Não foi possível abrir o vídeo de entrada")

    fps = cap.get(cv2.CAP_PROP_FPS) or 25.0
    width = int(cap.get(cv2.CAP_PROP_FRAME_WIDTH) or 640)
    height = int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT) or 480)
    fourcc = cv2.VideoWriter_fourcc(*'mp4v')

    dst_path.parent.mkdir(parents=True, exist_ok=True)
    out = cv2.VideoWriter(str(dst_path), fourcc, fps, (width, height))

    frame_count = int(cap.get(cv2.CAP_PROP_FRAME_COUNT) or 0)
    filter_fn = FILTERS[filter_name]

    # Para GIF de preview
    frames_for_gif = []
    sample_every = max(int(fps // 2), 1) # ~2 fps no GIF

    i = 0
    saved_thumb = False
    while True:
        ok, frame = cap.read()
        if not ok:
            break
        processed = filter_fn(frame)
        out.write(processed)

        if not saved_thumb:
            cv2.imwrite(str(thumb_jpg), processed)
            saved_thumb = True

        if preview_gif is not None and (i % sample_every == 0) and len(frames_for_gif) < 60:
            frames_for_gif.append(cv2.cvtColor(processed, cv2.COLOR_BGR2RGB))
        i += 1

    cap.release()
    out.release()

    # Gera GIF (opcional)
    if preview_gif is not None and frames_for_gif:
        try:
            import imageio
            imageio.mimsave(preview_gif, frames_for_gif, duration=0.5)
        except Exception:
            pass # se não tiver imageio ou falhar, apenas ignore


    return {
        'fps': float(fps),
        'width': int(width),
        'height': int(height),
        'frame_count': int(frame_count)
    }