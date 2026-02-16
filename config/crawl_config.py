# config/crawl_config.py
# TFT Double Up crawler config (Windows absolute paths)

REGIONAL_ROUTING = "europe"     # EUNE/EUW -> europe routing :contentReference[oaicite:1]{index=1}
PATCH_PREFIX = "16.3"           #  patch prefix

# Double Up queueId-k (if kept_count is 0, later you can debug)
DOUBLE_UP_QUEUE_IDS = {1150, 1160}

# Goal: How many games you want at least
TARGET_MATCHES = 10000

#  Match ID per player (to extend seeds)
MATCHLIST_COUNT_PER_PLAYER = 50

# Rate-limit friendly delay (dev key)
SLEEP_SECONDS = 0.20

# File paths
PROJECT_ROOT = r"C:\Users\Levi\Documents\tft_duo_project"
STATE_PATH = PROJECT_ROOT + r"\data\state\crawler_state.json"
RAW_DIR = PROJECT_ROOT + r"\data\raw\matches"

# Safety Limit
MAX_QUEUE_SIZE = 30000

# State saving frequency (kept games)
SAVE_EVERY_N_KEPT = 75
