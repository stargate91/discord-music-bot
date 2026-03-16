from abc import ABC, abstractmethod
from typing import Optional, Dict, Any

class MusicProvider(ABC):
    @abstractmethod
    async def resolve(self, query: str) -> Optional[Dict[str, Any]]:
        """
        Resolves a search query or URL into a standardized song dictionary.
        Returns None if resolution fails.
        """
        pass

    @abstractmethod
    def matches(self, query: str) -> bool:
        """
        Returns True if this provider can handle the given query/URL.
        """
        pass

    @abstractmethod
    async def search(self, query: str, limit: int = 5) -> list[Dict[str, Any]]:
        """
        Searches for tracks based on a query.
        """
        pass
    @abstractmethod
    def is_playlist(self, query: str) -> bool:
        """
        Returns True if the query/URL refers to a playlist.
        """
        pass
