"""SQLite база данных с миграциями, индексами и FTS5.

Паттерны портированы из app/db.py:
- Лёгкие миграции (ALTER TABLE ADD COLUMN с проверкой)
- FTS5 для полнотекстового поиска (BM25)
- Индексы для производительности
- WAL mode для конкурентного доступа
"""
import sqlite3
import logging
from pathlib import Path
from .config import DB_PATH, DATA_DIR, VIDEO_DIR, CLIPS_DIR, CHROMA_DIR

logger = logging.getLogger("standalone.db")


def ensure_dirs():
    for d in (DATA_DIR, VIDEO_DIR, CLIPS_DIR, CHROMA_DIR):
        d.mkdir(parents=True, exist_ok=True)


def get_db() -> sqlite3.Connection:
    conn = sqlite3.connect(str(DB_PATH))
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA journal_mode=WAL")
    conn.execute("PRAGMA synchronous=NORMAL")  # Быстрее WAL
    conn.execute("PRAGMA cache_size=-64000")    # 64MB cache
    conn.execute("PRAGMA busy_timeout=5000")    # 5с ожидание при блокировке
    return conn


def _get_columns(conn: sqlite3.Connection, table: str) -> set:
    """Получить список колонок таблицы."""
    rows = conn.execute(f"PRAGMA table_info({table})").fetchall()
    return {r["name"] for r in rows}


def _migrate(conn: sqlite3.Connection):
    """Лёгкие миграции — добавляем колонки если отсутствуют."""

    # --- videos ---
    cols = _get_columns(conn, "videos")

    migrations = {
        "tags": "ALTER TABLE videos ADD COLUMN tags TEXT",
        "channel_name": "ALTER TABLE videos ADD COLUMN channel_name TEXT",
        "duration": "ALTER TABLE videos ADD COLUMN duration INTEGER",
        "thumbnail_url": "ALTER TABLE videos ADD COLUMN thumbnail_url TEXT",
    }
    for col, sql in migrations.items():
        if col not in cols:
            conn.execute(sql)
            logger.info("✅ Добавлена колонка videos.%s", col)

    # --- segments ---
    seg_cols = _get_columns(conn, "segments")

    if "speaker" not in seg_cols:
        conn.execute("ALTER TABLE segments ADD COLUMN speaker TEXT")
        logger.info("✅ Добавлена колонка segments.speaker")

    # Сброс зависших processing → pending
    conn.execute("UPDATE videos SET status='added' WHERE status='processing'")
    conn.commit()


def _create_indexes(conn: sqlite3.Connection):
    """Создаём индексы для производительности."""
    indexes = [
        ("idx_seg_video", "segments", "video_id"),
        ("idx_seg_start", "segments", "start_sec"),
        ("idx_clip_video", "clips", "video_id"),
        ("idx_clip_created", "clips", "created_at DESC"),
        ("idx_video_status", "videos", "status"),
        ("idx_video_created", "videos", "created_at DESC"),
    ]
    for name, table, col in indexes:
        conn.execute(f"CREATE INDEX IF NOT EXISTS {name} ON {table}({col})")
    conn.commit()


def _create_fts(conn: sqlite3.Connection):
    """FTS5 таблица для полнотекстового поиска (BM25).
    
    Если таблица уже существует как contentless (content=''),
    пересоздаём — иначе SELECT возвращает пустые значения.
    """
    # Проверяем, нужно ли пересоздать (старая content='' не хранит данные)
    try:
        test = conn.execute("SELECT segment_id, text FROM segments_fts LIMIT 1").fetchone()
        if test and not test["segment_id"] and not test["text"]:
            # Contentless таблица — пересоздаём
            logger.warning("FTS5 таблица contentless — пересоздаём с хранением данных")
            conn.execute("DROP TABLE IF EXISTS segments_fts")
    except Exception:
        pass  # Таблица не существует — создадим ниже

    conn.executescript("""
        CREATE VIRTUAL TABLE IF NOT EXISTS segments_fts USING fts5(
            segment_id UNINDEXED,
            video_id UNINDEXED,
            text,
            tokenize='unicode61'
        );
    """)
    logger.info("FTS5 таблица ready")


def init_db():
    """Инициализация БД: таблицы + миграции + индексы + FTS5."""
    ensure_dirs()
    conn = get_db()

    # Основные таблицы
    conn.executescript("""
        CREATE TABLE IF NOT EXISTS videos (
            video_id   TEXT PRIMARY KEY,
            title      TEXT NOT NULL,
            local_path TEXT,
            status     TEXT DEFAULT 'added',
            created_at TEXT DEFAULT (datetime('now'))
        );
        CREATE TABLE IF NOT EXISTS segments (
            segment_id TEXT PRIMARY KEY,
            video_id   TEXT NOT NULL,
            start_sec  REAL NOT NULL,
            end_sec    REAL NOT NULL,
            text       TEXT NOT NULL,
            words_json TEXT,
            FOREIGN KEY (video_id) REFERENCES videos(video_id)
        );
        CREATE TABLE IF NOT EXISTS clips (
            clip_id    TEXT PRIMARY KEY,
            video_id   TEXT NOT NULL,
            start_sec  REAL NOT NULL,
            end_sec    REAL NOT NULL,
            path       TEXT NOT NULL,
            created_at TEXT DEFAULT (datetime('now')),
            FOREIGN KEY (video_id) REFERENCES videos(video_id)
        );
    """)

    # Миграции, индексы, FTS
    _migrate(conn)
    _create_indexes(conn)
    _create_fts(conn)

    conn.close()
    logger.info("DB ready: %s", DB_PATH)


def upsert_fts(conn: sqlite3.Connection, segment_id: str, video_id: str, text: str):
    """Вставить или обновить запись в FTS5."""
    conn.execute("DELETE FROM segments_fts WHERE segment_id = ?", (segment_id,))
    conn.execute(
        "INSERT INTO segments_fts (segment_id, video_id, text) VALUES (?, ?, ?)",
        (segment_id, video_id, text),
    )


def fts_search(query: str, top_k: int = 20) -> list:
    """BM25 поиск через FTS5. Возвращает [(segment_id, video_id, text, rank)]."""
    if not query.strip():
        return []

    conn = get_db()
    try:
        rows = conn.execute(
            """
            SELECT segment_id, video_id, text, bm25(segments_fts) AS rank
            FROM segments_fts
            WHERE segments_fts MATCH ?
            ORDER BY rank
            LIMIT ?
            """,
            (query, top_k),
        ).fetchall()
        results = [dict(r) for r in rows]
        # Фильтруем пустые результаты (защита)
        return [r for r in results if r.get("segment_id") and r.get("text")]
    except Exception as e:
        logger.warning("FTS5 ошибка: %s", e)
        return []
    finally:
        conn.close()
