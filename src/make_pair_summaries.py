import os
import json
import math
from collections import Counter

# =================================================
# FILE PATHS
# =================================================
RAW_DIR = r"C:\Users\Levi\Documents\tft_duo_project\data\raw\matches\16.3"
BUILDS_PATH = r"C:\Users\Levi\Documents\tft_duo_project\config\builds_set16_16.3_SA.json"

PROCESSED_DIR = r"C:\Users\Levi\Documents\tft_duo_project\data\processed"
OUT_PATH = os.path.join(PROCESSED_DIR, "pair_summaries_SA.jsonl")


# =================================================
# HELPER
# =================================================


def ensure_dirs():
    os.makedirs(PROCESSED_DIR, exist_ok=True)


def load_json(path: str):
    with open(path, "r", encoding="utf-8") as f:
        return json.load(f)


def iter_json_files(folder: str):
    for fn in os.listdir(folder):
        if fn.lower().endswith(".json"):
            yield os.path.join(folder, fn)


def placement_to_team_rank(placement: int) -> int:
    """
    1-2 -> team_rank 1
    3-4 -> team_rank 2
    5-6 -> team_rank 3
    7-8 -> team_rank 4
    """
    if placement in (1, 2):
        return 1
    if placement in (3, 4):
        return 2
    if placement in (5, 6):
        return 3
    return 4

# =================================================
# BUILD IDENTIFICATING PARAMETERS
# =================================================
KEY_UNITS_N = 3        #  First 3 unit is the "key"
KEY_UNITS_MIN_HITS = 3 # Minimum matches from the "key" units



def min_required_hits(size: int) -> int:
    ## ha nem S tier, régi setup(ugyanaz, mint a tesztkódban)
    #if size <= 1:
        #return 1
    #if size == 2:
        #return 2
    #if size <= 4:
        #return 2
    #return 2

    # általános: nagy core listánál több találat kell S tier setuő
    # 8 -> 5, 9 -> 6
    return max(2, math.ceil(size * 0.5))


# Régi azonositás, jobbra def identify_build(board_units: list[str], builds: list[dict]):

    """
    Bizonyítottan működő logika:
    - normalizál: lower()
    - build_units -> unique
    - score: matched/size
    - tie-break: score, matched count, build size
    """
    board = set(u.strip().lower() for u in board_units if u)
    best = None

    for b in builds:
        units = b.get("units", [])
        if not units:
            continue

        clean = list(dict.fromkeys(units))
        clean_norm = [u.strip().lower() for u in clean if u]

        matched = [clean[i] for i, u in enumerate(clean_norm) if u in board]

        if len(matched) < min_required_hits(len(clean_norm)):
            continue

        raw_score = len(matched) / len(clean_norm)
        adjusted_score = raw_score / math.sqrt(len(clean_norm))

        cand = {
            "build_id": b.get("build_id", "UNKNOWN"),
            "build_name": b.get("name", "UNKNOWN"),
            "matched_units": matched,
            "matched": len(matched),
            "size": len(clean_norm),
            "score": round(adjusted_score, 4),
        }

        if best is None:
            best = cand
        else:
            if (cand["score"], cand["matched"], cand["size"]) > (best["score"], best["matched"], best["size"]):
                best = cand

    return best

def identify_build(board_units: list[str], builds: list[dict]):
    """
    2 lépcsős build azonosítás (kulcs unitokkal):
    1) kulcs 4 alapján előszűrés
    2) ha több jelölt van, a maradék unitok alapján dönt

    Tie-break sorrend:
    - key_hits
    - key_ratio
    - score
    - matched
    - kisebb size
    """

    board = set(u.strip().lower() for u in board_units if u)

    best = None
    best_from_key_pool = False

    for b in builds:
        units = b.get("units", [])
        if not units:
            continue

        clean = list(dict.fromkeys(units))
        clean_norm = [u.strip().lower() for u in clean if u]

        size = len(clean_norm)
        if size == 0:
            continue

        key_n = min(KEY_UNITS_N, size)
        key_units_norm = clean_norm[:key_n]

        key_hits = 0
        for u in key_units_norm:
            if u in board:
                key_hits += 1

        key_ratio = key_hits / key_n if key_n > 0 else 0.0
        is_key_ok = (key_hits >= KEY_UNITS_MIN_HITS)

        matched_units = [clean[i] for i, u in enumerate(clean_norm) if u in board]
        matched = len(matched_units)

        if matched < min_required_hits(size):
            continue

        raw_score = matched / size
        adjusted_score = raw_score / math.sqrt(size)

        cand = {
            "build_id": b.get("build_id", "UNKNOWN"),
            "build_name": b.get("name", "UNKNOWN"),
            "matched_units": matched_units,
            "matched": matched,
            "size": size,
            "score": round(adjusted_score, 4),
            "key_hits": key_hits,
            "key_n": key_n,
            "key_ratio": round(key_ratio, 4),
        }

        if best is None:
            best = cand
            best_from_key_pool = is_key_ok
            continue

        if best_from_key_pool and not is_key_ok:
            continue

        if (not best_from_key_pool) and is_key_ok:
            best = cand
            best_from_key_pool = True
            continue

        cand_tuple = (cand["key_hits"], cand["key_ratio"], cand["score"], cand["matched"], -cand["size"])
        best_tuple = (best["key_hits"], best["key_ratio"], best["score"], best["matched"], -best["size"])

        if cand_tuple > best_tuple:
            best = cand

    return best

def write_jsonl_line(f, obj: dict):
    f.write(json.dumps(obj, ensure_ascii=False) + "\n")


# -------------------------------------------------
# MAIN
# -------------------------------------------------
def main():
    ensure_dirs()

    # build list + debug
    builds = load_json(BUILDS_PATH)
    print("[DEBUG] BUILDS_PATH =", BUILDS_PATH)
    print("[DEBUG] builds count =", len(builds))
    print("[DEBUG] first build =", builds[0] if builds else None)

    total_matches = 0
    skipped_wrong_set = 0
    skipped_bad_match = 0

    total_players_seen = 0
    total_pairs_written = 0

    build_counter = Counter()
    unknown_count = 0
    known_count = 0

    with open(OUT_PATH, "w", encoding="utf-8") as out_f:
        for match_path in iter_json_files(RAW_DIR):
            try:
                match = load_json(match_path)
            except Exception as e:
                print(f"[SKIP] Nem tudtam olvasni: {match_path} -> {e}")
                continue

            info = match.get("info", {})
            meta = match.get("metadata", {})
            match_id = meta.get("match_id", os.path.splitext(os.path.basename(match_path))[0])

            # --- Set16 filter ---
            if info.get("tft_set_number") != 16:
                skipped_wrong_set += 1
                continue

            participants = info.get("participants", [])
            total_players_seen += len(participants)

            # Must: everybody must have a placement (1..8)
            placement_map = {}
            ok = True
            for p in participants:
                pl = p.get("placement")
                if pl is None:
                    ok = False
                    break
                try:
                    pl = int(pl)
                except Exception:
                    ok = False
                    break
                placement_map[pl] = p

            # Required: 1..8 all places (if not, skip)
            for need in range(1, 9):
                if need not in placement_map:
                    ok = False
                    break

            if not ok:
                skipped_bad_match += 1
                continue

            total_matches += 1

            game_dt = info.get("game_datetime")
            queue_id = info.get("queue_id") or info.get("queueId")

            # 4 duo: (1,2), (3,4), (5,6), (7,8)
            pair_defs = [
                (1, 2, 1),
                (3, 4, 2),
                (5, 6, 3),
                (7, 8, 4),
            ]

            for a_pl, b_pl, team_rank in pair_defs:
                a = placement_map[a_pl]
                b = placement_map[b_pl]

                members = []
                for p in (a, b):
                    riot_name = p.get("riotIdGameName")
                    tagline = p.get("riotIdTagline")
                    puuid = p.get("puuid")
                    placement = int(p.get("placement"))

                    units = p.get("units", [])
                    board_units = [u.get("character_id") for u in units if u.get("character_id")]

                    best = identify_build(board_units, builds)
                    if best is None:
                        best = {
                            "build_id": "UNKNOWN",
                            "build_name": "UNKNOWN",
                            "matched_units": [],
                            "matched": 0,
                            "size": 0,
                            "score": 0.0,
                        }

                    # build stat
                    bid = best["build_id"]
                    build_counter[bid] += 1
                    if bid == "UNKNOWN":
                        unknown_count += 1
                    else:
                        known_count += 1

                    members.append({
                        "riotIdGameName": riot_name,
                        "riotIdTagline": tagline,
                        "puuid": puuid,
                        "placement": placement,           # 1..8 (egyéni)
                        "team_rank": team_rank,           # 1..4 (csapat)
                        "build_id": best["build_id"],
                        "build_name": best["build_name"],
                        "score": best["score"],
                        "matched": best["matched"],
                        "size": best["size"],
                        "matched_units": best["matched_units"],
                    })

                out_obj = {
                    "match_id": match_id,
                    "game_datetime": game_dt,
                    "queue_id": queue_id,
                    "team_rank": team_rank,        # 1..4  (“final placement”)
                    "team_bucket": team_rank,      # our bucket = team_rank
                    "pair_key": f"{a_pl}-{b_pl}",  # debug: placement pairs
                    "members": members
                }

                write_jsonl_line(out_f, out_obj)
                total_pairs_written += 1

    print("\n[DONE] Done.")
    print(f"  Set16 matches processed: {total_matches}")
    print(f"  SKIP (not Set16): {skipped_wrong_set}")
    print(f"  SKIP (faulty placement/missing 1..8): {skipped_bad_match}")
    print(f"  Players seen (all participant list lenght added together): {total_players_seen}")
    print(f"  Pair rows written (match*4 expected): {total_pairs_written}")
    print(f"  Output: {OUT_PATH}")

    print("\n[BUILD STATS] (player level, 2 player/pair)")
    print(f"  Known build (not UNKNOWN): {known_count}")
    print(f"  UNKNOWN: {unknown_count}")
    total_classified = known_count + unknown_count
    if total_classified > 0:
        print(f"  UNKNOWN ratio: {unknown_count / total_classified:.2%}")

    print("\n[TOP 15 BUILD_ID]")
    for bid, cnt in build_counter.most_common(15):
        print(f"  {bid}: {cnt}")


if __name__ == "__main__":
    main()


