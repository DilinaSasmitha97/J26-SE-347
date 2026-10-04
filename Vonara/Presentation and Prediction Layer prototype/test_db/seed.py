"""
Seed the synthetic multi-tenant MySQL database.

Each tenant's monthly totals come from a KNOWN generating process
(synthetic_data.generate_timeseries: level + trend + seasonality + noise +
injected anomalies). Those totals are then split into individual transactions
- invoices, sales, tickets - with random days, categories, vendors and regions.
The fixture SQL has to aggregate them back, so the rows Component 4 receives
have the realistic shape of a GROUP BY result, while the ground truth (true
monthly totals, anomaly months) is known exactly and saved for evaluation.

Money is split in integer cents, so SUM(amount) per month in MySQL equals the
recorded ground-truth total to the cent.

Usage:
    python test_db/seed.py           build, load into MySQL, verify
    python test_db/seed.py --check   build in memory and verify only (no DB)
"""

import argparse
import calendar
import json
import random
import secrets
import sys
from collections import defaultdict
from datetime import date

import db_config
from db_config import OUTPUT_DIR, admin_connection, database_name, schema_ddl

import synthetic_data as sd  # importable once db_config has set sys.path

SEED = 2026

CATEGORY_WEIGHTS = {"Software": 0.34, "Hardware": 0.18, "Travel": 0.16,
                    "Marketing": 0.20, "Facilities": 0.12}
VENDORS = {
    "Software": ["Atlassian", "Microsoft", "Zoho"],
    "Hardware": ["Dell", "Lenovo", "Singer"],
    "Travel": ["SriLankan Airlines", "PickMe", "Cinnamon Hotels"],
    "Marketing": ["Google Ads", "Meta Ads", "Leo Burnett"],
    "Facilities": ["CEB", "Water Board", "Abans Cleaning"],
}
REGION_WEIGHTS = {"North": 0.20, "South": 0.30, "East": 0.15, "West": 0.35}
PRODUCT_WEIGHTS = {"Basic": 0.30, "Pro": 0.45, "Enterprise": 0.25}
UNIT_PRICE = {"Basic": 45.0, "Pro": 120.0, "Enterprise": 480.0}
SALARY_RANGE = {"Engineering": (150_000, 320_000), "Sales": (90_000, 200_000),
                "Finance": (110_000, 240_000), "HR": (80_000, 160_000),
                "Support": (70_000, 140_000)}
PRIORITY_WEIGHTS = {"Low": 0.35, "Medium": 0.40, "High": 0.20, "Critical": 0.05}
PRIORITY_MEAN_HOURS = {"Low": 30.0, "Medium": 18.0, "High": 8.0, "Critical": 3.0}
FIRST_NAMES = ["Ayesha", "Nuwan", "Dilini", "Kasun", "Tharindu", "Sanduni", "Ishara",
               "Chamath", "Nethmi", "Ravindu", "Hiruni", "Supun", "Malki", "Dinuka"]
LAST_NAMES = ["Perera", "Fernando", "Silva", "Jayasuriya", "Bandara", "Rathnayake",
              "Wickramasinghe", "Gunawardena", "Dissanayake", "Herath"]

# One tenant per behaviour the prediction layer must handle. `anomalies` are
# month offsets; `magnitude` is the injected outlier size in noise sigmas.
TENANTS = {
    "tenant_a": {
        "profile": "Seasonal business: 36 months, trend + 12-month seasonality, 2 expense anomalies",
        "start": (2023, 1), "months": 36, "employees": 40,
        "expenses": dict(level=20_000, trend=90, seasonal=0.25, noise=0.05, anomalies=[11, 29]),
        "sales": dict(level=60_000, trend=400, seasonal=0.20, noise=0.06, anomalies=[]),
        "tickets": dict(level=120, trend=1, seasonal=0.10, noise=0.08, anomalies=[]),
    },
    "tenant_b": {
        "profile": "New business: only 5 months of history",
        "start": (2025, 8), "months": 5, "employees": 6,
        "expenses": dict(level=8_000, trend=200, seasonal=0.0, noise=0.05, anomalies=[]),
        "sales": dict(level=15_000, trend=600, seasonal=0.0, noise=0.06, anomalies=[]),
        "tickets": dict(level=25, trend=1, seasonal=0.0, noise=0.10, anomalies=[]),
    },
    "tenant_c": {
        "profile": "Volatile business: 24 months, heavy noise, injected spikes",
        "start": (2024, 1), "months": 24, "employees": 18,
        "expenses": dict(level=4_000, trend=20, seasonal=0.0, noise=0.35,
                         anomalies=[6, 15, 20], magnitude=2.5),
        "sales": dict(level=25_000, trend=150, seasonal=0.0, noise=0.30,
                      anomalies=[9], magnitude=2.5),
        "tickets": dict(level=60, trend=0, seasonal=0.0, noise=0.25,
                        anomalies=[12], magnitude=2.5),
    },
    "tenant_d": {
        "profile": "Steady grower: 24 months, clean linear growth",
        "start": (2024, 1), "months": 24, "employees": 25,
        "expenses": dict(level=3_500, trend=120, seasonal=0.0, noise=0.03, anomalies=[]),
        "sales": dict(level=45_000, trend=900, seasonal=0.0, noise=0.04, anomalies=[]),
        "tickets": dict(level=40, trend=1.5, seasonal=0.0, noise=0.05, anomalies=[]),
    },
}

# A monthly total is never allowed below this share of the series level: a
# negative spend month is not a business outcome, it is a generator artefact.
FLOOR_SHARE = 0.05

COLUMNS = {
    "expenses": ["expense_id", "tenant_id", "invoice_date", "category", "vendor",
                 "amount", "approved_by_email"],
    "sales": ["sale_id", "tenant_id", "sale_date", "region", "product", "units", "revenue"],
    "employees": ["employee_id", "tenant_id", "full_name", "email", "department",
                  "hire_date", "salary"],
    "support_tickets": ["ticket_id", "tenant_id", "opened_date", "priority",
                        "resolution_hours", "customer_phone"],
}


def _month(start: tuple, offset: int) -> tuple:
    total = start[1] - 1 + offset
    return start[0] + total // 12, total % 12 + 1


def _weighted(rng: random.Random, weights: dict) -> str:
    return rng.choices(list(weights), weights=list(weights.values()))[0]


def _random_day(rng: random.Random, year: int, month: int) -> date:
    return date(year, month, rng.randint(1, calendar.monthrange(year, month)[1]))


def _split_cents(total_cents: int, n: int, rng: random.Random) -> list:
    """Split an exact cent total into n positive parts that sum to it exactly."""
    n = max(1, min(n, total_cents))
    weights = [rng.uniform(0.3, 1.7) for _ in range(n)]
    scale = sum(weights)
    parts = [max(1, int(total_cents * w / scale)) for w in weights]
    parts[-1] += total_cents - sum(parts)
    if parts[-1] < 1:  # only possible if flooring overshot; fold into the largest part
        largest = parts.index(max(parts[:-1]))
        parts[largest] += parts[-1] - 1
        parts[-1] = 1
    return parts


def _series(spec: dict, n: int, seed: int) -> tuple:
    """Monthly values from the known generating process, floored at FLOOR_SHARE."""
    rows, truth = sd.generate_timeseries(
        n_periods=n, level=spec["level"], trend=spec["trend"],
        seasonal_amplitude=spec["seasonal"], noise_pct=spec["noise"],
        anomaly_indices=spec["anomalies"], anomaly_magnitude=spec.get("magnitude", 3.0),
        seed=seed,
    )
    floor = spec["level"] * FLOOR_SHARE
    values, floored = [], []
    for i, row in enumerate(rows):
        v = row["amount"]
        if v < floor:
            floored.append(i)
            v = floor
        values.append(v)
    return values, truth, floored


def build_dataset(seed: int = SEED) -> dict:
    """Generate every table's rows plus the ground truth, deterministically."""
    rng = random.Random(seed)
    tables = {name: [] for name in COLUMNS}
    truth = {"seed": seed, "floor_share": FLOOR_SHARE, "tenants": {}}
    next_id = defaultdict(lambda: 1)

    def new_id(table: str) -> int:
        value = next_id[table]
        next_id[table] += 1
        return value

    for t_index, (tenant, cfg) in enumerate(TENANTS.items()):
        n = cfg["months"]
        months = [_month(cfg["start"], i) for i in range(n)]
        labels = [f"{y:04d}-{m:02d}" for y, m in months]
        last_year, last_month = months[-1]
        period_end = date(last_year, last_month, calendar.monthrange(last_year, last_month)[1])

        # --- employees (PII source: full_name, email) ------------------
        emails = []
        for _ in range(cfg["employees"]):
            first, last = rng.choice(FIRST_NAMES), rng.choice(LAST_NAMES)
            emp_id = new_id("employees")
            email = f"{first.lower()}.{last.lower()}{emp_id}@{tenant.replace('_', '')}.example.com"
            emails.append(email)
            dept = rng.choice(list(SALARY_RANGE))
            low, high = SALARY_RANGE[dept]
            hire = date.fromordinal(rng.randint(date(2018, 1, 1).toordinal(), period_end.toordinal()))
            tables["employees"].append((
                emp_id, tenant, f"{first} {last}", email, dept, hire,
                f"{round(rng.uniform(low, high), -2):.2f}",
            ))

        tenant_truth = {"profile": cfg["profile"], "months": labels}
        base_seed = seed + 100 * t_index

        # --- expenses ------------------------------------------------------
        values, series_truth, floored = _series(cfg["expenses"], n, base_seed + 1)
        monthly_cents = []
        for (year, month), value in zip(months, values):
            cents = int(round(value * 100))
            monthly_cents.append(cents)
            for part in _split_cents(cents, rng.randint(8, 18), rng):
                category = _weighted(rng, CATEGORY_WEIGHTS)
                # ~8% of invoices were never approved: realistic NULLs.
                approver = None if rng.random() < 0.08 else rng.choice(emails)
                tables["expenses"].append((
                    new_id("expenses"), tenant, _random_day(rng, year, month), category,
                    rng.choice(VENDORS[category]), f"{part / 100:.2f}", approver,
                ))
        tenant_truth["expenses"] = _truth_block(cfg["expenses"], series_truth, floored,
                                                [c / 100 for c in monthly_cents], labels)

        # --- sales -----------------------------------------------------------
        values, series_truth, floored = _series(cfg["sales"], n, base_seed + 2)
        monthly_cents = []
        for (year, month), value in zip(months, values):
            cents = int(round(value * 100))
            monthly_cents.append(cents)
            for part in _split_cents(cents, rng.randint(10, 25), rng):
                product = _weighted(rng, PRODUCT_WEIGHTS)
                revenue = part / 100
                tables["sales"].append((
                    new_id("sales"), tenant, _random_day(rng, year, month),
                    _weighted(rng, REGION_WEIGHTS), product,
                    max(1, round(revenue / UNIT_PRICE[product])), f"{revenue:.2f}",
                ))
        tenant_truth["sales"] = _truth_block(cfg["sales"], series_truth, floored,
                                             [c / 100 for c in monthly_cents], labels)

        # --- support tickets (monthly COUNT is the series) ------------------
        values, series_truth, floored = _series(cfg["tickets"], n, base_seed + 3)
        counts = []
        for (year, month), value in zip(months, values):
            count = max(1, int(round(value)))
            counts.append(count)
            for _ in range(count):
                priority = _weighted(rng, PRIORITY_WEIGHTS)
                hours = max(0.25, rng.gammavariate(2.0, PRIORITY_MEAN_HOURS[priority] / 2.0))
                phone = None if rng.random() < 0.05 else f"+9477{rng.randint(0, 9_999_999):07d}"
                tables["support_tickets"].append((
                    new_id("support_tickets"), tenant, _random_day(rng, year, month),
                    priority, f"{hours:.2f}", phone,
                ))
        tenant_truth["tickets"] = _truth_block(cfg["tickets"], series_truth, floored,
                                               counts, labels)

        truth["tenants"][tenant] = tenant_truth

    return {"tables": tables, "truth": truth}


def _truth_block(spec: dict, series_truth: dict, floored: list, actual: list, labels: list) -> dict:
    anomalies = series_truth["anomaly_indices"]
    return {
        "params": {k: spec.get(k) for k in ("level", "trend", "seasonal", "noise", "anomalies",
                                            "magnitude")},
        "monthly_actual": [round(v, 2) for v in actual],
        "clean_signal": series_truth["clean_signal"],
        "anomaly_indices": anomalies,
        "anomaly_months": [labels[i] for i in anomalies],
        "floored_indices": floored,
    }


# ==========================================================================
# Verification
# ==========================================================================


def verify_in_memory(dataset: dict) -> list:
    """Re-aggregate the generated rows and compare them with the ground truth."""
    problems = []
    tables, truth = dataset["tables"], dataset["truth"]["tenants"]

    def monthly(rows, date_idx, value_idx, tenant, count=False):
        acc = defaultdict(int)
        for row in rows:
            if row[1] != tenant:
                continue
            key = row[date_idx].strftime("%Y-%m")
            acc[key] += 1 if count else int(round(float(row[value_idx]) * 100))
        return acc

    for tenant, t in truth.items():
        checks = (
            ("expenses", monthly(tables["expenses"], 2, 5, tenant), t["expenses"], 100),
            ("sales", monthly(tables["sales"], 2, 6, tenant), t["sales"], 100),
            ("tickets", monthly(tables["support_tickets"], 2, 0, tenant, count=True), t["tickets"], 1),
        )
        for name, got, expected, scale in checks:
            want = [int(round(v * scale)) for v in expected["monthly_actual"]]
            have = [got.get(label, 0) for label in t["months"]]
            if have != want:
                problems.append(f"{tenant}.{name}: re-aggregated totals differ from ground truth")
            if any(v <= 0 for v in have):
                problems.append(f"{tenant}.{name}: a month has no positive total")
    for table, rows in tables.items():
        for row in rows:
            if table in ("expenses", "sales") and float(row[5 if table == "expenses" else 6]) <= 0:
                problems.append(f"{table}: non-positive amount in row {row[0]}")
                break
    return problems


def verify_database(truth: dict) -> list:
    """Check the loaded data through the READ-ONLY account, and that it cannot write."""
    import pymysql

    problems = []
    conn = db_config.reader_connection()
    try:
        with conn.cursor() as cur:
            for tenant, t in truth["tenants"].items():
                cur.execute(
                    "SELECT DATE_FORMAT(invoice_date, '%%Y-%%m') AS m, SUM(amount) "
                    "FROM expenses WHERE tenant_id = %s GROUP BY m ORDER BY m", (tenant,))
                got = [float(v) for _, v in cur.fetchall()]
                if got != t["expenses"]["monthly_actual"]:
                    problems.append(f"{tenant}: MySQL monthly expense sums differ from ground truth")
            try:
                cur.execute("DELETE FROM expenses WHERE expense_id = -1")
                problems.append("reader account was able to run DELETE - it must be SELECT-only")
            except pymysql.err.OperationalError:
                pass  # expected: permission denied
        conn.rollback()
    finally:
        conn.close()
    return problems


# ==========================================================================
# Loading
# ==========================================================================


def _statements(ddl: str) -> list:
    lines = [ln for ln in ddl.splitlines() if not ln.strip().startswith("--")]
    return [s.strip() for s in "\n".join(lines).split(";") if s.strip()]


def _ensure_reader_password() -> str:
    password = db_config.setting("MYSQL_READER_PASSWORD")
    if password:
        return password
    password = secrets.token_urlsafe(18)
    user = db_config.setting("MYSQL_READER_USER", "c4_reader")
    with open(db_config.ENV_PATH, "a", encoding="utf-8") as fh:
        fh.write(
            "\n# Added by test_db/seed.py - SELECT-only account for fixture queries\n"
            f"MYSQL_READER_USER={user}\nMYSQL_READER_PASSWORD={password}\n"
        )
    import os

    os.environ["MYSQL_READER_USER"] = user
    os.environ["MYSQL_READER_PASSWORD"] = password
    print(f"  Generated a password for '{user}' and recorded it in .env")
    return password


def load(dataset: dict) -> None:
    db = database_name()
    reader = db_config.setting("MYSQL_READER_USER", "c4_reader")

    conn = admin_connection()  # fail on missing admin access before touching .env
    reader_password = _ensure_reader_password()
    try:
        with conn.cursor() as cur:
            cur.execute(f"CREATE DATABASE IF NOT EXISTS `{db}` CHARACTER SET utf8mb4")
            cur.execute(f"USE `{db}`")
            for stmt in _statements(schema_ddl()):
                cur.execute(stmt)
            for table, rows in dataset["tables"].items():
                cols = COLUMNS[table]
                sql = (f"INSERT INTO {table} ({', '.join(cols)}) "
                       f"VALUES ({', '.join(['%s'] * len(cols))})")
                for i in range(0, len(rows), 1000):
                    cur.executemany(sql, rows[i:i + 1000])
                print(f"  {table:<16} {len(rows):>6} rows")

            # Both host forms: 'localhost' covers the named pipe / socket,
            # '127.0.0.1' covers TCP when name resolution is skipped.
            for host in ("localhost", "127.0.0.1"):
                cur.execute("CREATE USER IF NOT EXISTS %s@%s IDENTIFIED BY %s",
                            (reader, host, reader_password))
                cur.execute("ALTER USER %s@%s IDENTIFIED BY %s", (reader, host, reader_password))
                cur.execute(f"GRANT SELECT ON `{db}`.* TO %s@%s", (reader, host))
        conn.commit()
    finally:
        conn.close()


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    parser.add_argument("--check", action="store_true",
                        help="build and verify in memory only; do not touch MySQL")
    args = parser.parse_args()

    print("Building synthetic dataset...")
    dataset = build_dataset()
    for tenant, t in dataset["truth"]["tenants"].items():
        e = t["expenses"]
        print(f"  {tenant}: {len(t['months'])} months ({t['months'][0]}..{t['months'][-1]}), "
              f"expense anomalies at {e['anomaly_months'] or 'none'}"
              + (f", floored months {e['floored_indices']}" if e["floored_indices"] else ""))

    problems = verify_in_memory(dataset)
    OUTPUT_DIR.mkdir(exist_ok=True)
    (OUTPUT_DIR / "ground_truth.json").write_text(
        json.dumps(dataset["truth"], indent=2), encoding="utf-8")
    print(f"  ground truth written to {OUTPUT_DIR / 'ground_truth.json'}")

    if args.check:
        _report(problems)
        return 1 if problems else 0

    print(f"\nLoading into MySQL database '{database_name()}'...")
    try:
        load(dataset)
        problems += verify_database(dataset["truth"])
    except db_config.DatabaseNotConfigured as exc:
        print(f"\nNOT LOADED: {exc}")
        return 2
    _report(problems)
    return 1 if problems else 0


def _report(problems: list) -> None:
    if problems:
        print("\nVerification FAILED:")
        for p in problems:
            print(f"  - {p}")
    else:
        print("\nVerification passed: every monthly total matches the ground truth.")


if __name__ == "__main__":
    sys.exit(main())
