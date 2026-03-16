from dataclasses import dataclass, field
from typing import Optional, Dict, Any

@dataclass
class Song:
    title: str
    path: str  # The playback URL or file path
    uploader: Optional[str] = None
    duration: int = 0
    thumbnail_url: Optional[str] = None
    webpage_url: Optional[str] = None
    source: Optional[str] = None
    requested_by: Optional[str] = None  # Mention string or name
    played_at: Optional[str] = None     # Timestamp when it was played
    
    # Internal state
    is_resolving: bool = False
    is_external: bool = False
    stream_url: Optional[str] = None

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "Song":
        """Factory method to create a Song object from a dictionary."""
        # Normalize uploader/artist
        uploader = data.get("uploader") or data.get("artist") or data.get("channel")
        
        return cls(
            title=data.get("title", "Unknown"),
            path=data.get("path") or data.get("url", ""),
            uploader=uploader,
            duration=int(data.get("duration", 0)),
            thumbnail_url=data.get("thumbnail_url") or data.get("thumbnail"),
            webpage_url=data.get("webpage_url"),
            source=data.get("source"),
            is_resolving=data.get("is_resolving", False),
            is_external=data.get("is_external", False),
            stream_url=data.get("stream_url"),
            played_at=data.get("played_at")
        )

    def to_dict(self) -> Dict[str, Any]:
        """Convert back to dict."""
        return self.__dict__
    
    def update(self, data: Dict[str, Any]):
        """Update fields from a dictionary with priority mapping."""
        # 1. Direct field mapping
        for key, value in data.items():
            if hasattr(self, key) and value is not None:
                # Always overwrite if current is placeholder or None
                current = getattr(self, key)
                if current in [None, 0, "...", "Unknown"]:
                    setattr(self, key, value)
                elif key in ["stream_url", "is_resolving"]: 
                     # Always overwrite internal state
                     setattr(self, key, value)

        # 2. Logic-based mapping for uploader
        new_uploader = data.get("uploader") or data.get("artist") or data.get("channel")
        if new_uploader and (self.uploader in [None, "...", "Unknown"]):
            self.uploader = new_uploader
        
        # 3. Path/URL mapping
        new_path = data.get("path") or data.get("url")
        if new_path and (self.path in [None, ""]):
            self.path = new_path
