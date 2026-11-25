"""SQLite 저장소: 옷장(clothes)과 할 일(todos).

복잡한 ORM 대신 표준 라이브러리 sqlite3만 사용해서 코드가 한눈에 보이게 했습니다.
"""
import sqlite3
from contextlib import contextmanager

from .config import settings

WARDROBE_DIR = settings.data_dir / "wardrobe"
DB_PATH = settings.data_dir / "mirror.db"


@contextmanager
def get_conn():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    try:
        yield conn
        conn.commit()
    finally:
        conn.close()


def init_db() -> None:
    WARDROBE_DIR.mkdir(parents=True, exist_ok=True)
    with get_conn() as conn:
        conn.executescript(
            """
            CREATE TABLE IF NOT EXISTS clothes (
                id         INTEGER PRIMARY KEY AUTOINCREMENT,
                name       TEXT    NOT NULL,
                category   TEXT    NOT NULL,           -- top | bottom | outer
                color      TEXT    NOT NULL,
                warmth     INTEGER NOT NULL,           -- 1(매우 얇음) ~ 5(매우 두꺼움)
                waterproof INTEGER NOT NULL DEFAULT 0, -- 방수 여부
                image      TEXT    NOT NULL,           -- 원본 사진 파일명
                cutout     TEXT,                       -- 배경 제거한 PNG 파일명
                created_at TEXT    NOT NULL DEFAULT CURRENT_TIMESTAMP
            );
            CREATE TABLE IF NOT EXISTS todos (
                id   INTEGER PRIMARY KEY AUTOINCREMENT,
                text TEXT    NOT NULL,
                done INTEGER NOT NULL DEFAULT 0
            );
            """
        )


# ── 옷장 ───────────────────────────────────────────
def _clothing_dict(row: sqlite3.Row) -> dict:
    d = dict(row)
    d["waterproof"] = bool(d["waterproof"])
    d["image_url"] = f"/data/wardrobe/{d['image']}"
    d["cutout_url"] = f"/data/wardrobe/{d['cutout']}" if d["cutout"] else d["image_url"]
    return d


def add_clothing(name, category, color, warmth, waterproof, image, cutout) -> int:
    with get_conn() as conn:
        cur = conn.execute(
            "INSERT INTO clothes (name, category, color, warmth, waterproof, image, cutout) "
            "VALUES (?, ?, ?, ?, ?, ?, ?)",
            (name, category, color, warmth, int(waterproof), image, cutout),
        )
        return cur.lastrowid


def list_clothes() -> list[dict]:
    with get_conn() as conn:
        rows = conn.execute("SELECT * FROM clothes ORDER BY id DESC").fetchall()
    return [_clothing_dict(r) for r in rows]


def get_clothing(clothing_id: int) -> dict | None:
    with get_conn() as conn:
        row = conn.execute("SELECT * FROM clothes WHERE id = ?", (clothing_id,)).fetchone()
    return _clothing_dict(row) if row else None


def delete_clothing(clothing_id: int) -> dict | None:
    """삭제하고, 파일 정리를 위해 삭제된 행을 돌려준다."""
    item = get_clothing(clothing_id)
    if item:
        with get_conn() as conn:
            conn.execute("DELETE FROM clothes WHERE id = ?", (clothing_id,))
    return item


# ── 할 일 ──────────────────────────────────────────
def list_todos() -> list[dict]:
    with get_conn() as conn:
        rows = conn.execute("SELECT * FROM todos ORDER BY done, id").fetchall()
    return [{**dict(r), "done": bool(r["done"])} for r in rows]


def add_todo(text: str) -> int:
    with get_conn() as conn:
        return conn.execute("INSERT INTO todos (text) VALUES (?)", (text,)).lastrowid


def toggle_todo(todo_id: int) -> None:
    with get_conn() as conn:
        conn.execute("UPDATE todos SET done = 1 - done WHERE id = ?", (todo_id,))


def delete_todo(todo_id: int) -> None:
    with get_conn() as conn:
        conn.execute("DELETE FROM todos WHERE id = ?", (todo_id,))
