# Discord Radio Bot 🎵

Hi! This is a Discord radio bot project I'm working on. It's built with Python and it's pretty cool because it uses a lot of new Discord UI features like buttons, selects, and modals.

## 🚀 Awesome Features

- **Rich Interface**: I made a custom UI that has progress bars, status icons, and nice containers. It looks really modern!
- **YouTube Search**: You can search for songs directly inside Discord and add them to the queue.
- **Queue Management**: You can see your queue, move songs up and down, or remove them. I even added a button to clear everything!
- **Seeking**: You can jump to a specific time (like 1:30) using a command or a modal. It even works when the bot is paused!
- **Multi-language**: The bot supports English and Hungarian. You can change it in the settings.
- **Monochrome Theme**: I made the UI mostly "monochrome" (dark gray) so it looks professional, but the "Playing" state has a nice blue accent.
- **Configurable**: I put settings like text length limits (so titles don't break the UI) and colors in `config.json` and `config.local.json`.

## 🛠️ How to get it running

1. **Install requirements**:
   ```bash
   pip install -r requirements.txt
   ```
2. **FFmpeg**: You need to have `ffmpeg` installed on your system because it's what plays the music.
3. **Setup Environment**:
   - Create a `.env` file.
   - Add your `DISCORD_TOKEN`.
4. **Config**: Check the `config.json` for things like `guild_id` and `radio_text_channel_id`.
5. **Run**:
   ```bash
   python main.py
   ```

## 📂 Project Structure

I tried to keep things organized:
- `main.py`: The starting point of the bot.
- `player_engine.py`: This is the "brain" that handles FFmpeg and the voice client.
- `core/`: Has the `RadioManager` which keeps track of the state.
- `ui_...py`: A bunch of files for different parts of the UI (player, search, translate, etc.).
- `providers/`: Where the YouTube-DL logic lives.

## 📝 A Note from Me
I'm trying to use "Clean Code" principles here. I used enums for actions and states, and I made everything modular so it's easier to add stuff later (like maybe Spotify support!).

Hope you enjoy it! Let me know if you find any bugs. 🐛
