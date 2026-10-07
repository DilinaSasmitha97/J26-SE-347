"""
Build the committed M4 benchmark sample from the official M4 files.

Source: the M4 competition dataset (Makridakis, Spiliotis & Assimakopoulos,
2020), files from https://github.com/Mcompetitions/M4-methods/tree/master/Dataset
downloaded into benchmark_data/m4_raw/ (git-ignored, ~100 MB):

    Train/Monthly-train.csv   Test/Monthly-test.csv   M4-info.csv

Selection, fixed in advance:
  - population: all 48,000 MONTHLY series (M4 has 100,000 series in total)
  - sample: SAMPLE_SIZE series drawn uniformly at random with seed SEED
  - each series = official train + test values concatenated, then truncated to
    its last TRUNCATE_TO observations, to match the 12-36 month histories of
    the small business datasets this component targets

Output: benchmark_data/m4_monthly_sample.csv (series_id, category,
original_length, start_date, values). Re-running reproduces it exactly.

Two samples are used:
  m4_monthly_sample.csv        seed 2026 - DEVELOPMENT (design decisions were
                               checked against it after its first evaluation)
  m4_monthly_test_seed2027.csv seed 2027, drawn from the 47,900 series NOT in
                               the development sample - HELD-OUT TEST

Run:  python benchmark_data/prepare_m4_sample.py
      python benchmark_data/prepare_m4_sample.py --seed 2027
          --exclude benchmark_data/m4_monthly_sample.csv
          --out benchmark_data/m4_monthly_test_seed2027.csv
"""

import argparse
import csv
import random
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
RAW = HERE / "m4_raw"
OUT = HERE / "m4_monthly_sample.csv"

SEED = 2026
SAMPLE_SIZE = 100
TRUNCATE_TO = 36
EXPECTED_MONTHLY_SERIES = 48_000

csv.field_size_limit(10**7)


def _read_series(path: Path) -> dict:
    out = {}
    with path.open(encoding="utf-8", newline="") as fh:
        reader = csv.reader(fh)
        next(reader)  # header: "V1","V2",...
        for row in reader:
            if not row:
                continue
            out[row[0]] = [float(v) for v in row[1:] if v not in ("", "NA")]
    return out


def main() -> int:
    parser = argparse.ArgumentParser(description="Build an M4 monthly sample")
    parser.add_argument("--seed", type=int, default=SEED)
    parser.add_argument("--size", type=int, default=SAMPLE_SIZE)
    parser.add_argument("--exclude", action="append", default=[],
                        help="existing sample CSV whose series must not be reused (repeatable)")
    parser.add_argument("--ids-from", help="reuse exactly the series of this sample CSV "
                        "(e.g. the development series at a different length)")
    parser.add_argument("--truncate", type=int, default=TRUNCATE_TO,
                        help=f"keep the last N observations (default {TRUNCATE_TO})")
    parser.add_argument("--out", default=str(OUT))
    args = parser.parse_args()
    out_path = Path(args.out)

    paths = {name: RAW / name for name in ("Monthly-train.csv", "Monthly-test.csv", "M4-info.csv")}
    missing = [n for n, p in paths.items() if not p.exists()]
    if missing:
        print(f"Missing raw files in {RAW}: {missing}")
        return 2

    train = _read_series(paths["Monthly-train.csv"])
    test = _read_series(paths["Monthly-test.csv"])
    if len(train) != EXPECTED_MONTHLY_SERIES or len(test) != EXPECTED_MONTHLY_SERIES:
        print(f"Incomplete download: {len(train)} train / {len(test)} test series, "
              f"expected {EXPECTED_MONTHLY_SERIES} each. Re-download and retry.")
        return 2

    info = {}
    with paths["M4-info.csv"].open(encoding="utf-8", newline="") as fh:
        for row in csv.DictReader(fh):
            info[row["M4id"]] = row

    excluded = set()
    for path in args.exclude:
        with open(path, encoding="utf-8", newline="") as fh:
            excluded |= {row["series_id"] for row in csv.DictReader(fh)}
    ids = sorted((s for s in train if s not in excluded), key=lambda s: int(s[1:]))
    if args.ids_from:
        with open(args.ids_from, encoding="utf-8", newline="") as fh:
            sample = sorted((row["series_id"] for row in csv.DictReader(fh)), key=lambda s: int(s[1:]))
    else:
        sample = sorted(random.Random(args.seed).sample(ids, args.size), key=lambda s: int(s[1:]))

    with out_path.open("w", encoding="utf-8", newline="") as fh:
        writer = csv.writer(fh)
        writer.writerow(["series_id", "category", "original_length", "start_date", "values"])
        for sid in sample:
            full = train[sid] + test[sid]
            meta = info.get(sid, {})
            writer.writerow([sid, meta.get("category", ""), len(full),
                             meta.get("StartingDate", ""),
                             " ".join(f"{v:g}" for v in full[-args.truncate:])])

    categories = {}
    for sid in sample:
        c = info.get(sid, {}).get("category", "?")
        categories[c] = categories.get(c, 0) + 1
    print(f"Wrote {out_path.name}: {len(sample)} of {len(ids)} monthly series (seed {args.seed}"
          f"{f', excluding {len(excluded)} already used' if excluded else ''}), "
          f"last {args.truncate} observations each. Categories: {categories}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
