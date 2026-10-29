from __future__ import annotations

import json
import sqlite3
from pathlib import Path

import numpy as np
import pandas as pd


DB_PATH = Path("database/water.db")
OUTPUT_PATH = Path("dashboard/data/dashboard.json")

ANOMALY_COLUMNS = (
    "finished_water_mgd",
    "precipitation_inches",
    "accord_pond_usage_mg",
    "accord_pond_level_ft",
    "estimated_reads_pct",
    "customer_contacts",
    "total_work_orders",
    "maintenance_paid_usd",
)


def records_with_nulls(frame: pd.DataFrame) -> list[dict]:
    clean = frame.astype(object).where(pd.notna(frame), None)
    return clean.to_dict(orient="records")


def anomaly_records(monthly: pd.DataFrame) -> list[dict]:
    rows = []
    for column in ANOMALY_COLUMNS:
        values = monthly[column]
        standard_deviation = values.std(ddof=0)
        if not standard_deviation or np.isnan(standard_deviation):
            continue
        z_scores = (values - values.mean()) / standard_deviation
        for index in z_scores[abs(z_scores) >= 2].index:
            rows.append(
                {
                    "observation_month": monthly.loc[index, "observation_month"],
                    "metric": column,
                    "value": float(values.loc[index]),
                    "z_score": round(float(z_scores.loc[index]), 4),
                }
            )
    return sorted(rows, key=lambda row: (row["observation_month"], row["metric"]))


def build_dashboard_data(database_path: Path = DB_PATH) -> dict:
    conn = sqlite3.connect(database_path)
    try:
        monthly = pd.read_sql_query(
            "SELECT * FROM monthly_system_summary ORDER BY observation_month", conn
        )
        coverage = pd.read_sql_query(
            "SELECT * FROM monthly_dataset_coverage ORDER BY observation_month", conn
        )
        chemicals = pd.read_sql_query(
            """
            SELECT observation_month, chemical_name, amount, unit
            FROM chemical_usage
            ORDER BY observation_month, chemical_name
            """,
            conn,
        )
    finally:
        conn.close()

    if len(monthly) != 15 or len(coverage) != 15 or len(chemicals) != 120:
        raise ValueError("Dashboard source coverage is incomplete")
    if not (coverage.iloc[:, 1:].sum(axis=1) == 9).all():
        raise ValueError("Dashboard source contains incomplete report months")

    units = {
        row.chemical_name: row.unit
        for row in chemicals[["chemical_name", "unit"]]
        .drop_duplicates()
        .itertuples()
    }
    chemical_pivot = chemicals.pivot(
        index="observation_month", columns="chemical_name", values="amount"
    ).reset_index()
    chemical_pivot.columns.name = None

    return {
        "reporting_period": {
            "start": monthly["observation_month"].iloc[0],
            "end": monthly["observation_month"].iloc[-1],
            "months": len(monthly),
        },
        "monthly": records_with_nulls(monthly),
        "chemicals": records_with_nulls(chemical_pivot),
        "chemical_units": units,
        "coverage": records_with_nulls(coverage),
        "anomalies": anomaly_records(monthly),
        "limitations": [
            "The 15-month reporting window is too short for robust seasonality or causal inference.",
            "Customer-consumption volume is unavailable, so water loss cannot be calculated.",
            "Missing operational activity remains unreported (null), not zero.",
            "Maintenance cumulative totals are current-report snapshots and may be restated.",
        ],
    }


def main() -> None:
    data = build_dashboard_data()
    OUTPUT_PATH.parent.mkdir(parents=True, exist_ok=True)
    OUTPUT_PATH.write_text(
        json.dumps(data, indent=2, allow_nan=False) + "\n", encoding="utf-8"
    )
    print(
        f"Wrote {len(data['monthly'])} monthly records and "
        f"{len(data['anomalies'])} anomaly flags to {OUTPUT_PATH}"
    )


if __name__ == "__main__":
    main()
