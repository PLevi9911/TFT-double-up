# TFT-double-up

TFT Double Up Synergy Analysis

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
