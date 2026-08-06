/* tn_shared.js — reusable components shared by BOTH pages.
   Extracted from the original single-file app to avoid duplicating code
   (color ramps, formatters, TPAD deep-links, the PMTiles parcel engine,
   parcel click/popup, and the live HUC8 watershed geometry loader).

   These functions reference a few page-level globals that every page defines
   before calling them: `map` (the Leaflet map) and `pclMode` (parcel source).
   Exactly as in the original, all scripts share one global scope, so a page's
   top-level `const map = ...` is visible to these helpers at call time. */

/* ---------------- color ramps (choropleth) ---------------- */
const GRN=['#e8f4ed','#c3e3d0','#8fcdaa','#52ad7e','#1a7f4b'];
const RED=['#fbeae8','#f5c6c1','#e89189','#d15a4e','#b8342a'];
const BLU=['#eef3f7','#cfe0eb','#9dc0d6','#5d8ba6','#16465f'];
const VSEQ=['#f6f2e6','#ecdcae','#dcb864','#c58a34','#9c5314'];   // land-value sequential (earthy)
function ramp(arr,t){ if(t<=0) return arr[0];
  const i=Math.min(arr.length-1, Math.floor(t*arr.length)); return arr[i]; }
function trendColor(s){ return s>0.5?'#1a7f4b':(s<-0.5?'#b8342a':'#7c8b97'); }  // rising / falling / flat

/* ---------------- formatters ---------------- */
function esc(s){ return String(s==null?'':s).replace(/[&<>]/g, c=>({'&':'&amp;','<':'&lt;','>':'&gt;'}[c])); }
function fmtMoney(v){ v = Number(v); return (v>0) ? '$'+v.toLocaleString('en-US') : '—'; }
function fmtAcre(v){ v = Number(v); return (v>0) ? v.toLocaleString('en-US',{maximumFractionDigits:2})+' ac' : '—'; }
function vMoney(v){ return '$'+Math.round(v).toLocaleString(); }
function wpMoney(v){ v=Number(v); return v>0?'$'+v.toLocaleString('en-US'):'—'; }
function wpAc(v){ v=Number(v); return v>0?v.toLocaleString('en-US',{maximumFractionDigits:1})+' ac':'—'; }
function setHint(id, txt){ const e=document.getElementById(id); if(e) e.textContent=txt; }

/* If the page was opened as a file:// URL, the parcel layers can't work (a
   browser cannot HTTP-Range-read the local tn_parcels.pmtiles from file://).
   Show a clear, actionable banner and pre-set the parcel hints. Call after the
   DOM exists. Returns true if running from file://. */
function showServeBannerIfFile(){
  if(/^https?:\/\//i.test(PCL_PMTILES)) return false;   // hosted archive: no local server needed
  if(location.protocol !== 'file:') return false;
  const page = location.pathname.split('/').pop() || 'this page';
  const wrap = document.querySelector('.wrap'), anchor = document.querySelector('.stats');
  if(wrap){
    const b=document.createElement('div');
    b.className='warn'; b.style.margin='0 0 18px';
    b.innerHTML='<b>Open this over the local server, not as a file.</b> The <b>Property Parcels</b> and '
      +'<b>Large Parcels (500+ ac)</b> layers read the local <code>tn_parcels.pmtiles</code>, which a browser can '
      +'only fetch over http (with byte-range support). Right now you’re viewing <code>'+location.protocol+'</code>. '
      +'Run <code>serve_tn_map.cmd</code> and open <b>http://localhost:8777/'+page+'</b>.';
    wrap.insertBefore(b, anchor || wrap.firstChild);
  }
  setHint('pclHint','⚠ Needs the local server — see the banner above');
  setHint('bigHint','⚠ Needs the local server — see the banner above');
  return true;
}

/* ================= Reference-layer service URLs =================
   HUC8   -> Feature Service (queryable, has attributes)
   Parcels-> Vector Tile Service (renders only) + local PMTiles archive
================================================================= */
const HUC_URL = 'https://services.arcgis.com/P3ePLMYs2RVChkJx/arcgis/rest/services/Watershed_Boundary_Dataset_HUC_8s/FeatureServer/0';
const PCL_TILES = 'https://tiles.arcgis.com/tiles/YuVBSS7Y1of2Qud1/arcgis/rest/services/Property_Boundaries_86_Counties/VectorTileServer/tile/{z}/{y}/{x}.pbf';
/* Merged parcels: all 86 counties in one PMTiles archive, joined to the
   assessment data. HOSTED on Hugging Face with HTTP-Range + CORS support, so the
   parcel & large-parcel layers work from anywhere — served locally, hosted, or
   even opened as a file:// page. (To use a local copy instead, set this to
   'tn_parcels.pmtiles' and serve the page over http via serve_tn_map.cmd.) */
const PCL_PMTILES = 'https://huggingface.co/datasets/mahtabmasoudinezhad/tn-parcels/resolve/main/tn_parcels.pmtiles';
const PCL_MINZ = 12;         // ALL-parcels layer renders from this zoom (z12 is the lowest the tiles exist; below it there is no parcel data)
const PCL_MINNATIVE = 12;    // lowest zoom baked into the tiles (nothing below z12 exists)
const PCL_MAXNATIVE = 14;    // highest zoom baked into the tiles; overzoomed beyond
const BIG_POLY_MINZ = 12;    // LARGE-parcel detailed polygons come from the native z12 tiles at this zoom+;
                             // BELOW it, the lightweight BIGPARCELS centroid dots give a from-far-out overview
                             // (downscaling z12 tiles to z8 would need thousands of tiles — dots instead)

/* ---------- live HUC8 watershed geometry (fetched once, cached) ----------
   Both pages need the polygons: for the filled analysis layer AND for the
   outline-only reference in the "other" view. One fetch, shared. */
let _wsGeom = null, _wsGeomPromise = null;
function fetchWatershedGeom(){
  if(_wsGeom) return Promise.resolve(_wsGeom);
  if(_wsGeomPromise) return _wsGeomPromise;
  const tn={xmin:-90.6,ymin:34.8,xmax:-81.4,ymax:36.9,spatialReference:{wkid:4326}};
  const q=HUC_URL+'/query?where='+encodeURIComponent('1=1')+'&geometry='+encodeURIComponent(JSON.stringify(tn))
    +'&geometryType=esriGeometryEnvelope&inSR=4326&spatialRel=esriSpatialRelIntersects'
    +'&outFields=huc8,name&returnGeometry=true&outSR=4326&resultRecordCount=1000&f=geojson';
  _wsGeomPromise = fetch(q).then(r=>r.json()).then(d=>{ _wsGeom=d; return d; });
  return _wsGeomPromise;
}
function wsHucOf(f){ const p=f.properties||{}; return String(p.huc8||p.HUC8||p.HUC_8||p.hu_8||''); }
function wsNameOf(f){ const p=f.properties||{}; return p.NAME||p.name||p.HU_8_NAME||p.hu_8_name||p.HUC8_Name||'Watershed'; }

/* ---------- Property parcels (local PMTiles, clickable) ---------- */
const _pcl = { pm:null, VectorTile:null, Pbf:null, ready:false, initing:null, why:'' };
// Load the MVT decoder (pbf + @mapbox/vector-tile) as ES modules. esm.sh is the
// primary CDN; jsDelivr's ESM build is a fallback in case esm.sh is blocked.
async function _loadMvtDecoder(){
  const CDNS = [
    ['https://esm.sh/@mapbox/vector-tile@1.3.1', 'https://esm.sh/pbf@3.2.1'],
    ['https://cdn.jsdelivr.net/npm/@mapbox/vector-tile@1.3.1/+esm', 'https://cdn.jsdelivr.net/npm/pbf@3.2.1/+esm']
  ];
  let lastErr;
  for(const [vtUrl, pbfUrl] of CDNS){
    try{
      const [vt, pbf] = await Promise.all([import(vtUrl), import(pbfUrl)]);
      return { VectorTile: vt.VectorTile, Pbf: pbf.default || pbf.Pbf || pbf };
    }catch(e){ lastErr = e; }
  }
  throw lastErr;
}
async function initPcl(){
  if(_pcl.ready) return true;
  if(_pcl.initing) return _pcl.initing;
  _pcl.initing = (async () => {
    const remote = /^https?:\/\//i.test(PCL_PMTILES);   // hosted archive works from any origin
    if(!remote && location.protocol === 'file:'){        // can't range-read a LOCAL pmtiles from file://
      _pcl.why = 'file'; return false;
    }
    if(typeof pmtiles === 'undefined'){ _pcl.why = 'lib'; return false; }
    try{
      const dec = await _loadMvtDecoder();
      _pcl.VectorTile = dec.VectorTile;
      _pcl.Pbf = dec.Pbf;
      _pcl.pm = new pmtiles.PMTiles(new URL(PCL_PMTILES, location.href).href);
      await _pcl.pm.getHeader();          // succeeds only if the archive is reachable via HTTP Range
      _pcl.ready = true;
      return true;
    }catch(e){ _pcl.why = 'fetch'; console.warn('parcel layer init failed (falling back to ArcGIS):', e); return false; }
  })();
  return _pcl.initing;
}
// human-readable reason the local parcel file could not load
function pclFailMsg(kind){
  const page = location.pathname.split('/').pop() || 'the page';
  if(_pcl.why === 'file') return '⚠ Open over http, not as a file — run serve_tn_map.cmd, then http://localhost:8777/'+page;
  if(_pcl.why === 'lib')  return '⚠ Tile library failed to load — needs internet';
  return '⚠ '+(kind||'Parcel file')+' unavailable — serve locally (serve_tn_map.cmd) or host tn_parcels.pmtiles';
}
let _PMGrid = null;
function pmGridClass(){
  if(_PMGrid) return _PMGrid;
  _PMGrid = L.VectorGrid.Protobuf.extend({
    _getVectorTilePromise: function(coords){
      return _pcl.pm.getZxy(coords.z, coords.x, coords.y).then(function(t){
        if(!t) return {layers:{}};
        var json = new _pcl.VectorTile(new _pcl.Pbf(t.data));
        for(var layerName in json.layers){
          var layer = json.layers[layerName], feats = [];
          for(var i=0; i<layer.length; i++){
            var feat = layer.feature(i);
            feat.geometry = feat.loadGeometry();
            feats.push(feat);
          }
          layer.features = feats;
        }
        return json;
      }).catch(function(){ return {layers:{}}; });
    }
  });
  return _PMGrid;
}
function makePclGrid(parcelStyle, opts){
  const G = pmGridClass();
  return new G('', Object.assign({
    rendererFactory: L.canvas.tile,
    vectorTileLayerStyles: { parcels: parcelStyle },
    maxNativeZoom: PCL_MAXNATIVE,
    minZoom: 0, maxZoom: 22,
    interactive: false
  }, opts || {}));
}
function pclAcres(props){ return Number(props.CALCAC) || Number(props.DEEDAC) || 0; }
function makeLocalPcl(){
  return makePclGrid({weight:.9, color:'#a8442f', opacity:.85,
                      fill:true, fillColor:'#b8342a', fillOpacity:.07});
}
function makeBigPcl(){
  const bigStyle = {weight:1.6, color:'#6d28d9', opacity:.95,
                    fill:true, fillColor:'#7c3aed', fillOpacity:.20};
  // native z12+ tiles only (the from-far-out view is handled by makeBigDots, below)
  return makePclGrid(function(props){ return pclAcres(props) > 500 ? bigStyle : []; });
}

/* Lightweight statewide overview of ALL 500+ ac parcels as centroid DOTS
   (from tn_bigparcels.js -> BIGPARCELS). ~2,650 points, canvas-rendered, so they
   show at ANY zoom (as far out as zoom 8 and beyond); the detailed polygons take
   over at z12+. Clicking a dot gives owner / county / acreage + a TPAD deep-link. */
// ATTOM market land-value $/ac trend block — shown only for parcels ATTOM actually has.
function bigAttomBlock(s){
  if(!s || s.length < 2) return '';
  const ys=s.map(d=>d[0]), vs=s.map(d=>d[1]);
  const y0=ys[0], y1=ys[ys.length-1], v0=vs[0], v1=vs[vs.length-1];
  const mn=Math.min.apply(null,vs), mx=Math.max.apply(null,vs), W=150,H=32,pad=3;
  const sx=i=>pad+(W-2*pad)*(ys[i]-y0)/((y1-y0)||1);
  const sy=v=>H-pad-(H-2*pad)*(v-mn)/((mx-mn)||1);
  let d=''; for(let i=0;i<vs.length;i++) d+=(i?'L':'M')+sx(i).toFixed(1)+' '+sy(vs[i]).toFixed(1);
  const up=v1>=v0, col=up?'#0b7a3b':'#b8342a', pct=v0?Math.round((v1/v0-1)*100):0;
  return '<div style="margin-top:7px;padding-top:6px;border-top:1px solid #e6eaee">'
    +'<div style="color:#0b7a3b;font-size:10.5px;font-weight:700;margin-bottom:2px">ATTOM market land value ($/ac)</div>'
    +'<svg width="'+W+'" height="'+H+'" style="display:block"><path d="'+d+'" fill="none" stroke="'+col+'" stroke-width="1.6"/>'
    +'<circle cx="'+sx(vs.length-1).toFixed(1)+'" cy="'+sy(v1).toFixed(1)+'" r="2.3" fill="'+col+'"/></svg>'
    +'<div style="font-size:11px;margin-top:1px"><b>'+fmtMoney(v0)+'</b>/ac ('+y0+') → <b>'+fmtMoney(v1)+'</b>/ac ('+y1+') '
    +'<span style="color:'+col+';font-weight:700">'+(up?'▲':'▼')+' '+Math.abs(pct)+'%</span></div></div>';
}
function bigDotPopup(rec){
  const [lat,lon,ac,own,co,gis,landMkt,impVal,appr,assd,useVal,lu,yrBuilt,sqft,grade,cond,attom]=rec;
  const totalMkt = (landMkt||0)+(impVal||0);
  const landPerAc = (landMkt>0 && ac>0) ? Math.round(landMkt/ac) : 0;
  const hasAttom = attom && attom.length;
  const greenbelt = (landMkt>0 && appr>0 && appr < landMkt*0.85);   // taxed on greenbelt use-value, below market
  const url = gis ? tpadUrl({GISLINK:gis}) : null;
  const link = url ? '<a href="'+url+'" target="_blank" rel="noopener" style="display:block;margin-top:7px;padding-top:6px;border-top:1px solid #e6eaee;color:#16465f;font-size:11.5px;font-weight:600;text-decoration:none">View full record on TN Property Assessment ↗</a>' : '';
  // Full value breakdown from the county ASSESSMENT_DATA (via GIS link): land MARKET
  // value, building value, total, appraised (tax) / assessed / greenbelt use value,
  // PLUS the ATTOM market land-value trend where ATTOM has the parcel.
  const row=(k,v)=> '<div class="pr"><span>'+k+'</span>'+v+'</div>';
  let body='';
  body+=row('Acreage','<b>'+Number(ac).toLocaleString()+' ac</b>');
  if(landMkt>0) body+=row('Land market value','<b>'+fmtMoney(landMkt)+'</b>');
  if(landPerAc>0) body+=row('Land $/acre',fmtMoney(landPerAc)+'/ac');
  if(impVal>0) body+=row('Building value',fmtMoney(impVal));
  if(totalMkt>0 && impVal>0) body+=row('Total market value','<b>'+fmtMoney(totalMkt)+'</b>');
  if(appr>0) body+=row('Appraised (tax)',fmtMoney(appr)+(greenbelt?' <span style="color:#b8860b;font-size:10.5px">· greenbelt use-value</span>':''));
  if(assd>0) body+=row('Assessed',fmtMoney(assd));
  // building line
  const bd=[];
  if(yrBuilt>0) bd.push('built '+yrBuilt);
  if(sqft>0) bd.push(sqft.toLocaleString()+' sqft');
  if(grade && grade!=='0') bd.push('grade '+esc(grade));
  if(cond && cond!=='0') bd.push(esc(cond));
  const bldgLine = bd.length ? '<div style="color:#6b7680;font-size:11px;margin-top:4px">Building: '+bd.join(' · ')+'</div>' : '';
  return '<div style="font:12px/1.45 -apple-system,Segoe UI,Roboto,sans-serif;min-width:210px">'
    +'<div style="font-weight:700;color:'+(hasAttom?'#0b7a3b':'#4c1d95')+';margin-bottom:3px">'+esc(own||'Parcel')+'</div>'
    +'<div style="color:#6b7680;margin-bottom:5px">'+esc(co)+' County'+(lu?' · '+esc(lu):'')+'</div>'
    +body+bldgLine+bigAttomBlock(attom)
    +'<div style="color:#98a6b2;font-size:10.5px;margin-top:5px">'
      +(hasAttom?'TN assessment (Comptroller) + ATTOM':'TN county assessment (Comptroller)')
      +' · zoom to '+BIG_POLY_MINZ+'+ for the parcel boundary</div>'
    +link+'</div>';
}
function makeBigDots(){
  const rndr = L.canvas({padding:0.5});
  const g = L.layerGroup();
  if(typeof BIGPARCELS === 'undefined') return g;
  BIGPARCELS.forEach(rec=>{
    const hasAttom = rec[16] && rec[16].length;   // green = has ATTOM series, purple = assessment only
    L.circleMarker([rec[0],rec[1]], {renderer:rndr, radius:hasAttom?3.8:3.2,
      fillColor: hasAttom?'#0b7a3b':'#7c3aed', color: hasAttom?'#075e34':'#4c1d95',
      weight:.6, opacity:.9, fillOpacity:.78})
     .addTo(g)
     .on('click', e=>{ L.popup({className:'pclbox',maxWidth:300}).setLatLng(e.latlng).setContent(bigDotPopup(rec)).openOn(map); });
  });
  return g;
}
function makeArcgisPcl(){
  const vs = {};
  ['Parcels','parcels','parcels_86_03_31','Property_Boundaries_86_Counties'].forEach(k=>{
    vs[k] = {weight:.9, color:'#a8442f', opacity:.75,
             fill:true, fillColor:'#b8342a', fillOpacity:.07};
  });
  return L.vectorGrid.protobuf(PCL_TILES, {
    rendererFactory: L.canvas.tile,
    vectorTileLayerStyles: vs,
    maxNativeZoom: 16,
    interactive: false
  });
}
function pclHintText(){
  if(map.getZoom() < PCL_MINZ) return 'Zoom to level '+PCL_MINZ+'+ for parcel detail';
  return (pclMode === 'local')
    ? 'Showing parcels · 86 counties · click a parcel for owner & acreage'
    : 'Showing parcels · 86 of 95 counties · live ArcGIS (no popups)';
}

/* ---------- parcel click -> owner / assessment popup (local mode only) ---------- */
function openParcelPopup(latlng, p){
  const owner = esc(p.OWNER||'') + (p.OWNER2 ? ' / '+esc(p.OWNER2) : '');
  const rows = [
    ['Owner',    owner || '—'],
    ['Situs',    esc(p.ADDRESS||'—')],
    ['County',   esc(p.COUNTY||'—')],
    ['Parcel',   esc(p.PARCELID||p.GISLINK||'—')],
    ['Acreage',  fmtAcre(p.CALCAC!=null ? p.CALCAC : p.DEEDAC)],
    ['Land use', esc(p.LANDUSE||p.CLASS||'—')],
    ['Appraised',fmtMoney(p.APPRAISAL)],
    ['Assessed', fmtMoney(p.ASSESSMENT)],
    ['Last sale',(p.SALEDATE ? esc(p.SALEDATE) : '—') + (Number(p.PRICE)>0 ? ' · '+fmtMoney(p.PRICE) : '')]
  ];
  const url = tpadUrl(p);
  const link = url
    ? '<a href="'+url+'" target="_blank" rel="noopener" style="display:block;margin-top:7px;padding-top:6px;border-top:1px solid #e6eaee;color:#16465f;font-size:11.5px;font-weight:600;text-decoration:none">View full record on TN Property Assessment ↗</a>'
    : '';
  const html = '<div style="font:12px/1.45 -apple-system,Segoe UI,Roboto,sans-serif;min-width:210px">'
    + '<div style="font-weight:700;margin-bottom:5px;color:#a8442f">'+(owner||'Parcel')+'</div>'
    + '<table style="border-collapse:collapse">'
    + rows.map(r => '<tr><td style="color:#6b7680;padding:1px 8px 1px 0;vertical-align:top;white-space:nowrap">'+r[0]+'</td><td style="vertical-align:top">'+r[1]+'</td></tr>').join('')
    + '</table>' + link + '</div>';
  L.popup({className:'pclbox', maxWidth:340}).setLatLng(latlng).setContent(html).openOn(map);
}

/* Deep-link a parcel to its record on the TN Comptroller's property site (TPAD). */
function tpadUrl(p){
  let g = (p.GISLINK || '');
  if(g.length < 15) g = g.padEnd(15, ' ');
  if(g.trim().length < 8) return null;
  const jur = g.slice(0,3);
  const parcelPortion = g.slice(3);
  let si = '000';
  let core = (p.PARCELID || '').trim().replace(/\s+\d{4}$/, '');
  if(core.slice(0,3) === jur) core = core.slice(3).replace(/^\s+/, '');
  const m = core.match(/(\d{3})\s*$/);
  if(m) si = m[1];
  const parcelId  = parcelPortion + ' ' + si;
  const parcelKey = jur + parcelId;
  const params = {
    Jur: jur, PropertyAddress:'', SubdivisionName:'', Query:'', Owner:'',
    PropertyType:'', SortBy:'Owner', SaleDateRangeStart:'', SaleDateRangeEnd:'',
    ControlMap: g.slice(3,8), MapGroup: g.slice(8,10), ParcelNumber: g.slice(10,15),
    GISLink: g
  };
  return 'https://assessment.cot.tn.gov/TPAD/Parcel/Details'
    + '?parcelId='  + encodeURIComponent(parcelId)
    + '&jur='       + jur
    + '&parcelKey=' + encodeURIComponent(parcelKey)
    + '&searchParameters=' + encodeURIComponent(JSON.stringify(params));
}

/* Point-in-polygon hit test straight against the PMTiles geometry. */
const _pclTileCache = new Map();
async function pclFeatureAt(latlng){
  if(!_pcl.ready) return null;
  const z = PCL_MAXNATIVE;
  const p = map.project(latlng, z);
  const tx = Math.floor(p.x / 256), ty = Math.floor(p.y / 256);
  const key = z + '/' + tx + '/' + ty;
  let vt = _pclTileCache.get(key);
  if(vt === undefined){
    try{ const t = await _pcl.pm.getZxy(z, tx, ty); vt = t ? new _pcl.VectorTile(new _pcl.Pbf(t.data)) : null; }
    catch(_){ vt = null; }
    _pclTileCache.set(key, vt);
  }
  if(!vt || !vt.layers.parcels) return null;
  const layer = vt.layers.parcels, extent = layer.extent || 4096;
  const lx = (p.x / 256 - tx) * extent, ly = (p.y / 256 - ty) * extent;
  for(let i = 0; i < layer.length; i++){
    const f = layer.feature(i);
    if(pointInRings(lx, ly, f.loadGeometry())) return f.properties;
  }
  return null;
}
function pointInRings(x, y, rings){            // even-odd across all rings (handles holes/multipart)
  let inside = false;
  for(const ring of rings){
    for(let i = 0, j = ring.length - 1; i < ring.length; j = i++){
      const xi = ring[i].x, yi = ring[i].y, xj = ring[j].x, yj = ring[j].y;
      if(((yi > y) !== (yj > y)) && (x < (xj - xi) * (y - yi) / (yj - yi) + xi)) inside = !inside;
    }
  }
  return inside;
}

/* small helper reused by SVG mini-charts */
function niceStep(mx){ const raw=mx/5, pow=Math.pow(10,Math.floor(Math.log10(raw))), m=raw/pow; return (m<1.5?1:m<3?2:m<7?5:10)*pow; }

/* Robustly fit the map to a layer's bounds. Guards against the common case
   where the map is created before its container has a width (getSize().x===0),
   which makes the first fitBounds pick a bogus zoom. Re-fits on window load and
   after a tick, and whenever the container width was still zero. */
function fitMapTo(layer){
  const doFit=()=>{ map.invalidateSize();
    try{ const b=layer.getBounds(); if(b.isValid()) map.fitBounds(b,{padding:[12,12]}); }catch(_){}
  };
  doFit();
  setTimeout(doFit,150);
  window.addEventListener('load', doFit);
}
