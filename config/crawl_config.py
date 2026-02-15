# config/crawl_config.py
# TFT Double Up crawler config (Windows absolute paths)

REGIONAL_ROUTING = "europe"     # EUNE/EUW -> europe routing :contentReference[oaicite:1]{index=1}
PATCH_PREFIX = "16.3"           # jelenlegi patch prefix

# Double Up queueId-k (ha a kept_count 0 marad, később debug alapján átírjuk)
DOUBLE_UP_QUEUE_IDS = {1150, 1160}

# Cél: ennyi patch+DoubleUp match legyen meg
TARGET_MATCHES = 10000

# Ennyi matchId-t kérünk le playerenként (seed bővítéshez)
MATCHLIST_COUNT_PER_PLAYER = 50

# Rate-limit barát delay (dev key-hez)
SLEEP_SECONDS = 0.20

# ABSZOLÚT útvonalak (a te gépedhez)
PROJECT_ROOT = r"C:\Users\Levi\Documents\tft_duo_project"
STATE_PATH = PROJECT_ROOT + r"\data\state\crawler_state.json"
RAW_DIR = PROJECT_ROOT + r"\data\raw\matches"

# Biztonsági korlát: ne nőjön végtelenre a queue
MAX_QUEUE_SIZE = 30000

# State mentés gyakorisága (kept meccsek alapján)
SAVE_EVERY_N_KEPT = 75
