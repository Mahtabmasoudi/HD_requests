# HD Requests — daily auto-updater

This checks TDEC every day for **new** Hydrologic Determination points, reads each
new determination's acceptance **letter**, pulls any **Stream / WWC** features
(begin/end coordinates), updates `tn_hd_streams.js`, and pushes the change to GitHub —
so the live map stays current with no help from Claude.

## What's in this folder

| File | What it does |
|---|---|
| `setup.cmd` | Run **once** to install what's needed. |
| `run_update.cmd` | **Double-click to update.** Checks TDEC, updates the map, pushes to git. |
| `hd_daily_update.py` | The actual program (you don't edit this to use it). |
| `hd_data.json` | The pipeline's memory of every determination it already has. |
| `manual_features.json` | Where **you** paste features it couldn't read automatically. |
| `tn_hd_pending.js` | Written each run — TDEC's full "HD Requests Collected" list, so requests not yet on the map (or with no coordinates) still appear. |
| `needs_review.txt` | Written each run — the few letters that need your eyes. |
| `update_log.txt` | Written each run — what it did. |

## Showing everything, even before TDEC maps it

The live map dots come from TDEC's **ArcGIS map service**, which only holds determinations
that have been given coordinates. TDEC's **DataViewer "HD Requests Collected" list** is broader
— it includes brand-new requests that aren't on the map yet, sometimes with no latitude/longitude.
Each run now also scrapes that list into **`tn_hd_pending.js`**, and the map overlays any request
that isn't already a live point:

- **No coordinates?** It's dropped on its **county centroid** and flagged **"location not added
  (approx.)"** so you know the position is a placeholder, not a survey point.
- **Future-dated?** A determination whose TDEC investigation date is in the future shows in
  **purple**, marked **"future-dated"** — it stays in the recent-day windows (including *Last 14
  days*) but its real date is never changed.

You can turn the scrape off with `SCRAPE_COLLECTED = False` in the CONFIG block. If a run's scrape
fails or returns nothing, the previous `tn_hd_pending.js` is left untouched (never blanked).

## Stream/WWC detail is kept, not rolling

Once a determination's acceptance letter has been read, its streams & WWC land in
`tn_hd_streams.js` keyed by determination ID and **stay there permanently** — the file is
cumulative, never pruned by date. So as a point ages out of the 14- and 30-day windows it keeps
its full detail on the **90-day and 2026** tabs; nothing is lost when it crosses 30 days. (The
"window" label inside the file is just descriptive.) Letters for the collected-list requests are
read a batch at a time — `LETTER_BUDGET` per run — so even a determination whose letter is posted
*after* it ages past 30 days still gets picked up and its detail added.

## First-time setup (once)

1. If you don't have Python: install it from <https://www.python.org/downloads/> and
   **tick "Add python.exe to PATH"** during install.
2. Double-click **`setup.cmd`**. It installs the browser engine and libraries
   (takes a few minutes; downloads ~150 MB the first time).
3. Make sure git can push without asking for a password. You already pushed once with
   HTTPS, so Windows has your GitHub credential saved — that's all it needs.

## Everyday use

Just double-click **`run_update.cmd`**. It will:

- pull the current determinations in the last 30 days from TDEC,
- process only the **new** ones (usually a handful),
- add any streams/WWC it finds, recompute lengths and counts,
- rewrite `tn_hd_streams.js`, and `git commit` + `git push` the change.

When it finishes, glance at:

- **`update_log.txt`** — e.g. "added 3 determinations, 11 features".
- **`needs_review.txt`** — letters it couldn't read automatically (see next section).

## The few it can't read by itself

Most TDEC letters list features as **text**, which the tool reads exactly. A minority
put the table in as a **picture** (or send the letter as a Word/Outlook file). The tool
can't OCR those safely, so it lists them in `needs_review.txt` with a link, e.g.:

```
35187  1039 Highway 96 N (Williamson) - letter table is an IMAGE (needs manual entry)  https://dataviewers...:35187
```

To add one: open the link, read the table, and paste it into **`manual_features.json`**
under `"byId"` (there's a filled-in `_example` in that file to copy). Only include
Streams and Wet Weather Conveyances — skip wetlands, ponds and upland points. The next
run (and every run after) merges your manual entries in automatically, and never asks
about that determination again.

## Make it run automatically every day (Windows Task Scheduler)

If you'd rather it run on its own each morning instead of clicking:

1. Press **Start**, type **Task Scheduler**, open it.
2. **Create Basic Task** → name it "HD daily update" → **Daily** → pick a time.
3. Action: **Start a program** → Program/script: browse to **`run_update.cmd`** in this
   folder → Finish.

Or paste this in PowerShell (adjust the path if the folder differs), which schedules it
for 8:00 AM daily:

```powershell
schtasks /create /tn "HD daily update" /tr "\"C:\Users\mahta\Downloads\HD_requests\HD_requests\run_update.cmd\"" /sc daily /st 08:00
```

To remove it later: `schtasks /delete /tn "HD daily update" /f`

## Settings you can change

Open `hd_daily_update.py` in Notepad — the top has a small **CONFIG** block:

- `DAYS_WINDOW = 30` — how many days back to look.
- `AUTO_GIT_PUSH = True` — set to `False` to update files but not push to GitHub.
- `HEADLESS = True` — set to `False` to watch the browser work (useful if something breaks).
- `SCRAPE_COLLECTED = True` — also scrape the "HD Requests Collected" list into `tn_hd_pending.js`
  (set `False` to skip it). If the first run's column names look off in `update_log.txt`
  (it prints `collected-list columns: [...]`), send me that line and I'll tune the mapping.
- `LETTER_BUDGET = 60` — how many collected-list acceptance letters to read per run for their
  stream/WWC detail (no-coordinate requests first). It's cached, so every request is fetched only
  once and the backfill fills in over a few runs. Raise it to backfill faster (each letter adds
  ~1–2 seconds to the run); set to `0` to skip letter-reading for collected requests entirely.

## If something goes wrong

- **"Python is not installed"** — install Python and tick *Add to PATH*, re-run `setup.cmd`.
- **Push failed** — files still updated locally; run `git push` yourself, or set
  `AUTO_GIT_PUSH = False`. The tool never loses data on a failed push.
- **A letter looks wrong on the map** — check `needs_review.txt`; you can always correct
  or add a determination by hand in `manual_features.json`.
- **Nothing new happened** — that's normal on days with no new determinations, or when
  the new ones don't have their acceptance letters posted yet (it'll pick them up
  automatically once TDEC posts them).
