# 🎵 Advanced Discord Music/Radio Bot

A highly modular, professional Discord music bot built with **discord.py**, featuring a rich, interactive UI and a robust playback engine.

---

## ✨ Key Features

- **🚀 Advanced Playback Navigation**: Implementing a browser-like non-destructive history traversal. Move back (`BACK`) and forward (`NEXT`) through your session without losing your original queue or duplicating history entries.
- **📱 Rich & Modern UI**: Built with a custom layout system (`LayoutView`, `Container`, `ActionRow`) providing a sleek, professional aesthetic. Includes dynamic progress bars, status icons, and real-time updates.
- **📚 Persistent Unlimited History**: Fully persistent playback history stored in SQLite. No entry limits by default, allowing you to browse and replay any song from your past sessions.
- **🔍 Smart Search & Favorites**: integrated YouTube search with automated metadata resolution and a personal Favorites/Library system for each user.
- **🧹 Auto-Cleaning Radio Channel**: Features an intelligent monitoring system (`_cleanup_stray_messages`) that automatically removes old controllers and stray messages, keeping your dedicated radio channel pristine.
- **🛠️ Multi-Instance Ready**: Designed for horizontal scaling. Use the `INSTANCE_NAME` environment variable to run multiple isolated bots from the same codebase with separate configurations and databases.
- **⚙️ Deeply Configurable**: Fine-tune everything from notification timeouts (ephemeral message auto-deletion) to UI themes and length limits via `configs/config.json`.
- **🌍 Multi-language Support**: Native English and Hungarian support with an extensible translation system.

---

## 🛠️ Installation & Setup

### 1. Requirements
- **Python 3.10+**
- **FFmpeg**: Must be installed and available in your system's PATH.
- **yt-dlp**: Required for metadata resolution and stream extraction.

### 2. Setup
```bash
# Clone the repository
git clone <repo-url>
cd dc_radio_bot

# Install dependencies
pip install -r requirements.txt
```

### 3. Configuration
1. Create a `configs/.env` file (refer to `.env.example`).
2. Add your `DISCORD_TOKEN`.
3. (Optional) Set `INSTANCE_NAME=mybot` to use a specific `config.mybot.json` and `radio.mybot.db`.
4. Configure your `guild_id` and `radio_text_channel_id` in `configs/config.json`.

---

## 📂 Project Architecture

The project follows a modular, action-dispatched architecture:

- **`main.py`**: Entry point and Discord bot initialization.
- **`player_engine.py`**: The "brain" of the playback. Handles FFmpeg streaming, state transitions, and the `BACK`/`SKIP` navigation logic.
- **`core/`**:
  - `radio.py`: The `RadioManager` - orchestrates State, Queue, and Action dispatching.
  - `database.py`: SQLite persistence layer for Cache, History, and Favorites.
  - `models.py`: Core dataclasses (Song, RadioState).
- **`ui_*.py`**: Modular UI components.
  - `ui_player.py`: The main Now Playing controller.
  - `ui_search.py`: Search modals and Library views.
  - `ui_translate.py`: The i18n engine.
- **`providers/`**: Pluggable source providers (currently YTDLP).

---

## 🛠️ Development & Principles
This project adheres to **Clean Code** and **SOLID** principles:
- **Action Dispatcher Pattern**: State changes are driven by `RadioAction` enums for predictable behavior.
- **Decoupled Engine**: The playback loop is separate from the UI, allowing for different interfaces (Bot, Web, etc.).
- **Async First**: Fully asynchronous design for high-performance handling of multiple concurrent events.

---

## 📝 Contribution
Found a bug? Have a feature request? Feel free to open an issue or submit a pull request! 🐛

Made with ❤️ for the Discord community.
