# Benchmark data

`m4_monthly_sample.csv` — 100 monthly series sampled uniformly at random
(seed 2026) from the 48,000 monthly series of the M4 competition dataset
(Makridakis, Spiliotis & Assimakopoulos, 2020; 100,000 series in total).
Each row is the official train + test values concatenated and truncated to
the last 36 observations, with the M4 id, category, original length and
start date.

Rebuild it exactly:

1. Download `Train/Monthly-train.csv`, `Test/Monthly-test.csv` and
   `M4-info.csv` from https://github.com/Mcompetitions/M4-methods/tree/master/Dataset
   into `benchmark_data/m4_raw/` (git-ignored, ~100 MB).
2. `python benchmark_data/prepare_m4_sample.py`

Used by `evaluate_forecasting.py` as the held-out test set: the forecasting
code was frozen before this sample was first evaluated.

## Spider dev questions (Stage 5 intent benchmark)

`spider_dev_intent.json` — the 1,032 questions of the Spider dev set (Yu et al.,
2018, *Spider: A Large-Scale Human-Labeled Dataset for Complex and Cross-Domain
Semantic Parsing and Text-to-SQL Task*, EMNLP; licence CC BY-SA 4.0), each with
its gold SQL, plus labels derived from that SQL by the fixed rules in
`prepare_spider_intent.py` and a DEV/TEST split by database (seed 2026).

The questions were copied from Member 1's evaluation file
`Dilina/NL TO SQL prototype/predictions_detailed.json` (branch
`dilina-nl-to-sql-prototype-stage-7-database-probing`); only `db_id`,
`difficulty`, `question` and `gold_sql` are kept. Spider's dev set has 1,034
questions; that file has 1,032.

Rebuild it exactly (labels and split are deterministic):

    git show "origin/dilina-nl-to-sql-prototype-stage-7-database-probing:Dilina/NL TO SQL prototype/predictions_detailed.json" > predictions_detailed.json
    python benchmark_data/prepare_spider_intent.py predictions_detailed.json

The label rules and this file were frozen before the classifier was run on any
Spider question (SHA-256 of the frozen file:
`853f412da70320ae0e17d3111763c5c0cdf063ad59d1fdf8137623113fa86794`).
