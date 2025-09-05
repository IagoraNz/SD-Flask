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

def get_best_codec():
    """Retorna o melhor codec disponível no sistema"""
    # Tenta diferentes codecs em ordem de preferência
    codecs = [
        ('avc1', cv2.VideoWriter_fourcc(*'avc1')),  # H.264 (melhor compatibilidade)
        ('mp4v', cv2.VideoWriter_fourcc(*'mp4v')),  # MPEG-4
        ('XVID', cv2.VideoWriter_fourcc(*'XVID')),  # Xvid
        ('MJPG', cv2.VideoWriter_fourcc(*'MJPG')),  # Motion JPEG (fallback)
    ]
    
    # Para teste rápido, vamos usar sempre avc1/H.264 primeiro
    return codecs[0][1], codecs[0][0]

def process_video(src_path: Path, dst_path: Path, filter_name: str, thumb_jpg: Path, preview_gif: Path | None = None):
    if filter_name not in FILTERS:
        raise ValueError(f"Filtro inválido: {filter_name}")

    print(f"Processando: {src_path} -> {dst_path}")
    
    cap = cv2.VideoCapture(str(src_path))
    if not cap.isOpened():
        raise RuntimeError("Não foi possível abrir o vídeo de entrada")

    # Obter propriedades do vídeo original
    fps = cap.get(cv2.CAP_PROP_FPS)
    width = int(cap.get(cv2.CAP_PROP_FRAME_WIDTH))
    height = int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT))
    frame_count = int(cap.get(cv2.CAP_PROP_FRAME_COUNT))
    
    # Validar propriedades
    if fps <= 0:
        fps = 25.0
    
    if width <= 0 or height <= 0:
        ret, test_frame = cap.read()
        if ret:
            height, width = test_frame.shape[:2]
            cap.set(cv2.CAP_PROP_POS_FRAMES, 0)  # Volta ao início
        else:
            raise RuntimeError("Não foi possível determinar dimensões do vídeo")
    
    # Garantir que dimensões são pares (necessário para alguns codecs)
    width = width + (width % 2)
    height = height + (height % 2)
    
    # Tentar diferentes codecs
    fourcc, codec_name = get_best_codec()
    
    dst_path.parent.mkdir(parents=True, exist_ok=True)
    
    # Tentar criar o VideoWriter
    out = cv2.VideoWriter(str(dst_path), fourcc, fps, (width, height))
    
    if not out.isOpened():
        # Fallback: tentar com MJPG
        fourcc = cv2.VideoWriter_fourcc(*'MJPG')
        out = cv2.VideoWriter(str(dst_path), fourcc, fps, (width, height))
        
        if not out.isOpened():
            raise RuntimeError("Não foi possível criar o vídeo de saída com nenhum codec")

    filter_fn = FILTERS[filter_name]

    # Para GIF de preview
    frames_for_gif = []
    sample_every = max(int(fps // 2), 1)  # ~2 fps no GIF

    i = 0
    saved_thumb = False
    processed_frames = 0
    
    # Mostrar progresso apenas a cada 10% do total
    progress_step = max(frame_count // 10, 30)
    
    while True:
        ret, frame = cap.read()
        if not ret:
            break
        
        # Garantir que frame tem as dimensões corretas
        if frame.shape[:2] != (height, width):
            frame = cv2.resize(frame, (width, height))
        
        # Aplicar filtro
        try:
            processed = filter_fn(frame)
            
            # Garantir que processed tem as dimensões corretas
            if processed.shape[:2] != (height, width):
                processed = cv2.resize(processed, (width, height))
            
            # Escrever frame
            out.write(processed)
            processed_frames += 1
            
            # Salvar thumbnail do primeiro frame processado
            if not saved_thumb:
                cv2.imwrite(str(thumb_jpg), processed)
                saved_thumb = True
            
            # Coletar frames para GIF
            if preview_gif is not None and (i % sample_every == 0) and len(frames_for_gif) < 60:
                frames_for_gif.append(cv2.cvtColor(processed, cv2.COLOR_BGR2RGB))
            
        except Exception as e:
            print(f"Erro ao processar frame {i}: {e}")
            break
        
        i += 1
        
        # Log de progresso apenas ocasionalmente
        if frame_count > 0 and i % progress_step == 0:
            progress = (i / frame_count) * 100
            print(f"Progresso: {progress:.1f}% ({i}/{frame_count} frames)")

    cap.release()
    out.release()
    
    print(f"Processamento concluído: {processed_frames} frames processados")

    # Verificar se o arquivo foi criado
    if not (dst_path.exists() and dst_path.stat().st_size > 0):
        raise RuntimeError("Vídeo não foi criado corretamente!")

    # Gerar GIF (opcional)
    if preview_gif is not None and frames_for_gif:
        try:
            import imageio
            preview_gif.parent.mkdir(parents=True, exist_ok=True)
            imageio.mimsave(str(preview_gif), frames_for_gif, duration=0.5)
        except Exception as e:
            print(f"Erro ao criar GIF: {e}")

    return {
        'fps': float(fps),
        'width': int(width),
        'height': int(height),
        'frame_count': int(frame_count),
        'processed_frames': processed_frames
    }