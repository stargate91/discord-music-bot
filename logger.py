import logging
import sys
import os
from colorama import init, Fore, Style

init(autoreset=True)

class ColoredFormatter(logging.Formatter):
    def format(self, record):
        level_colors = {
            logging.DEBUG: Fore.CYAN,
            logging.INFO: Fore.GREEN,
            logging.WARNING: Fore.YELLOW,
            logging.ERROR: Fore.RED,
            logging.CRITICAL: Fore.RED + Style.BRIGHT,
        }
        color = level_colors.get(record.levelno, Fore.WHITE)
        record.levelname = f"{color}{record.levelname}{Style.RESET_ALL}"
        record.msg = f"{Style.BRIGHT}{record.msg}{Style.RESET_ALL}" if record.levelno >= logging.WARNING else record.msg
        return super().format(record)

log = logging.getLogger("RadioBot")
log.setLevel(logging.INFO)

# Ensure data directory exists
os.makedirs("data", exist_ok=True)

# Support multiple instances via environment variable
instance_name = os.getenv("INSTANCE_NAME", "")
log_filename = f"data/{instance_name}_radio.log" if instance_name else "data/radio.log"

# File Handler
file_handler = logging.FileHandler(log_filename, encoding="utf-8")
file_handler.setFormatter(logging.Formatter("%(asctime)s [%(levelname)s] %(message)s"))
log.addHandler(file_handler)

# Console Handler
console_handler = logging.StreamHandler(sys.stdout)
console_handler.setFormatter(ColoredFormatter("%(asctime)s [%(levelname)s] %(message)s", "%H:%M:%S"))
log.addHandler(console_handler)
