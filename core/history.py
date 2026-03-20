from datetime import datetime
from typing import List, Optional
from core.models import Song
from core.database import Database

class HistoryManager:
    def __init__(self, db: Database, max_size: int = 50):
        self.db = db
        self.max_size = max_size
        # No local 'history' list, we fetch from DB when needed to keep it synced
        # But for performance in view we can still keep it cache if we want
        # However, the user wants 'everything in .db', so let's rely on DB.

    def add(self, song: Song):
        if not song or not song.path:
            return
            
        # Set timestamp if not set
        if not song.played_at:
            song.played_at = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        
        self.db.add_history(song)

    def get_all(self, limit: Optional[int] = None) -> List[Song]:
        """Returns items from the DB. Defaults to no limit if None."""
        return self.db.get_history(limit=limit)

    def clear(self):
        """Removes all items from history."""
        self.db.clear_history()

    def get_latest(self, offset: int = 0) -> Optional[Song]:
        """Returns the history entry at the given offset (0 = latest) without deleting."""
        return self.db.get_history_latest(offset=offset)

    def pop_latest(self) -> Optional[Song]:
        """Fetches and deletes the most recent history entry. (Legacy/Manual use)"""
        return self.db.pop_history_latest()

    @property
    def history(self) -> List[Song]:
        """Legacy access for compatibility with existing UI."""
        return self.get_all()
