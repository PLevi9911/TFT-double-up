import os
import json
import shutil
import re

# =========================================================
# 0) Setup
# =========================================================

RAW_DIR = r"C:\Users\Levi\Documents\tft_duo_project\data\raw\matches"

PATCH_PREFIX = "16.3"

OUT_DIR = rf"C:\Users\Levi\Documents\tft_duo_project\data\raw\matches\16.3"


# =========================================================
# 1) Helpers
# =========================================================

def ensure_dir(path: str):
    os.makedirs(path, exist_ok=True)


def extract_patch(game_version: str) -> str | None:
    """
    Riot format:
    <Releases/16.3>
    """
    if not game_version:
        return None

    m = re.search(r"<Releases/(\d+\.\d+)>", game_version)
    if m:
        return m.group(1)

    return None


# =========================================================
# 2) MAIN
# =========================================================

def main():

    ensure_dir(OUT_DIR)

    total = 0
    moved = 0
    skipped = 0

    for fn in os.listdir(RAW_DIR):
        if not fn.lower().endswith(".json"):
            continue

        total += 1
        full_path = os.path.join(RAW_DIR, fn)

        try:
            with open(full_path, "r", encoding="utf-8") as f:
                match = json.load(f)
        except Exception as e:
            print(f"[SKIP] I could not read: {fn} -> {e}")
            skipped += 1
            continue

        game_version = match.get("info", {}).get("game_version", "")
        patch = extract_patch(game_version)

        if patch == PATCH_PREFIX:
            target_path = os.path.join(OUT_DIR, fn)
            shutil.move(full_path, target_path)
            moved += 1
        else:
            continue

    print("\n[DONE]")
    print(f"Total files scanned: {total}")
    print(f"Moved to patch {PATCH_PREFIX}: {moved}")
    print(f"Skipped (read error): {skipped}")
    print(f"Output dir: {OUT_DIR}")


if __name__ == "__main__":
    main()
