import sqlite3
import json
from pathlib import Path

DB_PATH = Path(__file__).parent / 'videos.db'

def get_conn():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn

def init_db():
    with get_conn() as conn:
        conn.execute(
            '''CREATE TABLE IF NOT EXISTS videos (
                id TEXT PRIMARY KEY,
                original_name TEXT,
                ext TEXT,
                mime_type TEXT,
                size_bytes INTEGER,
                duration_sec REAL,
                fps REAL,
                width INTEGER,
                height INTEGER,
                filter TEXT,
                created_at TEXT,
                path_original TEXT,
                path_processed TEXT,
                urls TEXT
            );'''
        )

def insert_video(meta):
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    
    # garante que urls seja string JSON
    urls_json = json.dumps(meta["urls"]) if isinstance(meta["urls"], dict) else meta["urls"]

    c.execute("""
        INSERT INTO videos (
            id, original_name, ext, mime_type, size_bytes, duration_sec,
            fps, width, height, filter, created_at, path_original, path_processed, urls
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
    """, (
        meta.get("id"),
        meta.get("original_name"),
        meta.get("ext"),
        meta.get("mime_type"),
        meta.get("size_bytes"),
        meta.get("duration_sec"),
        meta.get("fps"),
        meta.get("width"),
        meta.get("height"),
        meta.get("filter"),
        meta.get("created_at"),
        meta.get("path_original"),
        meta.get("path_processed"),
        urls_json   # 👈 aqui sempre vai JSON válido
    ))
    
    conn.commit()
    conn.close()

def list_videos(limit=100):
    with get_conn() as conn:
        cur = conn.execute('SELECT * FROM videos ORDER BY created_at DESC LIMIT ?', (limit,))
        rows = [dict(r) for r in cur.fetchall()]

    for r in rows:
        # tenta carregar urls como JSON
        try:
            r["urls"] = json.loads(r["urls"]) if r.get("urls") else {}
        except Exception:
            r["urls"] = {}

        # garante todas as chaves
        for k in ["view", "original", "processed", "thumb", "gif"]:
            r["urls"].setdefault(k, "")

    return rows


def get_video(video_id: str):
    with get_conn() as conn:
        cur = conn.execute('SELECT * FROM videos WHERE id = ? LIMIT 1', (video_id,))
        row = cur.fetchone()

    if not row:
        return None

    r = dict(row)

    # tenta carregar urls como JSON
    try:
        r["urls"] = json.loads(r["urls"]) if r.get("urls") else {}
    except Exception:
        r["urls"] = {}

    # garante todas as chaves
    for k in ["view", "original", "processed", "thumb", "gif"]:
        r["urls"].setdefault(k, "")

    return r