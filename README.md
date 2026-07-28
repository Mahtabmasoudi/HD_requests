# HD Requests — TDEC Hydrologic Determinations (interactive map)

Interactive Leaflet map of TDEC Hydrologic Determination (HD) requests across Tennessee.

- **Historical tabs** (2021–2025 + 5-Year Overall) — embedded, work offline.
- **Live tabs** (Last 14 / 30 / 90 days, 2026 YTD) — pull the current determinations
  straight from the TDEC ArcGIS service each time the page loads.
- On the **14- and 30-day** tabs, determinations whose report has been parsed show a
  teal ring; click one for its identified **streams & WWC** (length, Corps/TDEC class,
  start/end coordinates), drawn on the map. Includes single-point WWCs.

Open `hd_requests.html` (or the repo root — `index.html` redirects to it). The live
tabs, watershed layer, and parcel layers need internet.

## Files
- `hd_requests.html` — the page
- `tn_shared.js`, `tn_shared.css` — shared map engine + styles
- `tn_hd_data.js` — 2021–2025 determinations (embedded)
- `tn_hd_streams.js` — parsed stream/WWC report detail (rolling 30-day window; regenerate as it advances)
- `tn_boundaries.js` — county boundaries
- `tn_bigparcels.js` — large-parcel overview dots
- `index.html` — redirect to `hd_requests.html`
