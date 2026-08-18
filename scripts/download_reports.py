import sqlite3
from pathlib import Path
from urllib.request import Request, urlopen


DB_PATH = Path("database/water.db")
OUTPUT_DIR = Path("data/raw")


def download_file(url: str, output_path: Path) -> None:
    request = Request(
        url,
        headers={"User-Agent": "Mozilla/5.0"},
    )

    with urlopen(request) as response:
        output_path.write_bytes(response.read())


def main():
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

    conn = sqlite3.connect(DB_PATH)

    reports = conn.execute(
        """
        SELECT report_id, report_month, source_url
        FROM reports
        WHERE source_url IS NOT NULL
        ORDER BY report_month
        """
    ).fetchall()

    for report_id, report_month, source_url in reports:
        month_name = report_month[:7]
        output_path = OUTPUT_DIR / f"weir_river_{month_name}.pdf"

        if output_path.exists():
            print(f"Already exists: {output_path}")
            continue

        print(f"Downloading {month_name}...")
        download_file(source_url, output_path)

        conn.execute(
            """
            UPDATE reports
            SET file_path = ?,
                extraction_status = 'downloaded',
                downloaded_at = CURRENT_TIMESTAMP
            WHERE report_id = ?
            """,
            (str(output_path), report_id),
        )

        conn.commit()
        print(f"  Saved: {output_path}")

    conn.close()

    print("\nDownload complete.")


if __name__ == "__main__":
    main()