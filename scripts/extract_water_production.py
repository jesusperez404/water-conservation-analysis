from __future__ import annotations

import csv
import math
import re
import sqlite3
from calendar import monthrange
from pathlib import Path
from statistics import mean

import numpy as np
import pymupdf


RAW_DIR = Path("data/raw")
DB_PATH = Path("database/water.db")
OUTPUT_DIR = Path("data/processed/water_production_review")
DAILY_CSV = OUTPUT_DIR / "water_production_daily_candidates.csv"
MONTHLY_CSV = OUTPUT_DIR / "water_production_monthly_candidates.csv"

EXPECTED_REPORTS = 15
ZOOM = 8.0

METRICS = {
    "finished_water": {
        "legend_text": "Finished Water Total MGD",
        "kind": "bar",
    },
    "accord_pond_usage": {
        "legend_text": "Accord Pond Usage MG",
        "kind": "bar",
    },
    "accord_pond_level": {
        "legend_text": "Pond Level Feet",
        "kind": "line",
    },
}


def get_report_month(path: Path) -> str:
    match = re.search(r"(\d{4})-(\d{2})", path.name)
    if not match:
        raise ValueError(f"Could not determine report month from {path.name}")
    return f"{match.group(1)}-{match.group(2)}-01"


def get_days(report_month: str) -> int:
    return monthrange(int(report_month[:4]), int(report_month[5:7]))[1]


def words(page):
    return [
        {
            "x0": float(w[0]),
            "y0": float(w[1]),
            "x1": float(w[2]),
            "y1": float(w[3]),
            "text": str(w[4]).strip(),
            "block": int(w[5]),
            "line": int(w[6]),
        }
        for w in page.get_text("words")
    ]


def normalized(text: str) -> str:
    return re.sub(r"\s+", " ", text).strip().lower()


def find_metric_page(doc, legend_text: str, year: int) -> int:
    """
    Find the page containing the actual chart legend, rather than relying
    on the Figure heading. This handles December 2025, where Figure 2-3's
    heading is on the preceding page but the pond chart is on the next page.
    """
    needle = normalized(legend_text)

    candidates = []

    for page_index, page in enumerate(doc):
        text = normalized(page.get_text("text"))

        if needle not in text:
            continue

        # Prefer a page that also contains the current report year.
        score = 1 if str(year) in text else 0
        candidates.append((score, page_index))

    if not candidates:
        raise ValueError(f"chart page containing '{legend_text}' not found")

    candidates.sort(reverse=True)
    return candidates[0][1]


def find_current_year_legend_line(page, legend_text: str, year: int):
    """
    Identify the current-year legend entry by its text, not by page position.
    This avoids accidentally selecting years from the chemical-use table.
    """
    page_words = words(page)
    needle = normalized(legend_text)

    exact_year_words = [
        w for w in page_words
        if w["text"] == str(year)
    ]

    candidates = []

    for year_word in exact_year_words:
        same_line = [
            w for w in page_words
            if w["block"] == year_word["block"]
            and w["line"] == year_word["line"]
        ]

        line_text = normalized(" ".join(w["text"] for w in same_line))

        if needle in line_text:
            candidates.append((year_word, same_line))
            continue

        # Fallback for PDFs that split visually identical legend text into
        # separate PDF blocks. Reconstruct a same-baseline band.
        yc = (year_word["y0"] + year_word["y1"]) / 2

        band = [
            w for w in page_words
            if abs(((w["y0"] + w["y1"]) / 2) - yc) <= 3.0
            and w["x1"] <= year_word["x1"] + 1
            and w["x0"] >= max(0, year_word["x0"] - 150)
        ]

        band.sort(key=lambda w: w["x0"])
        band_text = normalized(" ".join(w["text"] for w in band))

        if needle in band_text:
            candidates.append((year_word, band))

    if not candidates:
        raise ValueError("current-year legend label not found")

    # The chart legend occurs well above any later table rows. If there are
    # multiple valid candidates, use the first one vertically.
    year_word, line_words = min(
        candidates,
        key=lambda item: item[0]["y0"],
    )

    label_words = [
        w for w in line_words
        if w["x0"] < year_word["x0"]
    ]

    if not label_words:
        raise ValueError("current-year legend text could not be reconstructed")

    label_x0 = min(w["x0"] for w in label_words)
    label_y0 = min(w["y0"] for w in line_words)
    label_y1 = max(w["y1"] for w in line_words)

    swatch = pymupdf.Rect(
        max(0, label_x0 - 15),
        max(0, label_y0 - 3),
        max(0, label_x0 - 1),
        min(page.rect.height, label_y1 + 3),
    )

    return year_word, swatch


def render_rgb(page, rect, zoom=ZOOM):
    pix = page.get_pixmap(
        matrix=pymupdf.Matrix(zoom, zoom),
        clip=rect,
        alpha=False,
    )

    arr = np.frombuffer(pix.samples, dtype=np.uint8).reshape(
        pix.height,
        pix.width,
        pix.n,
    )

    return arr[:, :, :3]


def get_swatch_color(page, rect):
    image = render_rgb(page, rect, zoom=12.0)
    pixels = image.reshape(-1, 3).astype(np.int16)

    chroma = pixels.max(axis=1) - pixels.min(axis=1)
    brightness = pixels.mean(axis=1)

    selected = pixels[
        (chroma >= 20)
        & (brightness >= 35)
        & (brightness <= 248)
    ]

    if len(selected) < 5:
        raise ValueError("could not identify current-year legend swatch color")

    selected_chroma = selected.max(axis=1) - selected.min(axis=1)
    cutoff = np.percentile(selected_chroma, 50)
    selected = selected[selected_chroma >= cutoff]

    color = np.median(selected, axis=0)

    return tuple(int(round(v)) for v in color)


def numeric_axis_candidates(page, legend_y):
    """
    Collect possible Y-axis labels.

    Earlier versions capped x1 at 121, which excluded most pond-level
    labels. Pond labels are wider (e.g. 136.00 / 139.50), so allow x1
    through 140 and let linear-sequence detection isolate the correct axis.
    """
    result = []

    for w in words(page):
        if w["y0"] <= 75:
            continue

        if w["y1"] >= legend_y - 4:
            continue

        if w["x0"] < 60 or w["x1"] > 140:
            continue

        text = w["text"].replace(",", "")

        if not re.fullmatch(r"-?\d+(?:\.\d+)?", text):
            continue

        result.append(
            {
                "y": (w["y0"] + w["y1"]) / 2,
                "value": float(text),
                "x1": w["x1"],
            }
        )

    result.sort(key=lambda r: r["y"])
    return result


def isolate_axis_ticks(page, legend_y):
    """
    Isolate the Y-axis belonging to THIS chart.

    Multiple water-production charts can share a PDF page. The old
    implementation selected the longest linear numeric sequence on the
    page, which sometimes caused Accord Pond Usage to inherit the Finished
    Water axis.

    Each chart's legend is directly below its own plot. Therefore the
    correct Y-axis is the valid linear tick sequence whose bottom tick is
    closest above the current metric's legend.
    """
    candidates = numeric_axis_candidates(page, legend_y)

    if len(candidates) < 3:
        raise ValueError(
            f"only {len(candidates)} Y-axis tick candidates found"
        )

    # Separate vertically distinct chart axes.
    groups = []
    current = [candidates[0]]

    for item in candidates[1:]:
        if item["y"] - current[-1]["y"] > 45:
            groups.append(current)
            current = [item]
        else:
            current.append(item)

    groups.append(current)

    valid_sequences = []

    for group in groups:
        n = len(group)

        for start in range(n):
            for end in range(start + 3, n + 1):
                subset = group[start:end]

                ys = np.array(
                    [row["y"] for row in subset],
                    dtype=float,
                )
                vals = np.array(
                    [row["value"] for row in subset],
                    dtype=float,
                )

                value_steps = np.diff(vals)

                if not (
                    np.all(value_steps > 0)
                    or np.all(value_steps < 0)
                ):
                    continue

                # Tick values must form a nearly constant arithmetic sequence.
                if len(value_steps) > 1:
                    step_abs = np.abs(value_steps)
                    step_mean = float(np.mean(step_abs))

                    if step_mean <= 0:
                        continue

                    if float(np.std(step_abs)) > max(
                        0.001,
                        step_mean * 0.04,
                    ):
                        continue

                slope, intercept = np.polyfit(
                    ys,
                    vals,
                    1,
                )
                predicted = slope * ys + intercept

                span = float(
                    vals.max() - vals.min()
                )
                tolerance = max(
                    0.015,
                    span * 0.015,
                )
                error = float(
                    np.max(
                        np.abs(
                            predicted - vals
                        )
                    )
                )

                if error > tolerance:
                    continue

                y_steps = np.diff(ys)

                if len(y_steps) > 1:
                    spacing_mean = float(
                        np.mean(y_steps)
                    )

                    if spacing_mean <= 0:
                        continue

                    if float(np.std(y_steps)) > max(
                        1.5,
                        spacing_mean * 0.12,
                    ):
                        continue

                bottom_y = float(
                    np.max(ys)
                )

                legend_gap = (
                    legend_y - bottom_y
                )

                # The axis must be above this metric's legend.
                if legend_gap <= 0:
                    continue

                valid_sequences.append(
                    {
                        "subset": subset,
                        "legend_gap": legend_gap,
                        "count": len(subset),
                        "span": span,
                        "error": error,
                    }
                )

    if not valid_sequences:
        raise ValueError(
            "could not isolate linear Y-axis tick sequence"
        )

    # PRIMARY RULE:
    # The correct chart is the one immediately above this legend.
    #
    # Use rounded gap buckets so tiny PDF-coordinate differences do not
    # outweigh having a fuller tick sequence.
    best = min(
        valid_sequences,
        key=lambda item: (
            round(item["legend_gap"], 1),
            -item["count"],
            -item["span"],
            item["error"],
        ),
    )

    return best["subset"]


def get_plot_x_bounds(page, ticks):
    top = min(t["y"] for t in ticks)
    bottom = max(t["y"] for t in ticks)

    horizontal = []

    for drawing in page.get_drawings():
        for item in drawing.get("items", []):
            if not item or item[0] != "l":
                continue

            p1, p2 = item[1], item[2]

            if abs(p1.y - p2.y) > 0.7:
                continue

            y = (p1.y + p2.y) / 2

            if y < top - 8 or y > bottom + 8:
                continue

            x0 = min(p1.x, p2.x)
            x1 = max(p1.x, p2.x)
            length = x1 - x0

            if x0 < 100 or x1 > 500 or length < 200:
                continue

            horizontal.append((length, x0, x1))

    if horizontal:
        _, x0, x1 = max(horizontal, key=lambda r: r[0])
        return float(x0), float(x1)

    # Consistent chart fallback.
    x0 = max(t["x1"] for t in ticks) + 8
    return x0, x0 + 312.5


def get_color_mask(image, rgb, tolerance):
    pixels = image.astype(np.int16)
    target = np.asarray(rgb, dtype=np.int16).reshape(1, 1, 3)

    delta = pixels - target

    # int32 accumulation prevents the overflow/sqrt warning from the
    # original extractor.
    distance_squared = np.sum(
        delta * delta,
        axis=2,
        dtype=np.int32,
    )

    return distance_squared <= tolerance * tolerance


def pdf_y_to_value(ticks, pdf_y):
    ys = np.array([t["y"] for t in ticks], dtype=float)
    vals = np.array([t["value"] for t in ticks], dtype=float)

    slope, intercept = np.polyfit(ys, vals, 1)
    return float(slope * pdf_y + intercept)


def extract_metric(page, metric_name, legend_text, year, days, kind):
    year_word, swatch = find_current_year_legend_line(
        page,
        legend_text,
        year,
    )

    rgb = get_swatch_color(page, swatch)

    ticks = isolate_axis_ticks(
        page,
        legend_y=year_word["y0"],
    )

    x0, x1 = get_plot_x_bounds(page, ticks)

    y0 = min(t["y"] for t in ticks) - 4
    y1 = max(t["y"] for t in ticks) + 4

    clip = pymupdf.Rect(x0, y0, x1, y1)
    image = render_rgb(page, clip)

    mask = None
    used_tolerance = None

    for tolerance in (40, 55, 70, 90, 115):
        candidate = get_color_mask(
            image,
            rgb,
            tolerance,
        )

        if int(candidate.sum()) >= days * 10:
            mask = candidate
            used_tolerance = tolerance
            break

    if mask is None:
        raise ValueError(
            f"too few current-year pixels for RGB={rgb}"
        )

    height, width = mask.shape

    extracted = []
    missing = []

    for day in range(1, days + 1):
        left = int(round((day - 1) * width / days))
        right = int(round(day * width / days))

        slot_width = max(1, right - left)
        margin = max(1, int(slot_width * 0.08))

        sx0 = min(width - 1, left + margin)
        sx1 = min(width, max(sx0 + 1, right - margin))

        yy, _ = np.where(mask[:, sx0:sx1])

        if len(yy) == 0:
            if kind == "bar" and abs(min(t["value"] for t in ticks)) < 1e-9:
                extracted.append(
                    {
                        "day": day,
                        "value": 0.0,
                        "pixels": 0,
                    }
                )
                continue

            missing.append(day)
            continue

        if kind == "bar":
            # Upper edge of a vertical bar.
            pixel_y = float(np.percentile(yy, 3))
        else:
            # Median of the line segment inside each day slot.
            pixel_y = float(np.median(yy))

        pdf_y = clip.y0 + pixel_y / ZOOM
        value = pdf_y_to_value(ticks, pdf_y)

        extracted.append(
            {
                "day": day,
                "value": value,
                "pixels": int(len(yy)),
            }
        )

    if missing:
        raise ValueError(
            f"no current-year pixels for days {missing}"
        )

    if len(extracted) != days:
        raise ValueError(
            f"expected {days} daily values, got {len(extracted)}"
        )

    values = [row["value"] for row in extracted]

    axis_low = min(t["value"] for t in ticks)
    axis_high = max(t["value"] for t in ticks)
    axis_span = axis_high - axis_low

    for value in values:
        if not math.isfinite(value):
            raise ValueError("non-finite extracted value")

        if value < axis_low - axis_span * 0.10:
            raise ValueError(
                f"value {value:.3f} below displayed axis "
                f"{axis_low:.3f}..{axis_high:.3f}"
            )

        if value > axis_high + axis_span * 0.10:
            raise ValueError(
                f"value {value:.3f} above displayed axis "
                f"{axis_low:.3f}..{axis_high:.3f}"
            )

    debug = {
        "rgb": rgb,
        "tolerance": used_tolerance,
        "ticks": [round(t["value"], 4) for t in ticks],
        "plot": (
            round(x0, 2),
            round(y0, 2),
            round(x1, 2),
            round(y1, 2),
        ),
    }

    return extracted, debug


def write_csv(path, rows):
    path.parent.mkdir(parents=True, exist_ok=True)

    if not rows:
        if path.exists():
            path.unlink()
        return

    with path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(
            handle,
            fieldnames=list(rows[0].keys()),
        )
        writer.writeheader()
        writer.writerows(rows)



def load_water_production(monthly_rows):
    """
    Rebuild water_production only after every report has passed extraction.

    Mapping:
      finished_water_mgd   <- finished_water_mean_mgd
      accord_pond_usage_mg <- accord_pond_usage_total_mg
      accord_pond_level_ft <- accord_pond_level_mean_ft
    """
    if not DB_PATH.exists():
        raise ValueError(f"Database not found: {DB_PATH}")

    if len(monthly_rows) != EXPECTED_REPORTS:
        raise ValueError(
            f"Refusing database load: expected {EXPECTED_REPORTS} "
            f"validated monthly rows, got {len(monthly_rows)}"
        )

    conn = sqlite3.connect(DB_PATH)

    try:
        conn.execute("PRAGMA foreign_keys = ON")

        report_rows = conn.execute(
            """
            SELECT report_id, report_month
            FROM reports
            ORDER BY report_month
            """
        ).fetchall()

        report_ids = {
            str(report_month): report_id
            for report_id, report_month in report_rows
        }

        candidate_months = {
            row["observation_month"]
            for row in monthly_rows
        }

        missing_reports = sorted(
            candidate_months - set(report_ids)
        )

        if missing_reports:
            raise ValueError(
                "Missing matching report records for: "
                + ", ".join(missing_reports)
            )

        conn.execute("BEGIN")

        # Same validated-rebuild pattern used by extract_operations.py.
        conn.execute("DELETE FROM water_production")

        for row in monthly_rows:
            source_pages = sorted(
                {
                    int(row["finished_water_page"]),
                    int(row["accord_pond_usage_page"]),
                    int(row["accord_pond_level_page"]),
                }
            )

            source_page = source_pages[0]

            notes = (
                "Chart-derived monthly observation. "
                "finished_water_mgd = mean of extracted daily Finished Water MGD; "
                "accord_pond_usage_mg = sum of extracted daily Accord Pond Usage MG; "
                "accord_pond_level_ft = mean of extracted daily Accord Pond Level ft. "
                f"Source PDF pages: {', '.join(str(p) for p in source_pages)}. "
                "Daily chart candidates retained in "
                "data/processed/water_production_review/"
                "water_production_daily_candidates.csv."
            )

            conn.execute(
                """
                INSERT INTO water_production (
                    report_id,
                    observation_month,
                    finished_water_mgd,
                    accord_pond_usage_mg,
                    accord_pond_level_ft,
                    extraction_method,
                    source_page,
                    notes
                )
                VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    report_ids[row["observation_month"]],
                    row["observation_month"],
                    float(row["finished_water_mean_mgd"]),
                    float(row["accord_pond_usage_total_mg"]),
                    float(row["accord_pond_level_mean_ft"]),
                    "validated_chart_extraction",
                    source_page,
                    notes,
                ),
            )

        count = conn.execute(
            "SELECT COUNT(*) FROM water_production"
        ).fetchone()[0]

        distinct_months = conn.execute(
            """
            SELECT COUNT(DISTINCT observation_month)
            FROM water_production
            """
        ).fetchone()[0]

        if count != EXPECTED_REPORTS:
            raise ValueError(
                f"Post-load validation failed: expected {EXPECTED_REPORTS} "
                f"rows, found {count}"
            )

        if distinct_months != EXPECTED_REPORTS:
            raise ValueError(
                f"Post-load validation failed: expected {EXPECTED_REPORTS} "
                f"distinct months, found {distinct_months}"
            )

        conn.commit()

        return count

    except Exception:
        conn.rollback()
        raise

    finally:
        conn.close()


def main():
    pdfs = sorted(RAW_DIR.glob("weir_river_*.pdf"))

    print("WATER PRODUCTION CHART EXTRACTION")
    print("=" * 90)
    print("Database writes: NONE")
    print(f"Reports found: {len(pdfs)}")

    if len(pdfs) != EXPECTED_REPORTS:
        raise SystemExit(
            f"Expected {EXPECTED_REPORTS} PDFs, found {len(pdfs)}"
        )

    all_daily = []
    all_monthly = []
    failures = []

    for pdf_path in pdfs:
        month = get_report_month(pdf_path)
        year = int(month[:4])
        days = get_days(month)

        print()
        print("-" * 90)
        print(f"{month} | {days} days")

        try:
            # IMPORTANT: report rows stay local until all three metrics pass.
            report_daily = []
            report_metrics = {}
            report_pages = {}

            with pymupdf.open(pdf_path) as doc:
                for metric_name, config in METRICS.items():
                    page_index = find_metric_page(
                        doc,
                        config["legend_text"],
                        year,
                    )

                    page = doc[page_index]

                    rows, debug = extract_metric(
                        page=page,
                        metric_name=metric_name,
                        legend_text=config["legend_text"],
                        year=year,
                        days=days,
                        kind=config["kind"],
                    )

                    report_metrics[metric_name] = rows
                    report_pages[metric_name] = page_index + 1

                    values = [r["value"] for r in rows]

                    print(
                        f"{metric_name:<20} "
                        f"page={page_index + 1} "
                        f"days={len(values)} "
                        f"range={min(values):.3f}..{max(values):.3f} "
                        f"RGB={debug['rgb']} "
                        f"ticks={debug['ticks']}"
                    )

                    for row in rows:
                        report_daily.append(
                            {
                                "report_month": month,
                                "observation_date":
                                    f"{month[:7]}-{row['day']:02d}",
                                "metric": metric_name,
                                "value": round(row["value"], 4),
                                "source_page": page_index + 1,
                                "pixel_count": row["pixels"],
                            }
                        )

            finished = [
                r["value"]
                for r in report_metrics["finished_water"]
            ]

            usage = [
                r["value"]
                for r in report_metrics["accord_pond_usage"]
            ]

            pond = [
                r["value"]
                for r in report_metrics["accord_pond_level"]
            ]

            monthly = {
                "observation_month": month,
                "finished_water_mean_mgd": round(mean(finished), 4),
                "accord_pond_usage_total_mg": round(sum(usage), 4),
                "accord_pond_usage_mean_daily_mg": round(mean(usage), 4),
                "accord_pond_level_mean_ft": round(mean(pond), 4),
                "accord_pond_level_end_ft": round(pond[-1], 4),
                "finished_water_page": report_pages["finished_water"],
                "accord_pond_usage_page": report_pages["accord_pond_usage"],
                "accord_pond_level_page": report_pages["accord_pond_level"],
                "days": days,
            }

            # Atomic append: nothing from a failed report reaches the CSVs.
            all_daily.extend(report_daily)
            all_monthly.append(monthly)

            print(
                "MONTHLY CANDIDATE | "
                f"finished_mean={monthly['finished_water_mean_mgd']:.4f} MGD | "
                f"pond_usage_total={monthly['accord_pond_usage_total_mg']:.4f} MG | "
                f"pond_level_mean={monthly['accord_pond_level_mean_ft']:.4f} ft | "
                f"pond_level_end={monthly['accord_pond_level_end_ft']:.4f} ft"
            )

        except Exception as exc:
            failures.append((month, str(exc)))
            print(f"REVIEW FAILURE: {exc}")

    write_csv(DAILY_CSV, all_daily)
    write_csv(MONTHLY_CSV, all_monthly)

    print()
    print("=" * 90)
    print("VALIDATION SUMMARY")
    print("=" * 90)
    print(f"Reports passed: {len(all_monthly)}/{EXPECTED_REPORTS}")
    print(f"Daily rows produced: {len(all_daily)}")
    print(f"Monthly candidates produced: {len(all_monthly)}")
    print(f"Daily CSV: {DAILY_CSV}")
    print(f"Monthly CSV: {MONTHLY_CSV}")

    if failures:
        print()
        print("FAILURES")
        for month, error in failures:
            print(f"  {month}: {error}")

        print()
        print(
            "STOPPED: validation failure(s) detected. "
            "water_production was NOT modified."
        )
        return

    if len(all_monthly) != EXPECTED_REPORTS:
        print()
        print(
            f"STOPPED: expected {EXPECTED_REPORTS} validated reports, "
            f"got {len(all_monthly)}. water_production was NOT modified."
        )
        return

    print()
    print("ALL 15 WATER PRODUCTION EXTRACTIONS PASSED.")
    print("Loading validated monthly observations into SQLite...")

    loaded = load_water_production(all_monthly)

    print()
    print("=" * 90)
    print("DATABASE LOAD COMPLETE")
    print("=" * 90)
    print(f"water_production rows: {loaded}")


if __name__ == "__main__":
    main()
