import os
import uuid
import json
from pathlib import Path
from datetime import datetime, timezone
from flask import (
    Flask, request, jsonify, send_from_directory,
    abort, render_template_string, redirect, url_for
)
from dotenv import load_dotenv
import cv2

from db import init_db, insert_video, list_videos, get_video
from processing import process_video
from utils import now_parts, safe_ext, sha256sum, guess_mime

load_dotenv()

MEDIA_ROOT = Path(os.getenv('MEDIA_ROOT', './media')).resolve()
HOST = os.getenv('HOST', '0.0.0.0')
PORT = int(os.getenv('PORT', '5000'))
DEBUG = bool(int(os.getenv('DEBUG', '1')))

INCOMING = MEDIA_ROOT / 'incoming'
TRASH = MEDIA_ROOT / 'trash'
VIDEOS = MEDIA_ROOT / 'videos'

for p in (MEDIA_ROOT, INCOMING, TRASH, VIDEOS):
    p.mkdir(parents=True, exist_ok=True)

app = Flask(__name__)
init_db()


# =====================================
# Helpers
# =====================================

def build_paths(video_id: str, ext: str, filter_name: str):
    dt, y, m, d = now_parts()
    base = VIDEOS / y / m / d / video_id
    original_dir = base / 'original'
    processed_dir = base / 'processed' / filter_name
    thumbs_dir = base / 'thumbs'
    original_dir.mkdir(parents=True, exist_ok=True)
    processed_dir.mkdir(parents=True, exist_ok=True)
    thumbs_dir.mkdir(parents=True, exist_ok=True)
    return {
        'base': base,
        'original': original_dir / f'video{ext}',
        'processed': processed_dir / f'video{ext}',
        'thumb_jpg': thumbs_dir / 'frame_0001.jpg',
        'preview_gif': thumbs_dir / 'preview.gif',
        'meta_json': base / 'meta.json',
    }


def public_urls(video_id: str, ext: str, filter_name: str):
    return {
        'view': url_for('view_video', video_id=video_id, _external=True),
        'original': url_for(
            'serve_media',
            subpath=f'videos/*/*/*/{video_id}/original/video{ext}',
            _external=True
        ),
        'processed': url_for(
            'serve_media',
            subpath=f'videos/*/*/*/{video_id}/processed/{filter_name}/video{ext}',
            _external=True
        ),
        'thumb': url_for(
            'serve_media',
            subpath=f'videos/*/*/*/{video_id}/thumbs/frame_0001.jpg',
            _external=True
        ),
        'gif': url_for(
            'serve_media',
            subpath=f'videos/*/*/*/{video_id}/thumbs/preview.gif',
            _external=True
        ),
    }


def generate_thumbnail(video_path: Path, thumb_path: Path):
    cap = cv2.VideoCapture(str(video_path))
    ret, frame = cap.read()
    if ret:
        cv2.imwrite(str(thumb_path), frame)
    cap.release()


def save_meta_json(meta_path: Path, data: dict):
    with open(meta_path, "w") as f:
        json.dump(data, f, indent=4)


# =====================================
# Routes
# =====================================

@app.route("/upload", methods=["POST"])
def upload_video():
    file = request.files.get("video")  # trocar de "file" para "video"
    filter_name = request.form.get("filter", "gray")

    if not file:
        return jsonify({"error": "Nenhum arquivo enviado"}), 400

    ext = safe_ext(file.filename)
    if not ext:
        return jsonify({"error": "Extensão não suportada"}), 400

    video_id = str(uuid.uuid4().hex)
    paths = build_paths(video_id, ext, filter_name)

    # Salva original
    file.save(paths["original"])

    # Processa vídeo
    process_video(
        paths["original"],
        paths["processed"],
        filter_name,
        paths["thumb_jpg"],
        paths["preview_gif"]
    )

    # Gera thumb
    generate_thumbnail(paths["processed"], paths["thumb_jpg"])

    # Metadados
    meta = {
        "id": video_id,
        "original_name": file.filename,
        "ext": ext,
        "filter": filter_name,
        "created_at": datetime.now(timezone.utc).isoformat(),
        "path_original": str(paths["original"]),
        "path_processed": str(paths["processed"]),
        "urls": public_urls(video_id, ext, filter_name)  # ✅ já dict
    }

    save_meta_json(paths["meta_json"], meta)
    insert_video(meta)

    return jsonify(meta), 200

@app.route("/videos", methods=["GET"])
def api_list_videos():
    videos = list_videos()
    # garante compatibilidade com o client Tkinter
    for v in videos:
        u = v.get("urls") or {}
        v["original"]  = u.get("original", "")
        v["processed"] = u.get("processed", "")
        v["thumb"]     = u.get("thumb", "")
        v["view"]      = u.get("view", "")
        v["gif"]       = u.get("gif", "")
    return jsonify(videos)

@app.route("/video/<video_id>", methods=["GET"])
def view_video(video_id):
    video = get_video(video_id)
    if not video:
        abort(404)

    html = """
    <html>
    <head><title>Vídeo {{v['id']}}</title></head>
    <body>
        <h1>Vídeo {{v['id']}}</h1>
        <video width="480" controls>
            <source src="{{v['urls']['processed']}}" type="video/mp4">
        </video>
        <p>Filtro: {{v['filter']}}</p>
        <p>Criado em: {{v['created_at']}}</p>
        <p><a href="{{url_for('gallery')}}">← Voltar para galeria</a></p>
    </body>
    </html>
    """
    return render_template_string(html, v=video)

@app.route("/gallery", methods=["GET"])
def gallery():
    videos = list_videos()
    html = """
    <html>
    <head><title>Galeria</title></head>
    <body>
        <h1>Galeria</h1>
        <ul>
        {% for v in videos %}
            <li>
                <img src="{{v['urls']['thumb']}}" width="160"><br>
                <a href="{{v['urls']['view']}}">Ver vídeo {{v['id']}}</a>
            </li>
        {% endfor %}
        </ul>
    </body>
    </html>
    """
    return render_template_string(html, videos=videos)

@app.route("/media/<path:subpath>")
def serve_media(subpath):
    # Resolve padrões com * nos caminhos gerados por public_urls(...)
    if "*" in subpath:
        matches = list((MEDIA_ROOT).glob(subpath))
        if not matches:
            abort(404)
        full_path = matches[0]
    else:
        full_path = MEDIA_ROOT / subpath

    if not full_path.exists():
        abort(404)
    return send_from_directory(full_path.parent, full_path.name)


# =====================================
# Entrypoint
# =====================================

if __name__ == "__main__":
    app.run(host=HOST, port=PORT, debug=DEBUG)