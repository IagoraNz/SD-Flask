import hashlib
from datetime import datetime
import mimetypes
from pathlib import Path

ALLOWED_EXTENSIONS = {'.mp4', '.avi', '.mov', '.mkv'}

def now_parts():
    dt = datetime.utcnow()
    return dt, dt.strftime('%Y'), dt.strftime('%m'), dt.strftime('%d')

def safe_ext(filename: str) -> str:
    ext = Path(filename).suffix.lower()
    return ext if ext in ALLOWED_EXTENSIONS else '.mp4'

def sha256sum(path: Path, bufsize: int = 1 << 20) -> str:
    h = hashlib.sha256()
    with path.open('rb') as f:
        while True:
            b = f.read(bufsize)
            if not b:
                break
            h.update(b)
    return h.hexdigest()

def guess_mime(path: Path) -> str:
    mt, _ = mimetypes.guess_type(str(path))
    return mt or 'application/octet-stream'