#!/usr/bin/env python3
# =====================================================================
# HD Requests - daily auto-updater
# ---------------------------------------------------------------------
# Checks TDEC for NEW Hydrologic Determination points in the last N days,
# reads each new determination's acceptance LETTER, pulls any Stream / WWC
# features (begin/end coordinates), and updates tn_hd_streams.js + the map.
#
# Runs with NO manual data entry for letters whose feature table is TEXT
# (the majority). Letters whose table is an IMAGE (or a non-PDF format) are
# listed in needs_review.txt so you can add them by hand via manual_features.json.
#
# Usage:  python hd_daily_update.py        (or double-click run_update.cmd)
# One-time setup:  run setup.cmd once first.
# =====================================================================
import base64, json, math, re, subprocess, sys, time, urllib.request
from datetime import datetime, timezone, timedelta
from urllib.parse import urljoin, urlencode
from pathlib import Path

# ------------------------- CONFIG (edit these) -----------------------
DAYS_WINDOW   = 30      # look back this many days for new determinations
AUTO_GIT_PUSH = True    # set False to update files only and NOT push to GitHub
GIT_BRANCH    = "main"
HEADLESS      = True    # set False to watch the browser work (for debugging)
SELF_TEST     = False   # verified working 2026-07-28. Set True again only to re-run the letter-parse health check.
SCRAPE_COLLECTED    = True   # also scrape TDEC's "HD Requests Collected" list (Page 2) so requests
                             # that aren't on the ArcGIS map yet (or have no coordinates) still show.
COLLECTED_MAX_PAGES = 400    # safety cap on report pagination (each page ~15 rows)
# ---------------------------------------------------------------------

HERE      = Path(__file__).resolve().parent
DATA_JSON = HERE / "hd_data.json"          # the pipeline's source of truth
MANUAL    = HERE / "manual_features.json"  # your hand-entered features
OUT_JS    = HERE / "tn_hd_streams.js"      # what the map reads (stream/WWC detail)
PENDING_JS= HERE / "tn_hd_pending.js"      # DataViewer requests not (yet) on the ArcGIS map
LOG       = HERE / "update_log.txt"
REVIEW    = HERE / "needs_review.txt"

BASE        = "https://dataviewers.tdec.tn.gov/dataviewers/"
HOME_URL    = BASE + "f?p=2005:34341:0"
DETAIL_URL  = BASE + "f?p=2005:34341:0::::P34341_DETERMINATION_ID:{id}"
COLLECT_URL = BASE + "f?p=2005:34340:0"   # Page 2 — "HD Requests Collected" interactive report
ARCGIS      = "https://tdeconline.tn.gov/arcgis/rest/services/WPC_Hydro_Determination/MapServer/0/query"

def log(msg):
    line = f"[{datetime.now():%Y-%m-%d %H:%M:%S}] {msg}"
    print(line)
    with open(LOG, "a", encoding="utf-8") as f:
        f.write(line + "\n")

# ------------------------- coordinate helpers ------------------------
def haversine_ft(a, b):
    R = 6371000.0
    dlat = math.radians(b[0]-a[0]); dlon = math.radians(b[1]-a[1])
    s = math.sin(dlat/2)**2 + math.cos(math.radians(a[0]))*math.cos(math.radians(b[0]))*math.sin(dlon/2)**2
    return 2*R*math.asin(min(1, math.sqrt(s))) * 3.280839895

def fmt_ft(ft):
    return "point" if ft == 0 else f"{round(ft):,} ft"

# lat ~ 34.9..36.7  |  lon ~ -90.4..-81.6 (Tennessee). Tolerate a dropped minus sign.
def classify(v):
    if 34.5 <= v <= 37.0:   return ("lat", v)
    if 81.0 <= abs(v) <= 91.0: return ("lon", -abs(v))
    return (None, v)

# ------------------------- letter table parser -----------------------
NUM_RE = re.compile(r'-?\d{2,3}\.\d{3,7}')
STREAM_KW = ("wet weather", "wwc", "conveyance")     # -> WWC
STREAM_KW2 = ("stream", "perennial", "intermittent") # -> Stream
EXCLUDE_KW = ("wetland", "pond", "upland", "lake", "sinkhole")

def line_determination(text):
    low = text.lower()
    if any(k in low for k in STREAM_KW):  return "WWC"
    if any(k in low for k in STREAM_KW2): return "Stream"
    return None   # wetland/pond/upland/none -> not a stream/WWC row

def pairs_from_tokens(tokens):
    """tokens: list of floats in x-order -> list of (lat,lon) points."""
    pts, i = [], 0
    while i < len(tokens):
        k1, v1 = classify(tokens[i])
        if k1 == "lat" and i+1 < len(tokens):
            k2, v2 = classify(tokens[i+1])
            if k2 == "lon":
                pts.append((round(v1, 6), round(v2, 6))); i += 2; continue
        i += 1
    return pts

def parse_pdf_features(pdf_bytes):
    """Return (features, had_text). features = [{id,tdec,start,end,point}]."""
    try:
        import fitz  # PyMuPDF
    except ImportError:
        raise SystemExit("PyMuPDF is not installed. Run setup.cmd first.")
    doc = fitz.open(stream=pdf_bytes, filetype="pdf")
    had_text = False
    feats = []
    for page in doc:
        words = page.get_text("words")  # (x0,y0,x1,y1,text,block,line,wno)
        if words: had_text = True
        # group words into visual rows by y
        rows = {}
        for w in words:
            key = round((w[1]+w[3])/2 / 4)   # ~4pt row bucket
            rows.setdefault(key, []).append(w)
        for key in sorted(rows):
            ws = sorted(rows[key], key=lambda w: w[0])
            text = " ".join(w[4] for w in ws)
            tdec = line_determination(text)
            low = text.lower()
            # skip rows that are wetland/pond/upland unless they also carry a stream/WWC call
            if tdec is None:
                continue
            if any(k in low for k in EXCLUDE_KW) and tdec is None:
                continue
            # collect coordinate tokens in x-order
            toks = []
            for w in ws:
                for m in NUM_RE.findall(w[4].replace("°", "").replace(",", "")):
                    try: toks.append(float(m))
                    except ValueError: pass
            pts = pairs_from_tokens(toks)
            if not pts:
                continue
            # label = words before the first coordinate token / determination word
            label_parts = []
            for w in ws:
                wl = w[4].lower()
                if NUM_RE.search(w[4].replace("°","").replace(",","")): break
                if any(k in wl for k in STREAM_KW+STREAM_KW2+EXCLUDE_KW): break
                label_parts.append(w[4])
            label = " ".join(label_parts).strip(" -|:") or f"F{len(feats)+1}"
            start = pts[0]
            end = pts[1] if len(pts) > 1 else pts[0]
            feats.append({"id": label, "tdec": tdec,
                          "point": start == end,
                          "start": list(start), "end": list(end)})
    # de-duplicate
    seen, uniq = set(), []
    for f in feats:
        k = (f["id"], round(f["start"][0],5), round(f["start"][1],5),
             round(f["end"][0],5), round(f["end"][1],5))
        if k in seen: continue
        seen.add(k); uniq.append(f)
    return uniq, had_text

# ------------------------- in-browser JS -----------------------------
# Fetch the determination's detail HTML (same-origin, so headless allows it),
# find the acceptance-letter link, download the PDF, and return it as base64.
# This mirrors the approach proven to work interactively; it does NOT navigate
# to the detail page (whose document icons don't render in headless Chromium).
JS_GET_LETTER = r"""
async (did) => {
  const BASE = "https://dataviewers.tdec.tn.gov/dataviewers/";
  const html = await fetch(BASE + "f?p=2005:34341:0::::P34341_DETERMINATION_ID:" + did,
                           {credentials:'include'}).then(r=>r.text());
  const doc = new DOMParser().parseFromString(html, 'text/html');
  const anchors = Array.from(doc.querySelectorAll('a')).filter(a=>a.querySelector('img'));
  const rows = anchors.map(a=>({t:(a.closest('tr')?a.closest('tr').textContent.replace(/\s+/g,' '):''),
                                href:a.getAttribute('href')}));
  const pick = rows.find(r=>/Letter/i.test(r.t));
  if(!pick){ return {status:'no-letter'}; }
  const r = await fetch(new URL(pick.href, BASE).href, {credentials:'include'});
  const b = await r.blob();
  const buf = new Uint8Array(await b.slice(0,5).arrayBuffer());
  const magic = Array.from(buf).map(x=>x.toString(16).padStart(2,'0')).join('');
  const b64 = await new Promise(res=>{const fr=new FileReader();fr.onload=()=>res(fr.result.split(',')[1]);fr.readAsDataURL(b);});
  return {status:'ok', b64, magic, ct:b.type, size:b.size};
}
"""

JS_DIAG = r"""
async (did) => {
  const BASE = "https://dataviewers.tdec.tn.gov/dataviewers/";
  const url = BASE + "f?p=2005:34341:0::::P34341_DETERMINATION_ID:" + did;
  const r = await fetch(url, {credentials:'include'});
  const html = await r.text();
  const doc = new DOMParser().parseFromString(html, 'text/html');
  const imgA = Array.from(doc.querySelectorAll('a')).filter(a=>a.querySelector('img')).length;
  return {status:r.status, redirected:r.redirected, finalUrl:(r.url||'').slice(-55),
          len:html.length, imgAnchors:imgA, hasLetter:/Letter/i.test(html),
          hasDocs:/Determination Documents/i.test(html), head:html.slice(0,90).replace(/\s+/g,' ')};
}
"""

def get_letter(page, did):
    """Return {status:'ok', b64, magic, ...} or {status:'no-letter'} for a determination."""
    return page.evaluate(JS_GET_LETTER, str(did))

def fetch_arcgis(page, since):
    """Query the public ArcGIS point service. Try a plain HTTP request first
    (no browser, no CORS); fall back to browser navigation if that's blocked."""
    url = ARCGIS + "?" + urlencode({
        "where": f"INVESTIGATION_DATE >= DATE '{since}'",
        "outFields": "DETERMINATION_ID,COUNTY,PROPERTY_NAME,INVESTIGATION_DATE,LATITUDE,LONGITUDE",
        "returnGeometry": "true", "outSR": "4326", "resultRecordCount": "2000", "f": "json"})
    try:
        req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0", "Accept": "application/json"})
        with urllib.request.urlopen(req, timeout=45) as r:
            return json.loads(r.read().decode("utf-8", "replace"))
    except Exception as e1:
        log(f"  (ArcGIS via direct request failed: {e1}; retrying through the browser)")
    try:
        resp = page.goto(url, wait_until="domcontentloaded")
        return resp.json()
    except Exception as e2:
        raise SystemExit(f"Could not query the TDEC ArcGIS service ({e2}). Check your internet connection.")

# ------------------------- collected-requests scrape (Page 2) --------
MONTHS = {"JAN":1,"FEB":2,"MAR":3,"APR":4,"MAY":5,"JUN":6,
          "JUL":7,"AUG":8,"SEP":9,"OCT":10,"NOV":11,"DEC":12}
def parse_date_ms(s):
    """Parse '16-JUL-2026', '2026-07-16' or '7/16/2026' -> epoch ms (UTC), else None."""
    if not s: return None
    s = s.strip()
    m = re.match(r'(\d{1,2})[-/ ]([A-Za-z]{3})[A-Za-z]*[-/ ](\d{4})', s)
    if m:
        mon = MONTHS.get(m.group(2).upper())
        if mon:
            try: return int(datetime(int(m.group(3)), mon, int(m.group(1)), tzinfo=timezone.utc).timestamp()*1000)
            except Exception: return None
    m = re.match(r'(\d{4})-(\d{1,2})-(\d{1,2})', s)
    if m:
        try: return int(datetime(int(m.group(1)), int(m.group(2)), int(m.group(3)), tzinfo=timezone.utc).timestamp()*1000)
        except Exception: return None
    m = re.match(r'(\d{1,2})/(\d{1,2})/(\d{4})', s)
    if m:
        try: return int(datetime(int(m.group(3)), int(m.group(1)), int(m.group(2)), tzinfo=timezone.utc).timestamp()*1000)
        except Exception: return None
    return None

JS_SCRAPE_PAGE = r"""
() => {
  const norm = s => (s||'').replace(/\s+/g,' ').trim();
  let t = document.querySelector('table.a-IRR-table')
       || document.querySelector('.a-IRR-table')
       || document.querySelector('#apexir_DATA_PANEL table')
       || document.querySelector('table.apexir_WORKSHEET_DATA');
  if(!t){
    const cand = Array.from(document.querySelectorAll('table'))
      .filter(x => x.rows && x.rows.length > 1)
      .sort((a,b)=> b.rows.length - a.rows.length);
    t = cand[0] || null;
  }
  if(!t) return {headers:[], rows:[], pager:'', sig:'no-table'};
  let headers = Array.from(t.querySelectorAll('thead th, thead td')).map(h=>norm(h.textContent)).filter(x=>x);
  let bodyRows = Array.from(t.querySelectorAll('tbody tr'));
  if(!headers.length && t.rows.length){
    headers = Array.from(t.rows[0].cells).map(c=>norm(c.textContent));
    bodyRows = Array.from(t.rows).slice(1);
  }
  const rows = bodyRows.map(tr=>{
    const cells = Array.from(tr.cells).map(td=>norm(td.textContent));
    let id=null;
    const a = tr.querySelector('a[href*="DETERMINATION_ID"]') || tr.querySelector('a[href*="34341"]');
    if(a){ const h=a.getAttribute('href')||a.href||''; const m=h.match(/DETERMINATION_ID[:,]?(\d+)/i)||h.match(/(\d{3,})(?:\D*)$/); if(m) id=m[1]; }
    return {cells, id};
  }).filter(r=>r.cells.some(c=>c));
  let pager='';
  const p = document.querySelector('.a-IRR-pagination') || document.querySelector('.apexir_PAGINATION') || document.querySelector('td.pagination');
  if(p) pager = norm(p.textContent);
  const sig = (rows[0] ? (rows[0].id||rows[0].cells.join('|')).slice(0,80) : '') + '#' + rows.length;
  return {headers, rows, pager, sig};
}
"""

def _col(headers, *keys):
    for i, h in enumerate(headers):
        hl = h.lower()
        if any(k in hl for k in keys): return i
    return None

def _click_next(page):
    for sel in ("a.a-IRR-pagination-link--next", "button.a-IRR-button--pagination-next",
                "a[title='Next']", "button[title='Next']", "a[aria-label='Next']",
                "a[title='Next Page']", "img[title='Next']"):
        try:
            el = page.query_selector(sel)
            if el: el.click(); return True
        except Exception:
            continue
    try:
        el = page.query_selector("xpath=//a[normalize-space(.)='Next' or normalize-space(.)='>' "
                                 "or contains(@onclick,'NEXT') or contains(@onclick,'pgR')]")
        if el: el.click(); return True
    except Exception:
        pass
    return False

def fetch_collected_requests(page):
    """Scrape TDEC's Page-2 'HD Requests Collected' report. Returns a list of
    {id, prop, county, city, loc, lat, lon, ms}. Best-effort: never raises."""
    sites, seen = [], set()
    try:
        page.goto(COLLECT_URL, wait_until="domcontentloaded")
        page.wait_for_timeout(2500)
    except Exception as e:
        log(f"  (collected list: could not open Page 2 - {e})")
        return sites
    headers_logged, last_sig = False, None
    for pg in range(COLLECTED_MAX_PAGES):
        try:
            data = page.evaluate(JS_SCRAPE_PAGE)
        except Exception as e:
            log(f"  (collected list: read failed on page {pg+1} - {e})")
            break
        headers, rows = data.get("headers") or [], data.get("rows") or []
        if not headers_logged:
            log(f"  collected-list columns: {headers}")
            if data.get("pager"): log(f"  collected-list pager: {data['pager']}")
            headers_logged = True
        if not rows:
            break
        i_prop = _col(headers, "project", "property", "name", "site")
        i_cnty = _col(headers, "county")
        i_city = _col(headers, "city", "municipal", "town")
        i_loc  = _col(headers, "location", "description", "address")
        i_lat  = _col(headers, "latitude") ; i_lat = i_lat if i_lat is not None else _col(headers, "lat")
        i_lon  = _col(headers, "longitude"); i_lon = i_lon if i_lon is not None else _col(headers, "long", "lon")
        i_date = (_col(headers, "investigat") or _col(headers, "determination date", "completed", "field")
                  or _col(headers, "received", "request", "submit", "collect") or _col(headers, "date"))
        def cell(cells, idx):
            return cells[idx].strip() if (idx is not None and idx < len(cells)) else ""
        def fnum(s):
            try:
                v = float(str(s).replace(",", "").strip()); return v if v else None
            except Exception:
                return None
        for r in rows:
            cells, did = r.get("cells") or [], r.get("id")
            prop = cell(cells, i_prop)
            if not did and not prop:
                continue
            key = did or prop
            if key in seen:
                continue
            seen.add(key)
            sites.append({"id": str(did) if did else None, "prop": prop,
                          "county": cell(cells, i_cnty), "city": cell(cells, i_city),
                          "loc": cell(cells, i_loc),
                          "lat": fnum(cell(cells, i_lat)), "lon": fnum(cell(cells, i_lon)),
                          "ms": parse_date_ms(cell(cells, i_date))})
        sig = data.get("sig")
        if sig and sig == last_sig:
            break
        last_sig = sig
        if not _click_next(page):
            break
        page.wait_for_timeout(900)
    log(f"  collected list: {len(sites)} request(s) captured from the DataViewer")
    return sites

def write_pending_js(sites):
    stamp = datetime.now().strftime("%Y-%m-%d %H:%M")
    def js(v): return "null" if v is None else json.dumps(v)
    lines = [
        "/* tn_hd_pending.js - TDEC 'HD Requests Collected' list (Page 2), AUTO-GENERATED by hd_daily_update.py.",
        "   These are HD requests from TDEC's DataViewer that may NOT be on the ArcGIS map service yet",
        "   (or have no coordinates). hd_requests.html overlays any not already shown live, placing",
        "   coordinate-less ones on the county centroid, flagged 'location not added'.",
        "   sites[] = {id, prop, county, city, loc, lat, lon, ms}  (lat/lon/ms may be null) */",
        "const HD_EXTRA = {",
        f'  generatedAt: "{stamp} (auto)",',
        '  source: "TDEC DataViewer f?p=2005:34340 (HD Requests Collected)",',
        "  sites: [",
    ]
    for s in sites:
        lines.append("    {" + ", ".join([
            f'id:{js(s.get("id"))}', f'prop:{js(s.get("prop") or "")}',
            f'county:{js(s.get("county") or "")}', f'city:{js(s.get("city") or "")}',
            f'loc:{js(s.get("loc") or "")}',
            f'lat:{js(s.get("lat"))}', f'lon:{js(s.get("lon"))}', f'ms:{js(s.get("ms"))}',
        ]) + "},")
    lines += ["  ]", "};"]
    PENDING_JS.write_text("\n".join(lines) + "\n", encoding="utf-8")

# ------------------------- output writer -----------------------------
def rebuild_js(data):
    for did, rec in data["byId"].items():
        for f in rec["features"]:
            pt = bool(f.get("point")) or (f["start"] == f["end"])
            f["point"] = pt
            ft = 0.0 if pt else haversine_ft(f["start"], f["end"])
            f["lenFt"] = round(ft, 1)
            f["len"] = fmt_ft(ft)
        rec["features"].sort(key=lambda f: -(f["lenFt"] or 0))
        rec["count"] = len(rec["features"])

    def feat(f):
        parts = [f'id:{json.dumps(f["id"])}', f'len:{json.dumps(f["len"])}', f'lenFt:{f["lenFt"]}',
                 'corps:null', f'tdec:{json.dumps(f["tdec"])}', f'point:{str(f["point"]).lower()}',
                 f'start:[{f["start"][0]},{f["start"][1]}]', f'end:[{f["end"][0]},{f["end"][1]}]']
        return "    {" + ", ".join(parts) + "}"

    lines = []
    lines.append("/* tn_hd_streams.js - stream / WWC characteristics parsed from TDEC HD acceptance LETTERS.")
    lines.append("   AUTO-GENERATED by hd_daily_update.py. Each feature's begin/end lat-lon comes from the")
    lines.append("   letter's feature table. len / lenFt = straight-line distance begin->end (feet);")
    lines.append("   point:true = single-point feature; count = # of stream/WWC features per HD point.")
    lines.append("   Shown on the 14 / 30 / 90-day and 2026 live tabs of hd_requests.html.")
    lines.append("   byId[<DETERMINATION_ID>] = {prop, county, count, features:[{id,len,lenFt,corps,tdec,point,start,end}]} */")
    stamp = datetime.now().strftime("%Y-%m-%d %H:%M")
    lines.append("const STREAMS = {")
    lines.append(f' generatedAt:"{stamp} (auto)", window:"last {DAYS_WINDOW} days (rolling); reused by 90-day & 2026 tabs",')
    lines.append(" byId:{")
    for did in sorted(data["byId"], key=lambda x: int(x)):
        r = data["byId"][did]
        lines.append(f'  {json.dumps(did)}: {{prop:{json.dumps(r["prop"])}, county:{json.dumps(r["county"])}, count:{r["count"]}, features:[')
        lines.append(",\n".join(feat(f) for f in r["features"]))
        lines.append("  ]},")
    lines.append(" },")
    lines.append(" byName:{}")
    lines.append("};")
    OUT_JS.write_text("\n".join(lines) + "\n", encoding="utf-8")

# ------------------------- main --------------------------------------
def main():
    try:
        data = json.loads(DATA_JSON.read_text(encoding="utf-8"))
        if not isinstance(data, dict): raise ValueError("not a JSON object")
    except FileNotFoundError:
        log(f"{DATA_JSON.name} not found; starting a fresh dataset.")
        data = {}
    except Exception as e:
        log(f"Could not read {DATA_JSON.name} ({e}); starting a fresh dataset. "
            f"(The old file is left in place.)")
        data = {}
    data.setdefault("byId", {})
    data.setdefault("checked", {})
    checked = data["checked"]
    TERMINAL = {"empty", "image", "nonpdf"}   # won't change on re-check; "pending" IS re-checked daily

    # merge any hand-entered features first (so image-table letters get included)
    if MANUAL.exists():
        try:
            man = json.loads(MANUAL.read_text(encoding="utf-8"))
            for did, rec in man.get("byId", {}).items():
                if rec.get("features"):
                    data["byId"][did] = {"prop": rec.get("prop",""), "county": rec.get("county",""),
                                         "features": rec["features"]}
                    checked.pop(did, None)
        except Exception as e:
            log(f"manual_features.json skipped ({e})")
    known = set(data["byId"].keys())

    try:
        from playwright.sync_api import sync_playwright
    except ImportError:
        raise SystemExit("Playwright is not installed. Run setup.cmd first.")

    review_lines, added, feats_added, collected = [], [], 0, []
    # Present as a normal desktop Chrome so TDEC's firewall doesn't 403 the headless browser.
    REAL_UA = ("Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
               "(KHTML, like Gecko) Chrome/126.0.0.0 Safari/537.36")
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=HEADLESS,
                                    args=["--disable-blink-features=AutomationControlled"])
        context = browser.new_context(
            user_agent=REAL_UA, locale="en-US",
            extra_http_headers={"Accept-Language": "en-US,en;q=0.9"})
        context.add_init_script("Object.defineProperty(navigator,'webdriver',{get:()=>undefined});")
        page = context.new_page()
        page.set_default_timeout(45000)
        page.goto(HOME_URL, wait_until="domcontentloaded")   # seed the TDEC session
        time.sleep(1)

        # ----- DIAGNOSTIC: figure out which fetch method sees the letter link (35361) -----
        if SELF_TEST:
            did = "35361"
            durl = DETAIL_URL.format(id=did)
            # A) same-origin in-page fetch (current approach)
            try:
                a = page.evaluate(JS_DIAG, did)
                log("DIAG-A(fetch): " + json.dumps(a)[:300])
            except Exception as e:
                log(f"DIAG-A(fetch) error: {e}")
            # B) navigate to the page, read the rendered content
            try:
                page.goto(durl, wait_until="load")
                page.wait_for_timeout(2000)
                h = page.content()
                log(f"DIAG-B(nav): len={len(h)} hasLetter={'Letter' in h} hasDocs={'Determination Documents' in h} imgTags={h.count('<img')}")
            except Exception as e:
                log(f"DIAG-B(nav) error: {e}")
            # C) Playwright request channel (shares cookies, no CORS)
            try:
                rr = page.request.get(durl)
                t = rr.text()
                log(f"DIAG-C(request): status={rr.status} len={len(t)} hasLetter={'Letter' in t} hasDocs={'Determination Documents' in t} imgTags={t.count('<img')}")
            except Exception as e:
                log(f"DIAG-C(request) error: {e}")
            try:
                st = get_letter(page, "35361")
                if st.get("status") != "ok":
                    raise RuntimeError("no-letter (firewall may still be blocking)")
                stbody = base64.b64decode(st["b64"])
                tf, _ = parse_pdf_features(stbody)
                log(f"Self-test (35361 Canaan Baptist): letter downloaded ({len(stbody)} bytes), "
                    f"parsed {len(tf)} feature(s) - " + ("parser OK" if tf else "NO features (check pymupdf)"))
            except Exception as e:
                log(f"Self-test FAILED ({e})")

        since = (datetime.now() - timedelta(days=DAYS_WINDOW)).strftime("%Y-%m-%d 00:00:00")
        raw = fetch_arcgis(page, since)
        if isinstance(raw, dict) and raw.get("error"):
            raise SystemExit(f"TDEC ArcGIS query error: {raw['error']}")
        points = []
        for ftr in raw.get("features", []):
            a = ftr.get("attributes", {}) or {}; g = ftr.get("geometry", {}) or {}
            lat = a.get("LATITUDE") if a.get("LATITUDE") not in (None, 0) else g.get("y")
            lon = a.get("LONGITUDE") if a.get("LONGITUDE") not in (None, 0) else g.get("x")
            if a.get("INVESTIGATION_DATE") is None:
                continue
            no_ll = lat in (None, 0) or lon in (None, 0)
            # Keep records even when they carry no coordinates: their acceptance letter can still be
            # parsed, and the map drops them on the county centroid (flagged "location not added").
            points.append({"id": str(a.get("DETERMINATION_ID")), "prop": a.get("PROPERTY_NAME") or "",
                           "county": (a.get("COUNTY") or "").strip(),
                           "lat": None if no_ll else float(lat),
                           "lon": None if no_ll else float(lon),
                           "no_latlon": no_ll, "ms": a.get("INVESTIGATION_DATE")})
        log(f"TDEC live window ({DAYS_WINDOW}d): {len(points)} determination points")
        meta = {pt["id"]: pt for pt in points}
        new_ids = [pt["id"] for pt in points
                   if pt["id"] not in known and checked.get(pt["id"], {}).get("status") not in TERMINAL]
        log(f"Determinations to check (new, or awaiting a letter): {len(new_ids)}")

        for did in new_ids:
            m = meta[did]
            try:
                res = get_letter(page, did)
            except Exception as e:
                log(f"  {did} {m['prop']}: could not load ({e}) - will re-check next run")
                continue

            cmeta = {"prop": m["prop"], "county": m["county"]}
            if res.get("status") == "no-letter":
                checked[did] = {**cmeta, "status": "pending"}
                log(f"  {did} {m['prop']}: no acceptance letter yet - will re-check")
                continue
            if not res.get("magic", "").startswith("25504446"):   # %PDF
                checked[did] = {**cmeta, "status": "nonpdf", "ct": res.get("ct", "")}
                log(f"  {did} {m['prop']}: letter is not a PDF - flagged for manual review")
                continue

            pdf_bytes = base64.b64decode(res["b64"])
            try:
                feats, had_text = parse_pdf_features(pdf_bytes)
            except SystemExit:
                raise
            except Exception as e:
                checked[did] = {**cmeta, "status": "image"}
                log(f"  {did} {m['prop']}: parse error ({e}) - flagged for manual review")
                continue

            if feats:
                data["byId"][did] = {"prop": m["prop"], "county": m["county"], "features": feats}
                checked.pop(did, None)
                added.append(f"{did} {m['prop']} ({m['county']}): {len(feats)} feature(s)")
                feats_added += len(feats)
                log(f"  {did} {m['prop']}: +{len(feats)} stream/WWC feature(s)")
            elif not had_text:
                checked[did] = {**cmeta, "status": "image"}
                log(f"  {did} {m['prop']}: letter table is an IMAGE - flagged for manual review")
            else:
                checked[did] = {**cmeta, "status": "empty"}
                log(f"  {did} {m['prop']}: no stream/WWC features (wetlands/none)")

        # ----- collect the full DataViewer request list (incl. no-coordinate ones) -----
        if SCRAPE_COLLECTED:
            try:
                collected = fetch_collected_requests(page)
            except Exception as e:
                log(f"  (collected-list scrape failed: {e} - keeping any previous tn_hd_pending.js)")
        browser.close()

    # write the "requests not yet on the map" overlay file (only when the scrape returned rows,
    # so a one-off scrape failure never blanks a good existing file)
    if SCRAPE_COLLECTED and collected:
        try:
            write_pending_js(collected)
        except Exception as e:
            log(f"  (writing tn_hd_pending.js failed: {e})")
    elif SCRAPE_COLLECTED:
        log("  collected list empty - left existing tn_hd_pending.js untouched")

    rebuild_js(data)
    data["updated"] = datetime.now(timezone.utc).isoformat()
    DATA_JSON.write_text(json.dumps(data, indent=1), encoding="utf-8")

    review_lines = []
    for did, r in sorted(checked.items(), key=lambda kv: int(kv[0])):
        if r.get("status") in ("image", "nonpdf") and did not in data["byId"]:
            kind = "letter table is an IMAGE" if r["status"] == "image" else f"letter is not a PDF ({r.get('ct','')})"
            review_lines.append(f"{did}  {r.get('prop','')} ({r.get('county','')}) - {kind} "
                                f"- add via manual_features.json  {DETAIL_URL.format(id=did)}")
    REVIEW.write_text(("Determinations that need a manual look (image tables / non-PDF letters).\n"
                       "Open the link, read the table, and add them to manual_features.json.\n\n"
                       + ("\n".join(review_lines) if review_lines else "None right now.\n")),
                      encoding="utf-8")

    pending = sum(1 for r in checked.values() if r.get("status") == "pending")
    log(f"Summary: added {len(added)} determination(s), {feats_added} feature(s); "
        f"{len(review_lines)} need manual review; {pending} awaiting a letter.")
    for a in added: log("   + " + a)

    if AUTO_GIT_PUSH:
        try:
            files = ["tn_hd_streams.js", "hd_data.json"]
            if PENDING_JS.exists(): files.append("tn_hd_pending.js")
            subprocess.run(["git", "-C", str(HERE), "add", *files], check=True)
            r = subprocess.run(["git", "-C", str(HERE), "diff", "--cached", "--quiet"])
            if r.returncode == 1:  # there are staged changes
                msg = f"Auto-update HD streams/WWC ({datetime.now():%Y-%m-%d}): +{len(added)} determinations"
                subprocess.run(["git", "-C", str(HERE), "commit", "-m", msg], check=True)
                subprocess.run(["git", "-C", str(HERE), "push", "origin", GIT_BRANCH], check=True)
                log("Pushed update to GitHub.")
            else:
                log("No file changes to push.")
        except Exception as e:
            log(f"Git push skipped/failed ({e}). Files are updated locally; push manually if needed.")

if __name__ == "__main__":
    try:
        main()
    except SystemExit as e:
        # deliberate stop (missing dependency, unreachable ArcGIS); the message already says why
        if e.code not in (0, None):
            log(f"Stopped: {e}")
    except KeyboardInterrupt:
        log("Interrupted by user.")
    except Exception as e:
        import traceback
        log(f"UNEXPECTED ERROR: {e}")
        log(traceback.format_exc().strip())
        log("The run did not finish cleanly - see the traceback above. "
            "Existing files were left as they were unless a step above says otherwise.")
