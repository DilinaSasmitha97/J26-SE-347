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
