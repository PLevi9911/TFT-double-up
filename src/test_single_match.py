import json

# ---------- PATHOK (fix, abszolút) ----------
MATCH_PATH = r"C:\Users\Levi\Documents\tft_duo_project\data\raw\matches\EUN1_3906293362.json"
BUILDS_PATH = r"C:\Users\Levi\Documents\tft_duo_project\config\builds_set16_16.3.json"


# ---------- SEGÉD ----------
def load_json(path):
    with open(path, "r", encoding="utf-8") as f:
        return json.load(f)


def placement_to_bucket(p: int) -> int:
    if p in (1, 2):
        return 1
    if p in (3, 4):
        return 2
    if p in (5, 6):
        return 3
    return 4


def min_required_hits(size: int) -> int:
    if size <= 1:
        return 1
    if size == 2:
        return 2
    if size <= 4:
        return 2
    return 3


def identify_build(board_units, builds):
    board = set(u.lower() for u in board_units)

    best = None

    for b in builds:
        units = b.get("units", [])
        if not units:
            continue

        clean = list(dict.fromkeys(units))
        clean_norm = [u.lower() for u in clean]

        matched = [clean[i] for i, u in enumerate(clean_norm) if u in board]

        if len(matched) < min_required_hits(len(clean)):
            continue

        score = len(matched) / len(clean)

        candidate = {
            "build_id": b["build_id"],
            "name": b["name"],
            "matched": matched,
            "score": round(score, 3),
            "size": len(clean),
        }

        if best is None:
            best = candidate
        else:
            if (candidate["score"], len(candidate["matched"]), candidate["size"]) > \
               (best["score"], len(best["matched"]), best["size"]):
                best = candidate

    return best


# ---------- MAIN TESZT ----------
def main():
    match = load_json(MATCH_PATH)
    builds = load_json(BUILDS_PATH)

    info = match["info"]
    print("MATCH:", match["metadata"]["match_id"])
    print("SET:", info.get("tft_set_number"), info.get("tft_set_core_name"))
    print("-" * 50)

    for p in info["participants"]:
        name = p.get("riotIdGameName")
        tag = p.get("riotIdTagline")
        placement = p.get("placement")

        units = [u["character_id"] for u in p.get("units", [])]
        build = identify_build(units, builds)

        bucket = placement_to_bucket(int(placement))

        print(f"{name}#{tag}")
        print(" placement:", placement, "-> bucket:", bucket)
        print(" units:", units)

        if build:
            print(" BUILD:", build["build_id"], build["name"])
            print(" matched:", build["matched"], "score:", build["score"])
        else:
            print(" BUILD: UNKNOWN")

        print("-" * 50)


if __name__ == "__main__":
    main()