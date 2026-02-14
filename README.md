# TFT-double-up


This project analyzes build-level synergy in Teamfight Tactics (TFT) Double Up mode. While existing analytics platforms evaluate compositions individually, they do not measure how two builds perform together as a team. Double Up introduces cooperative dynamics that may generate interaction effects beyond individual strength, and this project investigates whether such measurable synergy exists.

Using Riot API match data filtered by patch and queue, each player board is mapped to predefined build templates. Every Double Up team is then represented as an unordered pair of builds, and performance statistics are aggregated at the pair level.

The core analytical framework separates marginal strength from interaction effects. First, each build’s independent strength is estimated using team-level metrics such as Top1 rate, Top2 rate, and average team points (4 for 1st, 1 for 4th). Then, for each build pair, observed performance is compared against an independence-based expectation.

For example, expected Top2 probability under independence is approximated as:
P(A and B) ≈ P(A) * P(B)

where P(A) and P(B) are the marginal Top2 rates of the individual builds.
The ratio of observed to expected performance defines a lift metric, which captures whether the pair performs better or worse than predicted by marginal strength alone.

To reduce small-sample distortion, Empirical Bayes shrinkage is applied:
EB = (n * pair_mean + m * global_mean) / (n + m)
where n is the pair’s sample size and m is a shrinkage parameter. This prevents low-sample outliers from dominating rankings.

A composite synergy score combines:

Shrunk performance (stability), Log-lift (interaction strength), Sample-size weighting

The objective is not simply to rank high win-rate pairs, but to isolate interaction effects to determine whether in Double Up, 1 + 1 can systematically exceed 2.

This is an independent exploratory project focused on applied game analytics, statistical modeling, and balance system analysis.


## Project Structure

tft_duo_project/
config/
crawl_config.py
builds_set16_16.3_S.json
builds_set16_16.3_SA.json
builds_set16_16_all.json

data/
raw/
matches/
16.3/ # raw match JSON files filtered by patch (optional)
archive/
processed/
pair_summaries_S.jsonl
pair_summaries_SA.jsonl
archive/
state/
crawler_state.json
reports/
unit_list/
16.txt

output/
synergy/ # CSVs + plots produced by synergy_MVP

src/
crawler.py
filter_patch_raw.py
make_pair_summaries.py
synergy_MVP.py
test_single_match.py

scripts/
(optional helper .bat files / archives)


## Requirements

- Python 3.10+ recommended
- Riot Games API key (TFT Match API)

Python packages used by the pipeline:
- `requests` (API calls)
- `numpy`, `pandas` (aggregation / stats)
- `matplotlib` (plots)

Install dependencies:

```bash
pip install requests numpy pandas matplotlib


(Optional) you can freeze them into a requirements file:

pip freeze > requirements.txt
pip install -r requirements.txt

CMD (for the current terminal session only):

set RIOT_API_KEY=RGAPI-xxxxxxxx-xxxx-xxxx-xxxx-xxxxxxxxxxxx



## Usage (End-to-End Pipeline)


1) Crawl raw matches (Riot API → data/raw/matches)

Run the crawler with seed Riot IDs:

python src/crawler.py "SomeName#EUW" "AnotherName#EUNE"
