import sqlite3
import os
from datetime import datetime
from typing import Optional, Dict, Any

class MetadataCache:
    def __init__(self, db_path: str = "cache.db"):
        self.db_path = db_path
        self._init_db()

    def _init_db(self):
        """Initializes the database and creates the table if it doesn't exist."""
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.cursor()
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
            conn.commit()

    def get(self, url: str) -> Optional[Dict[str, Any]]:
        """Retrieves song metadata from the cache."""
        try:
            with sqlite3.connect(self.db_path) as conn:
                conn.row_factory = sqlite3.Row
                cursor = conn.cursor()
                cursor.execute("SELECT * FROM song_cache WHERE url = ?", (url,))
                row = cursor.fetchone()
                if row:
                    data = dict(row)
                    # Convert duration to int just in case
                    data["duration"] = int(data["duration"])
                    return data
        except Exception as e:
            from logger import log
            log.debug(f"Cache get error for {url}: {e}")
        return None

    def set(self, url: str, title: str, uploader: str, duration: int, thumbnail_url: str):
        """Saves or updates song metadata in the cache."""
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
            log.error(f"Cache set error for {url}: {e}")
