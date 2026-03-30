# 🎵 DC Radio Bot - Professional Discord Audio System

A highly modular, professional Discord music bot built with **discord.py**, featuring a premium interactive UI, robust playback engine, and a standardized feedback system.

---

## ✨ Key Features

- **🚀 Advanced Playback Navigation**: Browser-like non-destructive history traversal. Move back (`BACK`) and forward (`NEXT`) through your session without losing your queue or duplicating entries.
- **📱 Premium Modern UI**: Built with a custom layout system (`LayoutView`, `Container`, `ActionRow`) providing a sleek aesthetic. Includes dynamic progress bars, status icons, and real-time updates.
- **💬 Standardized UI Feedback**: Every interaction (buttons, slash commands, prefix commands) provides immediate confirmation with icon-prefixed, auto-deleting messages (default 20s).
- **🛡️ Smart Error Handling**: Distinguishes between critical failures (❌ `Icons.ERROR`) and user guidance (⚠️ `Icons.WARNING`). Features private (ephemeral) error messages for out-of-channel usage.
- **🎨 Dynamic Icon & Emoji System**: Fully configurable icons via JSON with a robust three-tier fallback: `Instance Config` -> `Global Config` -> `Hardcoded Unicode Classics`.
- **📚 Persistent History & Favorites**: Fully persistent playback history and personal favorites stored in SQLite, allowing users to build their own collections.
- **🌍 Native Multi-language**: Built-in English and Hungarian support using a centralized localization engine (`hu.json`/`en.json`).
- **🛠️ Multi-Instance Ready**: Run multiple isolated bots from the same codebase. Use the `INSTANCE_NAME` environment variable to separate configurations and databases.

---

## 🛠️ Installation & Setup

### 1. Requirements
- **Python 3.10+**
- **FFmpeg**: Must be available in your system's PATH.
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
1. Create a `.env` file in the root or `configs/` directory.
2. Add your `DISCORD_TOKEN` and `GUILD_ID`.
3. (Optional) Set `INSTANCE_NAME=bot1` to use `config.bot1.json` and `radio.bot1.db`.
4. Define your `radio_text_channel_id` in the relevant JSON config.

---

## 📂 Project Architecture

The project follows a modular, action-dispatched architecture for maximum stability:

- **`main.py`**: Entry point and Discord bot initialization.
- **`player_engine.py`**: The playback brain. Handles FFmpeg streaming and navigation logic.
- **`config_loader.py`**: Handles JSON and Environment variable merging for multi-instance support.
- **`core/`**:
  - `radio.py`: The `RadioManager` - orchestrates State, Queue, and Action dispatching.
  - `database.py`: SQLite persistence layer (Cache, History, Favorites).
- **`ui_*.py`**: Modular UI & Logic components.
  - `ui_player.py`: The main Now Playing controller and player views.
  - `ui_search.py`: YouTube search modals and Library management.
  - `ui_icons.py`: Centralized icon registry with fallback logic.
  - `ui_utils.py`: Standardized UI helpers (feedback mapping, safe deletion).
  - `ui_translate.py`: Localization engine (i18n).
- **`locales/`**: JSON-based translation files for all user-facing text.

---

## 🛠️ Engineering Principles

- **Action Dispatcher Pattern**: All state changes are driven by `RadioAction` enums, ensuring predictable and traceable behavior.
- **Decoupled Design**: The UI and Playback Engine are strictly separated; the UI only reflects the State and dispatches Actions.
- **Automatic Cleanup**: Intelligent monitoring (`_cleanup_stray_messages`) keeps the radio channel clean by sweeping old controllers.

---

## 📝 Contribution
Found a bug? Have a feature request? Feel free to open an issue or submit a pull request! 🐛

Made with ❤️ for the Discord community.

