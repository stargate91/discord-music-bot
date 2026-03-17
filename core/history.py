import json
import os
from datetime import datetime
from typing import List, Dict, Any
from core.models import Song

class HistoryManager:
    def __init__(self, storage_path: str = "history.json", max_size: int = 50):
        self.storage_path = storage_path
        self.max_size = max_size
        self.history: List[Song] = self._load()

    def _load(self) -> List[Song]:
        if not os.path.exists(self.storage_path):
            return []
        try:
            with open(self.storage_path, "r", encoding="utf-8") as f:
                data = json.load(f)
                if isinstance(data, list):
                    return [Song.from_dict(d) for d in data if isinstance(d, dict)]
                return []
        except Exception:
            return []

    def _save(self):
        try:
            with open(self.storage_path, "w", encoding="utf-8") as f:
                data = []
                for song in self.history:
                    data.append({
                        "title": song.title,
                        "path": song.path,
                        "uploader": song.uploader,
                        "duration": song.duration,
                        "thumbnail_url": song.thumbnail_url,
                        "is_external": song.is_external,
                        "played_at": song.played_at,
                        "requested_by": song.requested_by
                    })
                json.dump(data, f, indent=4, ensure_ascii=False)
        except Exception as e:
            from logger import log
            log.error(f"Error saving history: {e}")

    def add(self, song: Song):
        if not song or not song.path:
            return
            
        # Set timestamp
        song.played_at = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        
        # Add to beginning
        self.history.insert(0, song)
        
        # Keep size limit
        if len(self.history) > self.max_size:
            self.history = self.history[:self.max_size]
            
        self._save()

    def get_all(self) -> List[Song]:
        return self.history

    def clear(self):
        """Removes all items from history."""
        self.history = []
        self._save()
