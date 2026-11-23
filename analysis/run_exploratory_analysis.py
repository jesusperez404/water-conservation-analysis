from __future__ import annotations

import sqlite3
from pathlib import Path

import matplotlib

matplotlib.use("Agg")

import matplotlib.dates as mdates
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
from scipy.stats import pearsonr


DB_PATH = Path("database/water.db")
RESULTS_DIR = Path("analysis/results")
FIGURES_DIR = Path("analysis/figures")
REPORT_PATH = Path("docs/exploratory_analysis.md")

CORRELATION_FEATURES = {
    "precipitation_inches": "Precipitation",
    "accord_pond_usage_mg": "Accord Pond usage",
    "accord_pond_level_ft": "Accord Pond level",
    "estimated_reads_pct": "Estimated meter reads",
    "meters_over_10_years_pct": "Meters over 10 years",
    "meters_changed": "Meters changed",
    "main_breaks": "Main breaks",
    "service_line_repairs": "Service-line repairs",
    "customer_contacts": "Customer contacts",
    "total_work_orders": "Total work orders",
    "collection_posting_work_orders": "Collection-posting work orders",
    "maintenance_paid_usd": "Maintenance paid",
}


def load_data() -> tuple[pd.DataFrame, pd.DataFrame]:
    conn = sqlite3.connect(DB_PATH)
    try:
        monthly = pd.read_sql_query(
            "SELECT * FROM monthly_system_summary ORDER BY observation_month",
            conn,
            parse_dates=["observation_month"],
        )
        chemicals = pd.read_sql_query(
            """
            SELECT observation_month, chemical_name, amount, unit
            FROM chemical_usage
            ORDER BY observation_month, chemical_name
            """,
            conn,
            parse_dates=["observation_month"],
        )
    finally:
        conn.close()
    return monthly, chemicals


def calculate_correlations(
    monthly: pd.DataFrame, chemicals: pd.DataFrame
) -> pd.DataFrame:
    features = dict(CORRELATION_FEATURES)
    data = monthly.copy()
    chemical_pivot = chemicals.pivot(
        index="observation_month", columns="chemical_name", values="amount"
    ).add_prefix("chemical__")
    data = data.merge(chemical_pivot, on="observation_month", how="left")
    for column in chemical_pivot.columns:
        features[column] = column.removeprefix("chemical__").replace("_", " ").title()

    rows = []
    target = data["finished_water_mgd"]
    for column, label in features.items():
        paired = pd.concat([target, data[column]], axis=1).dropna()
        if len(paired) < 8 or paired[column].nunique() < 2:
            continue
        coefficient, p_value = pearsonr(
            paired["finished_water_mgd"], paired[column]
        )
        rows.append(
            {
                "feature": column,
                "label": label,
                "observations": len(paired),
                "pearson_r": coefficient,
                "p_value": p_value,
                "absolute_r": abs(coefficient),
            }
        )
    return pd.DataFrame(rows).sort_values(
        ["absolute_r", "label"], ascending=[False, True]
    )


def calculate_anomalies(monthly: pd.DataFrame) -> pd.DataFrame:
    columns = [
        "finished_water_mgd",
        "precipitation_inches",
        "accord_pond_usage_mg",
        "accord_pond_level_ft",
        "estimated_reads_pct",
        "customer_contacts",
        "total_work_orders",
        "maintenance_paid_usd",
    ]
    rows = []
    for column in columns:
        values = monthly[column]
        mean = values.mean()
        standard_deviation = values.std(ddof=0)
        if not standard_deviation or np.isnan(standard_deviation):
            continue
        z_scores = (values - mean) / standard_deviation
        for index in z_scores[abs(z_scores) >= 2].index:
            rows.append(
                {
                    "observation_month": monthly.loc[index, "observation_month"],
                    "metric": column,
                    "value": values.loc[index],
                    "z_score": z_scores.loc[index],
                }
            )
    if not rows:
        return pd.DataFrame(
            columns=["observation_month", "metric", "value", "z_score"]
        )
    return pd.DataFrame(rows).sort_values(["observation_month", "metric"])


def style_axis(axis: plt.Axes) -> None:
    axis.spines[["top", "right"]].set_visible(False)
    axis.grid(axis="y", color="#d9e2ec", linewidth=0.8, alpha=0.8)


def create_figures(monthly: pd.DataFrame) -> None:
    FIGURES_DIR.mkdir(parents=True, exist_ok=True)
    dates = monthly["observation_month"]

    fig, production_axis = plt.subplots(figsize=(11, 5.5))
    precipitation_axis = production_axis.twinx()
    precipitation_axis.bar(
        dates,
        monthly["precipitation_inches"],
        width=18,
        color="#9ecae1",
        alpha=0.55,
        label="Precipitation",
    )
    production_axis.plot(
        dates,
        monthly["finished_water_mgd"],
        color="#08519c",
        linewidth=2.5,
        marker="o",
        label="Finished water",
    )
    production_axis.set_ylabel("Mean daily finished water (MGD)")
    precipitation_axis.set_ylabel("Monthly precipitation (inches)")
    production_axis.set_title("Finished-water production and precipitation")
    production_axis.xaxis.set_major_locator(mdates.MonthLocator(interval=2))
    production_axis.xaxis.set_major_formatter(mdates.DateFormatter("%b\n%Y"))
    style_axis(production_axis)
    precipitation_axis.spines["top"].set_visible(False)
    handles = production_axis.get_lines() + precipitation_axis.containers
    labels = [item.get_label() for item in handles]
    production_axis.legend(handles, labels, loc="upper left", frameon=False)
    fig.tight_layout()
    fig.savefig(FIGURES_DIR / "production_and_precipitation.png", dpi=160)
    plt.close(fig)

    fig, axes = plt.subplots(1, 2, figsize=(11, 4.8))
    axes[0].scatter(
        monthly["accord_pond_usage_mg"],
        monthly["finished_water_mgd"],
        color="#2171b5",
        s=55,
    )
    axes[0].set_xlabel("Accord Pond usage (MG/month)")
    axes[0].set_ylabel("Mean daily finished water (MGD)")
    axes[0].set_title("Production vs. pond usage")
    axes[1].scatter(
        monthly["accord_pond_level_ft"],
        monthly["finished_water_mgd"],
        color="#238b45",
        s=55,
    )
    axes[1].set_xlabel("Mean daily Accord Pond level (feet)")
    axes[1].set_ylabel("Mean daily finished water (MGD)")
    axes[1].set_title("Production vs. pond level")
    for axis in axes:
        style_axis(axis)
    fig.tight_layout()
    fig.savefig(FIGURES_DIR / "pond_relationships.png", dpi=160)
    plt.close(fig)

    fig, axis = plt.subplots(figsize=(11, 5.5))
    axis.plot(
        dates,
        monthly["total_work_orders"],
        color="#6a51a3",
        marker="o",
        linewidth=2.2,
        label="Total work orders",
    )
    axis.plot(
        dates,
        monthly["collection_posting_work_orders"],
        color="#e6550d",
        marker="o",
        linewidth=1.8,
        label="Collection-posting work orders",
    )
    axis.set_ylabel("Reported monthly count")
    axis.set_title("Field work-order activity")
    axis.xaxis.set_major_locator(mdates.MonthLocator(interval=2))
    axis.xaxis.set_major_formatter(mdates.DateFormatter("%b\n%Y"))
    style_axis(axis)
    axis.legend(frameon=False)
    fig.tight_layout()
    fig.savefig(FIGURES_DIR / "field_work_orders.png", dpi=160)
    plt.close(fig)

    fig, axis = plt.subplots(figsize=(11, 5.5))
    axis.plot(
        dates,
        monthly["actual_reads_pct"],
        color="#2ca25f",
        marker="o",
        linewidth=2.2,
        label="Actual reads",
    )
    axis.plot(
        dates,
        monthly["estimated_reads_pct"],
        color="#de2d26",
        marker="o",
        linewidth=2.2,
        label="Estimated reads",
    )
    axis.plot(
        dates,
        monthly["meters_over_10_years_pct"],
        color="#756bb1",
        marker="o",
        linewidth=1.8,
        label="Meters over 10 years",
    )
    axis.set_ylim(0, 100)
    axis.set_ylabel("Percent")
    axis.set_title("Meter-read quality and meter age")
    axis.xaxis.set_major_locator(mdates.MonthLocator(interval=2))
    axis.xaxis.set_major_formatter(mdates.DateFormatter("%b\n%Y"))
    style_axis(axis)
    axis.legend(frameon=False, ncol=3)
    fig.tight_layout()
    fig.savefig(FIGURES_DIR / "meter_read_quality.png", dpi=160)
    plt.close(fig)


def format_month(value: pd.Timestamp) -> str:
    return value.strftime("%B %Y")


def write_report(
    monthly: pd.DataFrame,
    correlations: pd.DataFrame,
    anomalies: pd.DataFrame,
) -> None:
    production_peak = monthly.loc[monthly["finished_water_mgd"].idxmax()]
    production_low = monthly.loc[monthly["finished_water_mgd"].idxmin()]
    precipitation = correlations.loc[
        correlations["feature"] == "precipitation_inches"
    ].iloc[0]
    pond_usage = correlations.loc[
        correlations["feature"] == "accord_pond_usage_mg"
    ].iloc[0]
    pond_level = correlations.loc[
        correlations["feature"] == "accord_pond_level_ft"
    ].iloc[0]
    meter_age = correlations.loc[
        correlations["feature"] == "meters_over_10_years_pct"
    ].iloc[0]
    estimated_reads = correlations.loc[
        correlations["feature"] == "estimated_reads_pct"
    ].iloc[0]
    overspent = monthly[monthly["maintenance_remaining_budget_usd"] < 0]
    top_correlations = correlations.head(8)

    correlation_rows = "\n".join(
        f"| {row.label} | {row.observations} | {row.pearson_r:.3f} | "
        f"{'<0.001' if row.p_value < 0.001 else f'{row.p_value:.3f}'} |"
        for row in top_correlations.itertuples()
    )
    if anomalies.empty:
        anomaly_rows = "| None | — | — | — |"
    else:
        anomaly_rows = "\n".join(
            f"| {format_month(row.observation_month)} | "
            f"`{row.metric}` | {row.value:,.3f} | {row.z_score:.2f} |"
            for row in anomalies.itertuples()
        )

    report = f"""# Exploratory Analysis

This analysis covers the 15 validated Weir River Water System reports from
October 2024 through December 2025. It is descriptive and hypothesis-generating;
the short, uneven seasonal window is not sufficient for causal conclusions or a
stable seasonal model.

## Main findings

- Mean daily finished-water production ranged from
  **{production_low.finished_water_mgd:.2f} MGD in {format_month(production_low.observation_month)}**
  to **{production_peak.finished_water_mgd:.2f} MGD in {format_month(production_peak.observation_month)}**.
- Accord Pond usage had a strong positive exploratory association with finished
  water (`r = {pond_usage.pearson_r:.2f}`, `n = {pond_usage.observations}`), while pond
  level had an inverse association (`r = {pond_level.pearson_r:.2f}`). These are
  correlations, not evidence that one measure causes the other.
- Monthly precipitation had little observed linear relationship with finished-water
  production in this window (`r = {precipitation.pearson_r:.2f}`,
  `p = {precipitation.p_value:.3f}`). More years and weather controls are needed
  before interpreting rainfall effects.
- Estimated-read percentage and meter age were associated at different strengths
  with production (`r = {estimated_reads.pearson_r:.2f}` and
  `r = {meter_age.pearson_r:.2f}`, respectively). These metrics should be treated
  as data-quality and system-age context, not production drivers.
- The maintenance contract showed a negative remaining balance in
  **{len(overspent)} report months**. Because cumulative totals were restated
  across reports, analysis uses each report's current-month snapshot rather than
  constructing a continuous cash-flow series from successive cumulative values.
- Standardized screening flagged **{len(anomalies)} metric-month observations**
  at or beyond two standard deviations. These flags identify review candidates,
  not errors; validated source values remain unchanged.

![Finished-water production and precipitation](../analysis/figures/production_and_precipitation.png)

![Accord Pond relationships](../analysis/figures/pond_relationships.png)

## Strongest exploratory correlations with finished water

Pearson coefficients are shown only where at least eight paired observations
exist. With 15 months, p-values are unstable and multiple-comparison adjustment
would further reduce apparent significance.

| Feature | n | Pearson r | p-value |
|---|---:|---:|---:|
{correlation_rows}

The complete table is in
[`analysis/results/correlations_with_finished_water.csv`](../analysis/results/correlations_with_finished_water.csv).
Chemical series are compared separately by chemical; amounts with different
units are never summed. Aluminum sulfate retains the source's unresolved
`report-specific` unit.

## Meter and work-order context

![Meter-read quality and meter age](../analysis/figures/meter_read_quality.png)

![Field work orders](../analysis/figures/field_work_orders.png)

The sharp August 2025 work-order change is retained as reported. Operational
event fields that are absent from a report remain `NULL`; the analysis does not
turn unreported activity into zero.

## Anomaly review candidates

| Month | Metric | Value | z-score |
|---|---|---:|---:|
{anomaly_rows}

The full machine-readable output is in
[`analysis/results/anomalies.csv`](../analysis/results/anomalies.csv).

## Limits and next data needs

- Fifteen months do not provide enough repeated seasons for a robust seasonal
  model, trend decomposition, or forecasting evaluation.
- The reports contain finished-water production but not customer-consumption
  volume. Water loss cannot be calculated without billed/authorized consumption
  and a consistent production-volume denominator.
- Population, development, temperature, drought, groundwater, and permit data
  are not yet joined. Claims about growth or environmental drivers would be
  premature.
- Maintenance cumulative totals are periodically restated. Current-report
  snapshots are authoritative for this analysis; month-to-month differences of
  cumulative totals should not be interpreted as exact cash flows.
- Correlation does not establish causation, especially with small samples and
  shared seasonality.

## Reproduce

```powershell
python database/apply_schema.py
python analysis/run_exploratory_analysis.py
python -m unittest discover -s tests -v
```
"""
    REPORT_PATH.write_text(report, encoding="utf-8")


def main() -> None:
    RESULTS_DIR.mkdir(parents=True, exist_ok=True)
    monthly, chemicals = load_data()
    correlations = calculate_correlations(monthly, chemicals)
    anomalies = calculate_anomalies(monthly)
    create_figures(monthly)

    monthly.to_csv(RESULTS_DIR / "monthly_system_summary.csv", index=False)
    correlations.drop(columns="absolute_r").to_csv(
        RESULTS_DIR / "correlations_with_finished_water.csv", index=False
    )
    anomalies.to_csv(RESULTS_DIR / "anomalies.csv", index=False)
    write_report(monthly, correlations, anomalies)

    print(f"Monthly observations: {len(monthly)}")
    print(f"Correlations calculated: {len(correlations)}")
    print(f"Anomaly review candidates: {len(anomalies)}")
    print(f"Report: {REPORT_PATH}")


if __name__ == "__main__":
    main()
