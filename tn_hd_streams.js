/* tn_hd_streams.js — stream / WWC characteristics parsed from TDEC HD report PDFs.
   Shown ONLY on the Last-14-day and Last-30-day live tabs of hd_requests.html.
   Auto-generated: pulls the trailing-30-day determinations from the TDEC ArcGIS
   layer, resolves each report PDF, and extracts the streams & WWC table (STR-/WWC-).
   Includes single-point WWCs (point:true). Regenerate as the window rolls. Generated 2026-07-28 13:47 (local).
   byId[<DETERMINATION_ID>] = {prop, county, features:[{id,len,corps,tdec,point,start:[lat,lon],end:[lat,lon]}]} */
const STREAMS = {
 generatedAt:"2026-07-28 13:47", window:"trailing 30 days (live pull)",
 byId:{
  "35233": {prop:"Crews Site", county:"Williamson", features:[
    {id:"WWC-1", len:"", corps:null, tdec:"WWC", point:false, start:[35.901979,-87.083043], end:[35.90231,-87.080811]},
    {id:"WWC-2", len:"", corps:null, tdec:"WWC", point:false, start:[35.901536,-87.084037], end:[35.901302,-87.084316]},
    {id:"WWC-3", len:"", corps:null, tdec:"WWC", point:false, start:[35.901067,-87.083672], end:[35.901197,-87.084316]},
    {id:"WWC-5", len:"", corps:null, tdec:"WWC", point:false, start:[35.89919,-87.082728], end:[35.899468,-87.081966]},
    {id:"WWC-6", len:"", corps:null, tdec:"WWC", point:true, start:[35.899937,-87.083994], end:[35.899937,-87.083994]},
    {id:"WWC-7", len:"", corps:null, tdec:"WWC", point:false, start:[35.899085,-87.084101], end:[35.899059,-87.084659]},
    {id:"WWC-8", len:"", corps:null, tdec:"WWC", point:false, start:[35.898121,-87.083651], end:[35.897721,-87.084166]},
    {id:"WWC-9", len:"", corps:null, tdec:"WWC", point:false, start:[35.897851,-87.083286], end:[35.897582,-87.083554]},
    {id:"WWC-10", len:"", corps:null, tdec:"WWC", point:false, start:[35.897408,-87.083029], end:[35.897756,-87.084724]},
    {id:"WWC-11", len:"", corps:null, tdec:"WWC", point:true, start:[35.896261,-87.084345], end:[35.896261,-87.084345]},
    {id:"WWC-12", len:"", corps:null, tdec:"WWC", point:false, start:[35.895644,-87.083712], end:[35.896504,-87.082306]},
    {id:"WWC-13", len:"", corps:null, tdec:"WWC", point:false, start:[35.895027,-87.084177], end:[35.894314,-87.085196]},
    {id:"WWC-14", len:"", corps:null, tdec:"WWC", point:false, start:[35.894239,-87.082903], end:[35.894039,-87.082549]},
    {id:"WWC-16", len:"", corps:null, tdec:"WWC", point:false, start:[35.89277,-87.083569], end:[35.893161,-87.083043]},
    {id:"WWC-17", len:"", corps:null, tdec:"WWC", point:false, start:[35.897906,-87.082306], end:[35.897602,-87.082177]},
    {id:"WWC-18", len:"", corps:null, tdec:"WWC", point:false, start:[35.894268,-87.085246], end:[35.894163,-87.085428]},
  ]},
  "35255": {prop:"Copperhill Farms Project", county:"Putnam", features:[
    {id:"STR-1", len:"1,471.84 ft", corps:null, tdec:"Stream", point:false, start:[36.163504,-85.635527], end:[36.161893,-85.631325]},
    {id:"STR-2", len:"861.82 ft", corps:null, tdec:"Stream", point:false, start:[36.160134,-85.632286], end:[36.162044,-85.633315]},
    {id:"WWC-1", len:"352.31 ft", corps:null, tdec:"WWC", point:false, start:[36.160546,-85.636979], end:[36.16128,-85.637737]},
  ]},
  "35258": {prop:"Norton Creek Property", county:"Sevier", features:[
    {id:"STR-1", len:"", corps:null, tdec:"Stream", point:false, start:[35.726282,-83.555241], end:[35.726331,-83.555151]},
    {id:"STR-3", len:"", corps:null, tdec:"Stream", point:false, start:[35.729469,-83.543662], end:[35.7292,-83.543963]},
    {id:"STR-2", len:"", corps:null, tdec:"Stream", point:false, start:[35.725595,-83.554901], end:[35.725816,-83.555127]},
  ]},
  "35265": {prop:"1124 Blairfield Drive", county:"Davidson", features:[
    {id:"STR-1", len:"", corps:null, tdec:"Stream", point:false, start:[36.020025,-86.648818], end:[36.020492,-86.649997]},
  ]},
  "35295": {prop:"2089 Highway 41A S", county:"Rutherford", features:[
    {id:"WWC-1", len:"", corps:null, tdec:"WWC", point:false, start:[35.714676,-86.632387], end:[35.714921,-86.632149]},
  ]},
  "35301": {prop:"7924 Nolensville Hwy", county:"Williamson", features:[
    {id:"WWC-1", len:"", corps:null, tdec:"WWC", point:true, start:[35.863335,-86.655038], end:[35.863335,-86.655038]},
  ]},
  "35319": {prop:"4633 Columbia Pike", county:"Williamson", features:[
    {id:"WWC-1", len:"", corps:null, tdec:"WWC", point:true, start:[35.808598,-86.900846], end:[35.808598,-86.900846]},
  ]},
 },
 byName:{}
};
