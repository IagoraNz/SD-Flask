import os
import uuid
import json
from pathlib import Path
from datetime import datetime, timezone
from flask import (
    Flask, request, jsonify, send_from_directory,
    abort, render_template_string, redirect, url_for,
    render_template, flash
)
from dotenv import load_dotenv
import cv2
import tempfile

from db import init_db, insert_video, list_videos, get_video, delete_video_db
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


def save_original_video_properly(uploaded_file, original_path: Path):
    """
    Salva o vídeo original garantindo que não seja corrompido.
    Usa OpenCV para reescrever o vídeo com codec compatível.
    """
    print(f"Salvando vídeo original: {original_path}")
    
    # Primeiro salva temporariamente o arquivo uploadado
    with tempfile.NamedTemporaryFile(suffix='.tmp', delete=False) as temp_file:
        temp_path = Path(temp_file.name)
        uploaded_file.save(temp_path)
        uploaded_file.seek(0)  # Reset para caso seja usado novamente
    
    try:
        # Abre o arquivo temporário com OpenCV
        cap = cv2.VideoCapture(str(temp_path))
        if not cap.isOpened():
            print("Falha ao abrir vídeo temporário, salvando diretamente...")
            # Fallback: salva diretamente
            uploaded_file.save(original_path)
            return
        
        # Obter propriedades
        fps = cap.get(cv2.CAP_PROP_FPS) or 25.0
        width = int(cap.get(cv2.CAP_PROP_FRAME_WIDTH))
        height = int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT))
        
        print(f"Propriedades do original: {width}x{height}, {fps} FPS")
        
        # Se não conseguir obter dimensões, usa fallback
        if width <= 0 or height <= 0:
            ret, test_frame = cap.read()
            if ret:
                height, width = test_frame.shape[:2]
                cap.set(cv2.CAP_PROP_POS_FRAMES, 0)
            else:
                print("Não foi possível ler frame, usando fallback...")
                cap.release()
                uploaded_file.save(original_path)
                return
        
        # Garantir dimensões pares
        width = width + (width % 2)
        height = height + (height % 2)
        
        # Usar codec compatível para o original
        fourcc = cv2.VideoWriter_fourcc(*'avc1')  # H.264
        
        original_path.parent.mkdir(parents=True, exist_ok=True)
        out = cv2.VideoWriter(str(original_path), fourcc, fps, (width, height))
        
        # Se falhar, tenta MJPG
        if not out.isOpened():
            print("Falha com avc1, tentando MJPG...")
            fourcc = cv2.VideoWriter_fourcc(*'MJPG')
            out = cv2.VideoWriter(str(original_path), fourcc, fps, (width, height))
            
            # Se ainda falhar, usa fallback
            if not out.isOpened():
                print("Falha com todos os codecs, usando fallback...")
                cap.release()
                uploaded_file.save(original_path)
                return
        
        # Copia todos os frames
        frame_count = 0
        while True:
            ret, frame = cap.read()
            if not ret:
                break
            
            # Redimensionar se necessário
            if frame.shape[:2] != (height, width):
                frame = cv2.resize(frame, (width, height))
            
            out.write(frame)
            frame_count += 1
        
        cap.release()
        out.release()
        
        print(f"Vídeo original salvo com {frame_count} frames")
        
        # Verificar se foi criado corretamente
        if not original_path.exists() or original_path.stat().st_size == 0:
            print("Falha na reescrita, usando fallback...")
            uploaded_file.save(original_path)
    
    except Exception as e:
        print(f"Erro ao processar original: {e}, usando fallback...")
        # Em caso de erro, salva diretamente
        uploaded_file.save(original_path)
    
    finally:
        # Remove arquivo temporário
        if temp_path.exists():
            temp_path.unlink()


def generate_thumbnail(video_path: Path, thumb_path: Path):
    cap = cv2.VideoCapture(str(video_path))
    ret, frame = cap.read()
    if ret:
        cv2.imwrite(str(thumb_path), frame)
    cap.release()


def save_meta_json(meta_path: Path, data: dict):
    with open(meta_path, "w") as f:
        json.dump(data, f, indent=4)


def move_video_to_trash(video_id):
    """
    Move o vídeo para a pasta trash baseado no video_id.
    Procura pela estrutura: videos/Y/M/D/video_id/
    """
    video = get_video(video_id)
    if not video:
        print("Vídeo não encontrado no banco de dados.")
        return False

    # Procura pelo diretório do vídeo na estrutura videos/Y/M/D/video_id
    video_base_path = None
    
    # Primeiro tenta usar o path_original se estiver disponível
    if "path_original" in video:
        original_path = Path(video["path_original"])
        # O path original é: videos/Y/M/D/video_id/original/video.ext
        # Então o base_path é 2 níveis acima
        potential_base = original_path.parent.parent
        if potential_base.name == video_id and potential_base.exists():
            video_base_path = potential_base
    
    # Se não encontrou pelo path_original, procura manualmente
    if video_base_path is None:
        print(f"Procurando diretório para video_id: {video_id}")
        # Procura em todos os subdiretórios de videos/
        for year_dir in VIDEOS.iterdir():
            if not year_dir.is_dir():
                continue
            for month_dir in year_dir.iterdir():
                if not month_dir.is_dir():
                    continue
                for day_dir in month_dir.iterdir():
                    if not day_dir.is_dir():
                        continue
                    video_dir = day_dir / video_id
                    if video_dir.exists() and video_dir.is_dir():
                        video_base_path = video_dir
                        break
                if video_base_path:
                    break
            if video_base_path:
                break
    
    if video_base_path is None:
        print(f"Diretório do vídeo {video_id} não encontrado")
        return False
    
    print(f"Encontrado diretório do vídeo: {video_base_path}")
    
    try:
        # Move para a pasta trash
        trash_path = TRASH / video_id
        
        # Se já existe na trash, remove primeiro
        if trash_path.exists():
            import shutil
            shutil.rmtree(trash_path)
        
        # Garante que o diretório pai da trash existe
        trash_path.parent.mkdir(parents=True, exist_ok=True)
        
        # Move o diretório inteiro
        video_base_path.rename(trash_path)
        print(f"Vídeo movido para trash: {trash_path}")
        return True
        
    except Exception as e:
        print(f"Erro ao mover vídeo para trash: {e}")
        return False

# =====================================
# Routes
# =====================================

@app.route("/upload", methods=["POST"])
def upload_video():
    file = request.files.get("video")
    filter_name = request.form.get("filter", "gray")

    if not file:
        return jsonify({"error": "Nenhum arquivo enviado"}), 400

    ext = safe_ext(file.filename)
    if not ext:
        return jsonify({"error": "Extensão não suportada"}), 400

    video_id = str(uuid.uuid4().hex)
    paths = build_paths(video_id, ext, filter_name)

    print(f"Iniciando upload do vídeo {video_id} com filtro {filter_name}")

    try:
        # Salva o original de forma segura
        save_original_video_properly(file, paths["original"])
        
        # Verifica se o original foi salvo
        if not paths["original"].exists():
            return jsonify({"error": "Falha ao salvar vídeo original"}), 500
        
        print(f"Original salvo: {paths['original']} ({paths['original'].stat().st_size} bytes)")

        # Processa vídeo (aplicando filtro)
        processing_result = process_video(
            paths["original"],
            paths["processed"],
            filter_name,
            paths["thumb_jpg"],
            paths["preview_gif"]
        )
        
        print(f"Vídeo processado: {paths['processed']} ({paths['processed'].stat().st_size} bytes)")

        # Metadados
        meta = {
            "id": video_id,
            "original_name": file.filename,
            "ext": ext,
            "filter": filter_name,
            "created_at": datetime.now(timezone.utc).isoformat(),
            "path_original": str(paths["original"]),
            "path_processed": str(paths["processed"]),
            "urls": public_urls(video_id, ext, filter_name),
            **processing_result  # Adiciona fps, width, height, etc.
        }

        save_meta_json(paths["meta_json"], meta)
        insert_video(meta)

        print(f"Upload concluído com sucesso: {video_id}")
        return jsonify(meta), 200
    
    except Exception as e:
        print(f"Erro durante upload: {e}")
        return jsonify({"error": f"Erro ao processar vídeo: {str(e)}"}), 500


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

@app.route("/delete_video/<video_id>", methods=["POST"])
def delete_video(video_id):
    try:
        print(f"Tentando deletar vídeo: {video_id}")
        
        # Verifica se o vídeo existe no banco
        video = get_video(video_id)
        if not video:
            print(f"Vídeo {video_id} não encontrado no banco de dados")
            return jsonify({"success": False, "error": "Vídeo não encontrado"}), 404
        
        # Tenta mover para trash
        success = move_video_to_trash(video_id)
        
        if success:
            # Remove do banco de dados apenas se moveu com sucesso
            delete_video_db(video_id)
            print(f"Vídeo {video_id} deletado com sucesso")
            return jsonify({"success": True, "message": "Vídeo deletado com sucesso"}), 200
        else:
            print(f"Falha ao mover vídeo {video_id} para trash")
            return jsonify({"success": False, "error": "Não foi possível mover para trash"}), 500
            
    except Exception as e:
        print(f"Erro inesperado ao deletar vídeo {video_id}: {e}")
        return jsonify({"success": False, "error": f"Erro interno: {str(e)}"}), 500
@app.route("/gallery", methods=["GET"])
def gallery():
    videos = list_videos()
    html = """
    <html>
    <head>
        <title>Galeria</title>
        <script>
        function deleteVideo(videoId, btn) {
            if (!confirm('Tem certeza que deseja apagar este vídeo?')) return;
            fetch('/delete_video/' + videoId, {method: 'POST'})
                .then(resp => resp.json())
                .then(data => {
                    if (data.success) {
                        btn.closest('li').remove();
                    } else {
                        alert('Erro ao apagar: ' + (data.error || ''));
                    }
                });
        }
        </script>
    </head>
    <body>
        <h1>Galeria</h1>
        <ul>
        {% for v in videos %}
            <li>
                <img src="{{v['urls']['thumb']}}" width="160"><br>
                <a href="{{v['urls']['view']}}">Ver vídeo {{v['id']}}</a><br>
                <button onclick="deleteVideo('{{v['id']}}', this)">Apagar</button>
            </li>
        {% endfor %}
        </ul>
    </body>
    </html>
    """
    return render_template_string(html, videos=videos)
    
@app.route("/", methods=["GET"])
def index():
    videos = list_videos()
    return render_template('index.html', videos=videos)

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