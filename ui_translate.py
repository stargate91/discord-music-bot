import json
import os
import re
from ui_icons import Icons

# Global storage for loaded translations
_translations = {}
_radio_ref = None

def load_locales():
    """Load all .json files from the locales directory."""
    global _translations
    base_path = os.path.dirname(os.path.abspath(__file__))
    locales_path = os.path.join(base_path, "locales")
    
    if not os.path.exists(locales_path):
        print(f"Warning: Locales path not found at {locales_path}")
        return

    for filename in os.listdir(locales_path):
        if filename.endswith(".json"):
            lang_code = filename[:-5]
            try:
                with open(os.path.join(locales_path, filename), "r", encoding="utf-8") as f:
                    _translations[lang_code] = json.load(f)
            except Exception as e:
                print(f"Error loading locale {filename}: {e}")

# Initial load
load_locales()

def init_translate(radio_instance):
    global _radio_ref
    _radio_ref = radio_instance

def t(key, **kwargs):
    """
    Translates a key based on the current radio language.
    Supports icon placeholders like {SYNC} and dynamic kwargs.
    """
    lang = "hu"
    if _radio_ref:
        lang = getattr(_radio_ref, "language", "hu")
    
    # Get translation for current language, fallback to English, then to the key itself
    lang_dict = _translations.get(lang, _translations.get("en", {}))
    text = lang_dict.get(key)
    
    if text is None:
        # Fallback to English if current lang doesn't have the key
        text = _translations.get("en", {}).get(key, key)

    # 1. Replace Icon placeholders: {SYNC} -> Icons.SYNC
    if isinstance(text, str) and "{" in text:
        # We extract names between braces and try to match with Icons constants
        # Using a regex to find placeholders like {SYNC}
        placeholders = re.findall(r"\{([A-Z0-9_]+)\}", text)
        for p in placeholders:
            if hasattr(Icons, p):
                icon_val = getattr(Icons, p)
                text = text.replace(f"{{{p}}}", str(icon_val))
    
    # 2. Support for dynamic variables (if any)
    if kwargs and isinstance(text, str):
        try:
            text = text.format(**kwargs)
        except Exception:
            # If formatting fails (e.g. missing keys in kwargs or malformed string), return as is
            pass
            
    return text
