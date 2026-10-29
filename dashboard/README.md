# Interactive Dashboard

The dashboard is a buildless, offline-friendly site backed by a generated JSON
snapshot of the tracked SQLite database. It has no CDN or hosted-service
dependency.

From the repository root:

```powershell
python dashboard/build_dashboard_data.py
python -m http.server 8000 -d dashboard
```

Then open `http://localhost:8000`.

The dashboard provides date-range filtering, selectable monthly trends,
production-versus-pond-use comparison, per-chemical trends, anomaly review,
coverage status, a source-aligned detail table, and filtered CSV download.

`dashboard/data/dashboard.json` is generated only from validated database tables
and views. Rebuild it after database changes and commit it with the associated
source update so the static dashboard remains reproducible.
