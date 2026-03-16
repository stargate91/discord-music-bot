import json
import os
from typing import List, Dict, Any
from core.models import Song

class FavoriteManager:
    def __init__(self, storage_path: str = "favorites.json"):
        self.storage_path = storage_path
        self.favorites: Dict[str, List[Dict[str, Any]]] = self._load()

    def _load(self) -> Dict[str, List[Dict[str, Any]]]:
        if not os.path.exists(self.storage_path):
            return {}
        try:
            with open(self.storage_path, "r", encoding="utf-8") as f:
                return json.load(f)
        except Exception:
            return {}

    def _save(self):
        try:
            with open(self.storage_path, "w", encoding="utf-8") as f:
                json.dump(self.favorites, f, indent=4, ensure_ascii=False)
        except Exception as e:
            from logger import log
            log.error(f"Error saving favorites: {e}")

    def is_favorite(self, user_id: str, song: Song) -> bool:
        if not song or not song.path:
            return False
        user_id_str = str(user_id)
        if user_id_str not in self.favorites:
            return False
        return any(fav.get("path") == song.path for fav in self.favorites[user_id_str])

    def toggle_favorite(self, user_id: str, song: Song) -> bool:
        """Returns True if added, False if removed."""
        if not song or not song.path:
            return False
            
        user_id_str = str(user_id)
        if user_id_str not in self.favorites:
            self.favorites[user_id_str] = []
        
        # Check by path (unique identifier for streams/files)
        existing = next((fav for fav in self.favorites[user_id_str] if fav.get("path") == song.path), None)
        
        if existing:
            self.favorites[user_id_str].remove(existing)
            self._save()
            return False
        else:
            # We only store the essential data to recreate a Song object
            self.favorites[user_id_str].append({
                "title": song.title,
                "path": song.path,
                "uploader": song.uploader,
                "duration": song.duration,
                "thumbnail_url": song.thumbnail_url,
                "is_external": song.is_external
            })
            self._save()
            return True

    def get_favorites(self, user_id: str) -> List[Song]:
        user_id_str = str(user_id)
        if user_id_str not in self.favorites:
            return []
        return [Song.from_dict(fav) for fav in self.favorites[user_id_str]]
