from typing import List
from core.models import Song
from core.database import Database

class FavoriteManager:
    def __init__(self, db: Database):
        self.db = db

    def is_favorite(self, user_id: str, song: Song) -> bool:
        if not song or not song.path:
            return False
        return self.db.is_favorite(user_id, song.path)

    def toggle_favorite(self, user_id: str, song: Song) -> bool:
        """Returns True if added, False if removed."""
        if not song or not song.path:
            return False
            
        u_id = str(user_id)
        if self.db.is_favorite(u_id, song.path):
            self.db.remove_favorite(u_id, song.path)
            return False
        else:
            self.db.add_favorite(u_id, song)
            # Verify if it was actually added before returning True
            if self.db.is_favorite(u_id, song.path):
                # Support fast playback from library by auto-caching
                self.db.set_cache(
                    url=song.path,
                    title=song.title,
                    uploader=song.uploader or "Unknown",
                    duration=song.duration,
                    thumbnail_url=song.thumbnail_url or ""
                )
                return True
            return False

    def get_favorites(self, user_id: str) -> List[Song]:
        return self.db.get_favorites(user_id)

    def clear_favorites(self, user_id: str):
        """Removes all favorites for a specific user."""
        self.db.clear_favorites(user_id)
