import asyncio
import asyncio.subprocess
import json
from typing import Optional, Dict, Any
from .base import MusicProvider
from logger import log

class YTDLPProvider(MusicProvider):
    def __init__(self, ytdlp_path: str = "yt-dlp"):
        self.ytdlp_path = ytdlp_path

    def matches(self, query: str) -> bool:
        return query.startswith(("http://", "https://", "www."))

    async def resolve(self, url: str) -> Optional[Dict[str, Any]]:
        return await self._resolve_internal(url, playlist=False)

    def is_playlist(self, query: str) -> bool:
        return "list=" in query or "playlist" in query.lower() or "/sets/" in query.lower()

    async def _resolve_internal(self, url: str, playlist: bool = False) -> Optional[Dict[str, Any]]:
        try:
            referer = "https://soundcloud.com/" if "soundcloud.com" in url else "https://www.google.com"
            cmd = [
                self.ytdlp_path, 
                "-j", 
                "-f", "bestaudio[ext=mp3]/bestaudio/best",
                "--no-playlist", 
                "--flat-playlist",
                "--user-agent", "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
                "--referer", referer,
                url
            ]
                 
            process = await asyncio.create_subprocess_exec(
                *cmd,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE
            )
            stdout, stderr = await process.communicate()
            
            if process.returncode != 0:
                err_msg = stderr.decode(errors="ignore").strip()
                log.error(f"[YT-DLP] Error probing {url} (code {process.returncode}): {err_msg}")
                return None
                
            info = json.loads(stdout.decode())
            
            stream_url = info.get("url")
            if not stream_url and "formats" in info:
                formats = info["formats"]
                audio_formats = [f for f in formats if f.get("vcodec") == "none"]
                if audio_formats:
                    stream_url = audio_formats[-1].get("url")
                else:
                    stream_url = formats[-1].get("url")
            
            if not stream_url:
                log.warning(f"[YT-DLP] No stream URL found in metadata for {url}")
                return None
                
            return {
                "title": info.get("title", "Unknown Title"),
                "uploader": info.get("uploader") or info.get("channel") or info.get("artist") or "Unknown Artist",
                "album": info.get("extractor_key", "Web Stream"),
                "duration": int(info.get("duration", 0)),
                "stream_url": stream_url,
                "thumbnail_url": info.get("thumbnail"),
                "is_external": True,
                "webpage_url": info.get("webpage_url"),
                "path": url # Keep original URL as path
            }
        except Exception as e:
            log.error(f"[YT-DLP] Exception resolving {url}: {e}")
            return None

    async def resolve_playlist(self, url: str) -> list[Dict[str, Any]]:
        try:
            referer = "https://soundcloud.com/" if "soundcloud.com" in url else "https://www.google.com"
            cmd = [
                self.ytdlp_path, 
                "-j", 
                "--flat-playlist",
                "--user-agent", "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
                "--referer", referer,
                url
            ]
                 
            process = await asyncio.create_subprocess_exec(
                *cmd,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE
            )
            stdout, stderr = await process.communicate()
            
            if process.returncode != 0:
                err_msg = stderr.decode(errors="ignore").strip()
                log.error(f"[YT-DLP] Error fetching playlist {url}: {err_msg}")
                return []
                
            results = []
            lines = stdout.decode().splitlines()
            for line in lines:
                try:
                    info = json.loads(line)
                    results.append({
                        "title": info.get("title", "Unknown Title"),
                        "uploader": info.get("uploader") or info.get("channel") or info.get("artist") or "Unknown Artist",
                        "duration": int(info.get("duration", 0)),
                        "path": info.get("url") or info.get("webpage_url"),
                        "thumbnail_url": info.get("thumbnail"),
                        "is_external": True,
                        "webpage_url": info.get("webpage_url") or (f"https://www.youtube.com/watch?v={info['id']}" if info.get('id') else None)
                    })
                except: continue
            return results
        except Exception as e:
            log.error(f"[YT-DLP] Playlist resolution exception for {url}: {e}")
            return []

    async def search(self, query: str, limit: int = 5) -> list[Dict[str, Any]]:
        try:
            # use yt_search prefix for actual search
            search_query = f"ytsearch{limit}:{query}"
            cmd = [
                self.ytdlp_path, 
                "-j",
                "--flat-playlist",
                "--no-playlist",
                "--print-json",
                search_query
            ]
            
            process = await asyncio.create_subprocess_exec(
                *cmd,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE
            )
            stdout, stderr = await process.communicate()
            
            results = []
            if stdout:
                lines = stdout.decode().splitlines()
                for line in lines:
                    try:
                        info = json.loads(line)
                        results.append({
                            "title": info.get("title", "Unknown"),
                            "uploader": info.get("uploader") or info.get("channel") or "Unknown",
                            "duration": int(info.get("duration", 0)),
                            "path": info.get("url") or info.get("webpage_url"),
                            "thumbnail_url": info.get("thumbnail"),
                            "is_external": True
                        })
                    except: continue
            return results
        except Exception as e:
            log.error(f"[YT-DLP] Search exception for {query}: {e}")
            return []
