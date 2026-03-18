import sqlite3
import os
from datetime import datetime
from typing import Optional, Dict, Any, List
from core.models import Song

class Database:
    def __init__(self, db_path: str = "data/radio.db"):
        self.db_path = db_path
        # Ensure the directory exists
        os.makedirs(os.path.dirname(self.db_path), exist_ok=True)
        self._init_db()

    def _init_db(self):
        """Initializes the database and creates tables if they don't exist."""
        with sqlite3.connect(self.db_path) as conn:
            conn.execute("PRAGMA journal_mode=WAL")
            cursor = conn.cursor()
            
            # 1. Song Metadata Cache
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS song_cache (
                    url TEXT PRIMARY KEY,
                    title TEXT,
                    uploader TEXT,
                    duration INTEGER,
                    thumbnail_url TEXT,
                    last_updated TIMESTAMP
                )
            """)
            
            # 2. Playback History (with user stats)
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS history (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    title TEXT,
                    path TEXT,
                    uploader TEXT,
                    duration INTEGER,
                    thumbnail_url TEXT,
                    is_external BOOLEAN,
                    requested_by TEXT,
                    user_id TEXT,
                    played_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
            """)

            # 3. User Settings (future features)
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS user_settings (
                    user_id TEXT PRIMARY KEY,
                    language TEXT,
                    volume FLOAT,
                    ui_mode TEXT
                )
            """)

            # 4. Global Stats
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS system_stats (
                    key TEXT PRIMARY KEY,
                    value INTEGER DEFAULT 0
                )
            """)
            
            # 5. User Favorites (Global)
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS favorites (
                    user_id TEXT,
                    path TEXT,
                    title TEXT,
                    uploader TEXT,
                    duration INTEGER,
                    thumbnail_url TEXT,
                    is_external BOOLEAN,
                    PRIMARY KEY (user_id, path)
                )
            """)
            
            conn.commit()

    # --- Cache Methods ---
    def get_cache(self, url: str) -> Optional[Dict[str, Any]]:
        try:
            with sqlite3.connect(self.db_path) as conn:
                conn.row_factory = sqlite3.Row
                cursor = conn.cursor()
                cursor.execute("SELECT * FROM song_cache WHERE url = ?", (url,))
                row = cursor.fetchone()
                if row:
                    data = dict(row)
                    data["duration"] = int(data["duration"])
                    return data
        except Exception as e:
            from logger import log
            log.debug(f"Cache get error: {e}")
        return None

    def set_cache(self, url: str, title: str, uploader: str, duration: int, thumbnail_url: str):
        try:
            with sqlite3.connect(self.db_path) as conn:
                cursor = conn.cursor()
                cursor.execute("""
                    INSERT OR REPLACE INTO song_cache 
                    (url, title, uploader, duration, thumbnail_url, last_updated)
                    VALUES (?, ?, ?, ?, ?, ?)
                """, (url, title, uploader, duration, thumbnail_url, datetime.now()))
                conn.commit()
        except Exception as e:
            from logger import log
            log.error(f"Cache set error: {e}")

    # --- History Methods ---
    def add_history(self, song: Song, max_size: int = 50):
        try:
            with sqlite3.connect(self.db_path) as conn:
                cursor = conn.cursor()
                cursor.execute("""
                    INSERT INTO history 
                    (title, path, uploader, duration, thumbnail_url, is_external, requested_by, user_id)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                """, (
                    song.title, song.path, song.uploader, song.duration, 
                    song.thumbnail_url, song.is_external, song.requested_by, str(song.user_id) if song.user_id else None
                ))
                
                # Cleanup if exceeded max size
                cursor.execute("SELECT COUNT(*) FROM history")
                count = cursor.fetchone()[0]
                if count > max_size:
                    to_remove = count - max_size
                    cursor.execute(f"DELETE FROM history WHERE id IN (SELECT id FROM history ORDER BY played_at ASC LIMIT {to_remove})")
                
                conn.commit()
        except Exception as e:
            from logger import log
            log.error(f"Error adding to history DB: {e}")

    def increment_stat(self, key: str):
        """Increments a global counter for analytics."""
        try:
            with sqlite3.connect(self.db_path) as conn:
                conn.execute("""
                    INSERT INTO system_stats (key, value) VALUES (?, 1)
                    ON CONFLICT(key) DO UPDATE SET value = value + 1
                """, (key,))
                conn.commit()
        except: pass

    def pop_history_latest(self) -> Optional[Song]:
        """Fetches and deletes the most recent history entry."""
        try:
            with sqlite3.connect(self.db_path) as conn:
                conn.row_factory = sqlite3.Row
                cursor = conn.cursor()
                cursor.execute("SELECT * FROM history ORDER BY played_at DESC LIMIT 1")
                row = cursor.fetchone()
                if row:
                    song = Song.from_dict(dict(row))
                    cursor.execute("DELETE FROM history WHERE id = ?", (row["id"],))
                    conn.commit()
                    return song
                return None
        except Exception as e:
            from logger import log
            log.error(f"Error popping history from DB: {e}")
            return None

    def get_history(self, limit: int = 50) -> List[Song]:
        try:
            with sqlite3.connect(self.db_path) as conn:
                conn.row_factory = sqlite3.Row
                cursor = conn.cursor()
                cursor.execute("SELECT * FROM history ORDER BY played_at DESC LIMIT ?", (limit,))
                rows = cursor.fetchall()
                return [Song.from_dict(dict(row)) for row in rows]
        except Exception as e:
            from logger import log
            log.error(f"Error getting history from DB: {e}")
            return []

    def clear_history(self):
        try:
            with sqlite3.connect(self.db_path) as conn:
                conn.execute("DELETE FROM history")
                conn.commit()
        except Exception as e:
            from logger import log
            log.error(f"Error clearing history DB: {e}")

    # --- Favorites Methods ---
    def add_favorite(self, user_id: str, song: Song):
        if not song or not song.path:
            return
            
        try:
            with sqlite3.connect(self.db_path) as conn:
                cursor = conn.cursor()
                cursor.execute("""
                    INSERT OR REPLACE INTO favorites 
                    (user_id, path, title, uploader, duration, thumbnail_url, is_external)
                    VALUES (?, ?, ?, ?, ?, ?, ?)
                """, (
                    str(user_id), song.path, song.title, song.uploader, 
                    song.duration, song.thumbnail_url, song.is_external
                ))
                conn.commit()
        except Exception as e:
            from logger import log
            log.error(f"Error adding favorite to DB: {e}")

    def remove_favorite(self, user_id: str, path: str):
        try:
            with sqlite3.connect(self.db_path) as conn:
                conn.execute("DELETE FROM favorites WHERE user_id = ? AND path = ?", (str(user_id), path))
                conn.commit()
        except Exception as e:
            from logger import log
            log.error(f"Error removing favorite from DB: {e}")

    def is_favorite(self, user_id: str, path: str) -> bool:
        try:
            with sqlite3.connect(self.db_path) as conn:
                cursor = conn.cursor()
                cursor.execute("SELECT 1 FROM favorites WHERE user_id = ? AND path = ?", (str(user_id), path))
                return cursor.fetchone() is not None
        except Exception:
            return False

    def get_favorites(self, user_id: str) -> List[Song]:
        try:
            with sqlite3.connect(self.db_path) as conn:
                conn.row_factory = sqlite3.Row
                cursor = conn.cursor()
                cursor.execute("SELECT * FROM favorites WHERE user_id = ?", (str(user_id),))
                rows = cursor.fetchall()
                return [Song.from_dict(dict(row)) for row in rows]
        except Exception as e:
            from logger import log
            log.error(f"Error getting favorites from DB: {e}")
            return []

    def clear_favorites(self, user_id: str):
        try:
            with sqlite3.connect(self.db_path) as conn:
                conn.execute("DELETE FROM favorites WHERE user_id = ?", (str(user_id),))
                conn.commit()
        except Exception as e:
            from logger import log
            log.error(f"Error clearing favorites DB: {e}")

# Legacy name support or just use metadata cache as wrapper
class MetadataCache:
    def __init__(self, db_path: str = "data/cache.db"):
        # We redirect to the new central DB
        self.db = Database("data/radio.db")
    
    def get(self, url: str): return self.db.get_cache(url)
    def set(self, *args, **kwargs): self.db.set_cache(*args, **kwargs)
