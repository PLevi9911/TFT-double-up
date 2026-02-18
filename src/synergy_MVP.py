import json
import os
import math
from typing import Dict, Any, List, Tuple

import numpy as np
import pandas as pd
import matplotlib.pyplot as plt


# =========================================================
# 0) SETTINGS
# =========================================================

PAIR_FILE = r"C:\Users\Levi\Documents\tft_duo_project\data\processed\pair_summaries_S.jsonl"
OUT_DIR = r"C:\Users\Levi\Documents\tft_duo_project\output\synergy"

# Double Up queue_id: 1160
DOUBLE_UP_QUEUE_ID = 1160

# Minimum games
MIN_GAMES = 30

# Empirical Bayes shrink “m” parameter
EB_M = 200

# Top N for plot
TOPN = 10


# =========================================================
# 1) HELPERS
# =========================================================

def ensure_dir(path: str) -> None:
    os.makedirs(path, exist_ok=True)

def read_jsonl(path: str) -> List[Dict[str, Any]]:
    rows = []
    with open(path, "r", encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            rows.append(json.loads(line))
    return rows

def safe_get_build_name(member: Dict[str, Any]) -> str:
    # nálad van build_name
    name = member.get("build_name")
    if name is None or name == "" or str(name).upper() == "UNKNOWN":
        # fallback: ID
        bid = member.get("build_id", "UNKNOWN")
        return f"UNKNOWN({bid})"
    return str(name)

def canonical_pair(a: str, b: str) -> Tuple[str, str]:
    # kanonikus rendezés: ugyanaz a pár mindig ugyanúgy nézzen ki
    return (a, b) if a <= b else (b, a)

def team_rank_to_points(team_rank: int) -> int:
    """
    Double Up-ban has 4 teams.
    team_rank: 1..4 (1 is best)
    Pont: 4..1 (the more, the better)
    """
    r = int(team_rank)
    return 5 - r  # 1->4, 2->3, 3->2, 4->1

def empirical_bayes(mean_i: float, n_i: int, global_mean: float, m: float) -> float:
    """
    EB shrink: (n*mean + m*global_mean) / (n+m)
    small n -> pulls to global, big n -> close to own mean
    """
    if n_i <= 0:
        return global_mean
    return (n_i * mean_i + m * global_mean) / (n_i + m)

def clip01(x: float) -> float:
    return max(0.0, min(1.0, x))


# =========================================================
# 2) LOADING + FLATTEN (PAIR LEVEL)
# =========================================================

def build_pair_dataframe(rows: List[Dict[str, Any]]) -> pd.DataFrame:
    out = []
    for r in rows:
        # queue filter
        if r.get("queue_id") != DOUBLE_UP_QUEUE_ID:
            continue

        members = r.get("members", [])
        if not isinstance(members, list) or len(members) != 2:
            continue

        b1 = safe_get_build_name(members[0])
        b2 = safe_get_build_name(members[1])
        c1, c2 = canonical_pair(b1, b2)

        team_rank = r.get("team_rank")
        if team_rank is None:
            continue

        out.append({
            "match_id": r.get("match_id"),
            "game_datetime": r.get("game_datetime"),
            "pair_key": r.get("pair_key"),
            "team_rank": int(team_rank),               # 1..4
            "team_points": team_rank_to_points(team_rank),  # 4..1
            "team_bucket": r.get("team_bucket"),
            "build_a": c1,
            "build_b": c2,
        })

    df = pd.DataFrame(out)
    return df


# =========================================================
# 3) MARGINALS (BUILD-LEVEL BASIC PROBABILITY)
# =========================================================

def compute_build_marginals(df_pairs: pd.DataFrame) -> pd.DataFrame:
    """
    Calculating on build level:
      - how many matches included (any partner)
      - top1/top2 ratio (team_rank)
      - average team_points / team_rank
    """
    # separate pairs “long”: 1 row = (match, build)
    long_rows = []
    for _, row in df_pairs.iterrows():
        for b in (row["build_a"], row["build_b"]):
            long_rows.append({
                "build": b,
                "team_rank": row["team_rank"],
                "team_points": row["team_points"],
            })
    df_long = pd.DataFrame(long_rows)

    g = df_long.groupby("build", as_index=False).agg(
        games=("build", "count"),
        avg_team_rank=("team_rank", "mean"),
        avg_team_points=("team_points", "mean"),
        top1=("team_rank", lambda s: float((s == 1).mean())),
        top2=("team_rank", lambda s: float((s <= 2).mean())),
        top3=("team_rank", lambda s: float((s <= 3).mean())),
    )
    return g


# =========================================================
# 4) PAIR SYNERGY METRICS
# =========================================================

def compute_pair_synergies(df_pairs: pd.DataFrame, df_marg: pd.DataFrame) -> pd.DataFrame:
    """
    Pair level stats:
      - games
      - avg_team_rank, avg_team_points
      - top1/top2/top3 arány
      - EB_shrunk_points (Empirical Bayes)
      - Lift_top2: observed_top2 / (pA_top2 * pB_top2)
      - Lift_top1: observed_top1 / (pA_top1 * pB_top1)
      - log_lift_top2, log_lift_top1
      - synergy_score (combined)
    """
    # Marginal lookup
    marg = df_marg.set_index("build").to_dict(orient="index")

    def get_marg(build: str) -> Dict[str, float]:
        return marg.get(build, {"top1": 0.0, "top2": 0.0, "top3": 0.0, "avg_team_points": df_pairs["team_points"].mean(), "games": 0})

    # Pair aggregations
    g = df_pairs.groupby(["build_a", "build_b"], as_index=False).agg(
        games=("team_rank", "count"),
        avg_team_rank=("team_rank", "mean"),
        avg_team_points=("team_points", "mean"),
        top1=("team_rank", lambda s: float((s == 1).mean())),
        top2=("team_rank", lambda s: float((s <= 2).mean())),
        top3=("team_rank", lambda s: float((s <= 3).mean())),
    )

    global_mean_points = float(df_pairs["team_points"].mean())

    # EB + lift calculation
    eb_points = []
    lift_top2 = []
    lift_top1 = []
    log_lift_top2 = []
    log_lift_top1 = []
    synergy_score = []

    for _, row in g.iterrows():
        a = row["build_a"]
        b = row["build_b"]
        n = int(row["games"])

        # Empirical Bayes shrinkelt point
        eb = empirical_bayes(float(row["avg_team_points"]), n, global_mean_points, EB_M)
        eb_points.append(eb)

        ma = get_marg(a)
        mb = get_marg(b)

        # expected baseline (independence condition)
        exp_top2 = clip01(float(ma["top2"])) * clip01(float(mb["top2"]))
        exp_top1 = clip01(float(ma["top1"])) * clip01(float(mb["top1"]))

        obs_top2 = clip01(float(row["top2"]))
        obs_top1 = clip01(float(row["top1"]))

        # Lift: if >1 then “better together, then expected”
        lt2 = (obs_top2 / exp_top2) if exp_top2 > 1e-9 else np.nan
        lt1 = (obs_top1 / exp_top1) if exp_top1 > 1e-9 else np.nan

        lift_top2.append(lt2)
        lift_top1.append(lt1)

        # Log-lift for stable ranking
        llt2 = math.log(lt2) if (lt2 is not np.nan and lt2 is not None and not (isinstance(lt2, float) and np.isnan(lt2)) and lt2 > 1e-12) else np.nan
        llt1 = math.log(lt1) if (lt1 is not np.nan and lt1 is not None and not (isinstance(lt1, float) and np.isnan(lt1)) and lt1 > 1e-12) else np.nan

        log_lift_top2.append(llt2)
        log_lift_top1.append(llt1)

        # Combined synergy score:
        # - EB point (stabil performance)
        # - + log-lift (if “together extra”)
        # - and a “sample number factor” (don't have a 3-game miracle)
        sample_factor = math.sqrt(n) / math.sqrt(n + EB_M)
        score = (eb * 1.0) + (0.30 * (llt2 if not np.isnan(llt2) else 0.0)) + (0.15 * (llt1 if not np.isnan(llt1) else 0.0))
        score *= sample_factor
        synergy_score.append(score)

    g["eb_points"] = eb_points
    g["lift_top2"] = lift_top2
    g["lift_top1"] = lift_top1
    g["log_lift_top2"] = log_lift_top2
    g["log_lift_top1"] = log_lift_top1
    g["synergy_score"] = synergy_score

    return g


# =========================================================
# 5) FIGURES
# =========================================================

def plot_top_bar(df: pd.DataFrame, col: str, title: str, out_path: str, topn: int = TOPN) -> None:
    d = df.sort_values(col, ascending=False).head(topn).copy()
    # short label: "A + B"
    d["pair"] = d["build_a"] + "  +  " + d["build_b"]

    plt.figure(figsize=(12, max(6, topn * 0.35)))
    plt.barh(d["pair"][::-1], d[col][::-1])
    plt.title(title)
    plt.xlabel(col)
    plt.tight_layout()
    plt.savefig(out_path, dpi=200)
    plt.close()

def plot_scatter_count_vs_perf(df: pd.DataFrame, out_path: str) -> None:
    d = df.copy()
    plt.figure(figsize=(10, 6))
    plt.scatter(d["games"], d["eb_points"], alpha=0.6)
    plt.title("Pair: number of matches vs EB-shrinked performance (team_points)")
    plt.xlabel("games")
    plt.ylabel("eb_points (1..4)")
    plt.tight_layout()
    plt.savefig(out_path, dpi=200)
    plt.close()

def plot_heatmap_top_builds(df_pairs: pd.DataFrame, out_path: str, top_builds: int = 18) -> None:
    """
    Basic heatmap matrix:
    - Select the top N most common build based on marginal
    - mátrix cells = average team_points on (i,j) pairs
    """
    # build frequency
    counts = pd.concat([df_pairs["build_a"], df_pairs["build_b"]]).value_counts()
    top = list(counts.head(top_builds).index)

    # filter on top builds
    df = df_pairs[(df_pairs["build_a"].isin(top)) & (df_pairs["build_b"].isin(top))].copy()

    # pivot: mean points
    piv = df.pivot_table(index="build_a", columns="build_b", values="team_points", aggfunc="mean")

    # fill the missings
    piv = piv.reindex(index=top, columns=top)
    mat = piv.values

    plt.figure(figsize=(10, 8))
    plt.imshow(mat, aspect="auto")
    plt.title(f"Top {top_builds} build pairs – agerage team_points (4=better)")
    plt.xticks(range(len(top)), top, rotation=90)
    plt.yticks(range(len(top)), top)
    plt.colorbar(label="avg team_points")
    plt.tight_layout()
    plt.savefig(out_path, dpi=200)
    plt.close()


# =========================================================
# 6) MAIN
# =========================================================

def main():
    ensure_dir(OUT_DIR)

    print(f"[LOAD] {PAIR_FILE}")
    rows = read_jsonl(PAIR_FILE)
    print(f"[LOAD] rows: {len(rows)}")

    df_pairs = build_pair_dataframe(rows)
    print(f"[PAIRS] filtered rows (Double Up queue): {len(df_pairs)}")

    if df_pairs.empty:
        print("[ERROR] Empty df_pairs – something is not right.")
        return

    # marginals
    df_marg = compute_build_marginals(df_pairs)

    # synergies
    df_syn = compute_pair_synergies(df_pairs, df_marg)

    # alap szűrés ranglistához
    df_rank = df_syn[df_syn["games"] >= MIN_GAMES].copy()

    # mentsük ki táblákba
    df_pairs.to_csv(os.path.join(OUT_DIR, "pairs_raw.csv"), index=False, encoding="utf-8-sig")
    df_marg.sort_values("games", ascending=False).to_csv(os.path.join(OUT_DIR, "build_marginals.csv"), index=False, encoding="utf-8-sig")
    df_syn.sort_values("synergy_score", ascending=False).to_csv(os.path.join(OUT_DIR, "pair_synergies_all.csv"), index=False, encoding="utf-8-sig")
    df_rank.sort_values("synergy_score", ascending=False).to_csv(os.path.join(OUT_DIR, "pair_synergies_ranked_min_games.csv"), index=False, encoding="utf-8-sig")

    print(f"[SAVE] CSVs saved to: {OUT_DIR}")

    # ábrák
    plot_top_bar(df_rank, "synergy_score", f"TOP pairs synergy_score (min {MIN_GAMES} game)", os.path.join(OUT_DIR, "top_synergy_score.png"))
    plot_top_bar(df_rank, "eb_points", f"TOP pairs EB-shrunken performance (min {MIN_GAMES} game)", os.path.join(OUT_DIR, "top_eb_points.png"))
    plot_top_bar(df_rank, "top2", f"TOP pairs Top2 ratio (min {MIN_GAMES} game)", os.path.join(OUT_DIR, "top_top2_rate.png"))
    plot_top_bar(df_rank, "lift_top2", f"TOP pairs Lift Top2 (min {MIN_GAMES} game)", os.path.join(OUT_DIR, "top_lift_top2.png"))
    plot_top_bar(df_rank, "lift_top1", f"TOP pairs Lift Top1 (min {MIN_GAMES} game)", os.path.join(OUT_DIR, "top_lift_top1.png"))

    plot_scatter_count_vs_perf(df_syn, os.path.join(OUT_DIR, "scatter_games_vs_eb_points.png"))
    plot_heatmap_top_builds(df_pairs, os.path.join(OUT_DIR, "heatmap_top_builds.png"))

    print("[DONE] Ready! Look at the output/synergy folder.")


if __name__ == "__main__":
    main()
