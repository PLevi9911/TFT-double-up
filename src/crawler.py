from __future__ import annotations

import sys
from pathlib import Path
import random

# add project root to PYTHONPATH (so "import config..." always works)
PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

import os
import json
import time
from collections import deque
from pathlib import Path
from typing import Any, Dict, List, Optional, Set

import requests

import config.crawl_config as cfg


API_KEY = os.getenv("RIOT_API_KEY")
if not API_KEY:
    raise SystemExit(
        "Hiányzik a RIOT_API_KEY env var.\n"
        "PowerShell (tartós): setx RIOT_API_KEY \"RGAPI-...\"\n"
        "CMD (csak erre az ablakra): set RIOT_API_KEY=RGAPI-...\n"
        "Utána nyiss új terminált és próbáld újra."
    )

HEADERS = {"X-Riot-Token": API_KEY}


def base(region: str) -> str:
    return f"https://{region}.api.riotgames.com"


#def riot_get_json(url: str, params: Optional[Dict[str, Any]] = None, max_retries: int = 7) -> Any:
    for attempt in range(max_retries):
        resp = requests.get(url, headers=HEADERS, params=params, timeout=25)

        if resp.status_code == 200:
            return resp.json()

        if resp.status_code == 429:
            retry_after = resp.headers.get("Retry-After")
            wait = float(retry_after) if retry_after else (8 + attempt * 4)
            print(f"[RATE LIMIT] 429 – waiting {wait:.1f}s")
            time.sleep(wait)
            continue

        if resp.status_code in (500, 502, 503, 504):
            wait = 1.5 + attempt
            print(f"[SERVER] {resp.status_code} – retry in {wait:.1f}s")
            time.sleep(wait)
            continue

        if resp.status_code in (401, 403):
            raise RuntimeError(
                f"Auth error {resp.status_code}. Valószínű lejárt/rossz a RIOT_API_KEY.\n"
                f"Response: {resp.text[:200]}"
            )

        raise RuntimeError(f"HTTP {resp.status_code}: {resp.text[:200]} @ {url}")

    raise RuntimeError(f"Max retries exceeded @ {url}")
#server 500 error change

def riot_get_json(url: str, params: Optional[Dict[str, Any]] = None, max_retries: int = 9) -> Any:
    """
    Robusztusabb hívás:
    - 429: Retry-After tiszteletben tartása
    - 5xx: exponenciális backoff + jitter + 'circuit breaker' jelleg
    """
    last_status = None
    for attempt in range(max_retries):
        try:
            resp = requests.get(url, headers=HEADERS, params=params, timeout=35)
        except requests.RequestException as e:
            # Hálózati hiba -> backoff
            wait = min(60.0, 2.0 * (2 ** attempt)) + random.uniform(0, 1.0)
            print(f"[NET] {type(e).__name__} – retry in {wait:.1f}s")
            time.sleep(wait)
            continue

        last_status = resp.status_code

        if resp.status_code == 200:
            return resp.json()

        if resp.status_code == 429:
            retry_after = resp.headers.get("Retry-After")
            # Riot néha nem ad Retry-After-t -> legyen konzervatív
            base_wait = float(retry_after) if retry_after else (12 + attempt * 6)
            wait = min(120.0, base_wait) + random.uniform(0, 1.5)
            print(f"[RATE LIMIT] 429 – waiting {wait:.1f}s")
            time.sleep(wait)
            continue

        if resp.status_code in (500, 502, 503, 504):
            # Exponenciális backoff + jitter, plafonnal
            wait = min(90.0, 2.0 * (2 ** attempt)) + random.uniform(0, 2.0)
            print(f"[SERVER] {resp.status_code} – retry in {wait:.1f}s")
            time.sleep(wait)
            continue

        if resp.status_code in (401, 403):
            raise RuntimeError(
                f"Auth error {resp.status_code}. Valószínű lejárt/rossz a RIOT_API_KEY.\n"
                f"Response: {resp.text[:200]}"
            )

        raise RuntimeError(f"HTTP {resp.status_code}: {resp.text[:200]} @ {url}")

    raise RuntimeError(f"Max retries exceeded (last_status={last_status}) @ {url}")

def account_by_riot_id(riot_id: str) -> Dict[str, Any]:
    # /riot/account/v1/accounts/by-riot-id/{gameName}/{tagLine} :contentReference[oaicite:2]{index=2}
    game, tag = riot_id.split("#", 1)
    url = f"{base(cfg.REGIONAL_ROUTING)}/riot/account/v1/accounts/by-riot-id/{game}/{tag}"
    return riot_get_json(url)


def match_ids_by_puuid(puuid: str, count: int) -> List[str]:
    # /tft/match/v1/matches/by-puuid/{puuid}/ids :contentReference[oaicite:3]{index=3}
    url = f"{base(cfg.REGIONAL_ROUTING)}/tft/match/v1/matches/by-puuid/{puuid}/ids"
    return riot_get_json(url, params={"count": count})


def match_detail(match_id: str) -> Dict[str, Any]:
    # /tft/match/v1/matches/{matchId} :contentReference[oaicite:4]{index=4}
    url = f"{base(cfg.REGIONAL_ROUTING)}/tft/match/v1/matches/{match_id}"
    return riot_get_json(url)


def load_state() -> Dict[str, Any]:
    p = Path(cfg.STATE_PATH)
    if p.exists():
        return json.loads(p.read_text(encoding="utf-8"))
    return {
        "seen_match_ids": [],
        "seen_puuids": [],
        "queue_puuids": [],
        "kept_match_ids": [],
        "kept_count": 0,
        "debug_queue_ids_seen": {}
    }


def save_state(state: Dict[str, Any]) -> None:
    Path(cfg.STATE_PATH).parent.mkdir(parents=True, exist_ok=True)
    Path(cfg.STATE_PATH).write_text(json.dumps(state, ensure_ascii=False, indent=2), encoding="utf-8")


def raw_path(match_id: str) -> Path:
    return Path(cfg.RAW_DIR) / f"{match_id}.json"


def has_raw(match_id: str) -> bool:
    return raw_path(match_id).exists()


def write_raw(match_id: str, payload: Dict[str, Any]) -> None:
    Path(cfg.RAW_DIR).mkdir(parents=True, exist_ok=True)
    raw_path(match_id).write_text(json.dumps(payload, ensure_ascii=False), encoding="utf-8")


def get_game_version(m: Dict[str, Any]) -> str:
    return str(m.get("info", {}).get("game_version", ""))


def get_queue_id(m: Dict[str, Any]) -> Optional[int]:
    qid = m.get("info", {}).get("queue_id")
    return qid if isinstance(qid, int) else None


import re

def is_target_patch(m):
    gv = get_game_version(m)
    # Riot match JSON-ban így van: <Releases/16.1>
    m_ = re.search(r"<Releases/(\d+\.\d+)>", gv)
    if m_:
        return m_.group(1) == cfg.PATCH_PREFIX
    # fallback, ha a formátum változna
    return cfg.PATCH_PREFIX in gv


def is_double_up(m: Dict[str, Any]) -> bool:
    qid = get_queue_id(m)
    return qid in cfg.DOUBLE_UP_QUEUE_IDS


def extract_puuids(m: Dict[str, Any]) -> List[str]:
    parts = m.get("info", {}).get("participants", [])
    puuids: List[str] = []
    for p in parts:
        pu = p.get("puuid")
        if pu:
            puuids.append(pu)
    return puuids


def crawl(seed_riot_ids: List[str]) -> None:
    state = load_state()

    seen_match_ids: Set[str] = set(state["seen_match_ids"])
    seen_puuids: Set[str] = set(state["seen_puuids"])
    kept_match_ids: Set[str] = set(state["kept_match_ids"])
    debug_queue_ids_seen: Dict[str, int] = dict(state.get("debug_queue_ids_seen", {}))

    q = deque(state["queue_puuids"])
    kept_count = int(state.get("kept_count", len(kept_match_ids)))

    # Seed RiotID -> PUUID -> queue
    for rid in seed_riot_ids:
        acc = account_by_riot_id(rid)
        puuid = acc["puuid"]
        if puuid not in seen_puuids:
            seen_puuids.add(puuid)
            q.append(puuid)

    print(f"Start crawl. patch={cfg.PATCH_PREFIX} queueIds={sorted(cfg.DOUBLE_UP_QUEUE_IDS)}")
    print(f"RAW_DIR={cfg.RAW_DIR}")
    print(f"STATE={cfg.STATE_PATH}")
    print(f"Queue={len(q)} kept={kept_count}/{cfg.TARGET_MATCHES}")

    last_saved_at_kept = kept_count

    while q and kept_count < cfg.TARGET_MATCHES:
        puuid = q.popleft()

        try:
            mids = match_ids_by_puuid(puuid, cfg.MATCHLIST_COUNT_PER_PLAYER)
        except Exception as e:
            print(f"[WARN] matchlist fail {puuid[:8]}…: {e}")
            time.sleep(cfg.SLEEP_SECONDS)
            continue

        for mid in mids:
            if kept_count >= cfg.TARGET_MATCHES:
                break
            if mid in seen_match_ids:
                continue

            seen_match_ids.add(mid)

            # match detail (cache)
            try:
                if has_raw(mid):
                    m = json.loads(raw_path(mid).read_text(encoding="utf-8"))
                else:
                    m = match_detail(mid)
                    write_raw(mid, m)
            except Exception as e:
                print(f"[WARN] match detail fail {mid}: {e}")
                time.sleep(cfg.SLEEP_SECONDS)
                continue

            # Debug: queueId eloszlás (segít belőni a Double Up queueId-t)
            qid = get_queue_id(m)
            if qid is not None:
                k = str(qid)
                debug_queue_ids_seen[k] = debug_queue_ids_seen.get(k, 0) + 1

            # Szűrés: patch + Double Up
            if not is_target_patch(m):
                continue
            if not is_double_up(m):
                continue

            # Keep
            if mid not in kept_match_ids:
                kept_match_ids.add(mid)
                kept_count += 1
                gv = get_game_version(m)
                print(f"[OK] kept {kept_count}/{cfg.TARGET_MATCHES}  qid={qid}  gv={gv}  match={mid}")

            # Snowball: résztvevők queue-ba
            for pu in extract_puuids(m):
                if len(q) >= cfg.MAX_QUEUE_SIZE:
                    break
                if pu not in seen_puuids:
                    seen_puuids.add(pu)
                    q.append(pu)

            time.sleep(cfg.SLEEP_SECONDS)

            # időnként mentsünk state-et
            if kept_count - last_saved_at_kept >= cfg.SAVE_EVERY_N_KEPT:
                state_out = {
                    "seen_match_ids": list(seen_match_ids),
                    "seen_puuids": list(seen_puuids),
                    "queue_puuids": list(q),
                    "kept_match_ids": list(kept_match_ids),
                    "kept_count": kept_count,
                    "debug_queue_ids_seen": debug_queue_ids_seen,
                }
                save_state(state_out)
                last_saved_at_kept = kept_count
                print(f"[SAVE] state saved. queue={len(q)} seen_matches={len(seen_match_ids)}")

    # Final save
    state_out = {
        "seen_match_ids": list(seen_match_ids),
        "seen_puuids": list(seen_puuids),
        "queue_puuids": list(q),
        "kept_match_ids": list(kept_match_ids),
        "kept_count": kept_count,
        "debug_queue_ids_seen": debug_queue_ids_seen,
    }
    save_state(state_out)

    print("Done.")
    print(f"Kept matches: {kept_count}")
    print(f"Queue remaining: {len(q)}")
    print("QueueId debug counts (top 10):")
    top = sorted(debug_queue_ids_seen.items(), key=lambda x: x[1], reverse=True)[:10]
    for k, v in top:
        print(f"  queue_id={k}  count={v}")


if __name__ == "__main__":
    import sys
    seeds = sys.argv[1:]
    if not seeds:
        raise SystemExit('Add meg a seed Riot ID-kat: python src/crawler.py "Lewking#EUNE" "zBeno#EUNE"')
    crawl(seeds)
