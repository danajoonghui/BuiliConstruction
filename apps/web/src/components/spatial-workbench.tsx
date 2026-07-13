'use client';

import Link from 'next/link';
import { Box, ChevronDown, Crosshair, Layers3, Maximize2, MousePointer2, ScanLine, Search, SplitSquareHorizontal, ZoomIn, ZoomOut } from 'lucide-react';
import { useEffect, useMemo, useRef, useState } from 'react';
import { StatusPill } from './status-pill';
import { useWorkspace } from './demo-mode';
import { PageHeader } from './page-header';
import { ThreeSpatialScene } from './three-spatial-scene';
import { api } from '@/lib/api';

type ViewMode = '2d' | '3d' | 'split' | 'evidence';
const sheets = [
  { discipline:'Architectural', items:[['A1.1','Ground floor architectural plan','Rev 03']] },
  { discipline:'Electrical', items:[['E1.1','Power & lighting plan','Rev 03']] },
  { discipline:'Mechanical', items:[['M1.1','HVAC distribution plan','Rev 03']] }
];
const issueDetails={
  'BUI-1042':{discipline:'Electrical',title:'Garage GFCI receptacle below required elevation',status:'Ready for review',tone:'green' as const,location:'Garage / East wall',source:'E1.1 / Rev 03',observed:'12 in. AFF centerline',required:'18 in. AFF minimum',finding:'The installed box appears 6 in. below Electrical Note 3. The open stud bay allows correction before close-in.',sufficient:true},
  'BUI-1038':{discipline:'Architectural',title:'Office partition offset from approved layout',status:'Evidence required',tone:'amber' as const,location:'Ground floor / Office',source:'A1.1 / Rev 03',observed:'Partition face appears offset west',required:'Align partition with approved dimension string',finding:'The plan pin is located, but a measured offset and wider context photo are still required before routing an action.',sufficient:false},
  'RFI-017':{discipline:'Mechanical',title:'Return-air route conflicts with hall opening',status:'Coordination review',tone:'blue' as const,location:'Ground floor / Hall ceiling',source:'M1.1 / Rev 03',observed:'Return duct crosses the framed opening zone',required:'Maintain the coordinated opening and required airflow area',finding:'The mechanical route is spatially anchored. Section elevation and framing clearance are required before an alternate route is approved.',sufficient:false}
};

const sheetAssets = {
  'A1.1': { preview:'/demo/A1.1-preview.png', issue:'BUI-1038' as const, alt:'Architectural ground floor contract drawing' },
  'E1.1': { preview:'/demo/E1.1-preview.png', issue:'BUI-1042' as const, alt:'Electrical power and lighting contract drawing' },
  'M1.1': { preview:'/demo/M1.1-preview.png', issue:'RFI-017' as const, alt:'Mechanical HVAC distribution contract drawing' },
};

export function SpatialWorkbench() {
  const{demo,projectId}=useWorkspace();
  const [mode,setMode] = useState<ViewMode>('2d'); const [selected,setSelected] = useState<keyof typeof issueDetails>('BUI-1042'); const [sheet,setSheet] = useState('E1.1'); const[zoom,setZoom]=useState(1); const[searchOpen,setSearchOpen]=useState(false); const[sheetQuery,setSheetQuery]=useState(''); const viewerRef=useRef<HTMLDivElement>(null);
  if(!demo)return <LiveSpatialScenes projectId={projectId}/>;
  const selectedInfo=issueDetails[selected];
  const selectedSheet=sheets.flatMap(group=>group.items).find(item=>item[0]===sheet);
  const visibleSheets=sheets.map(group=>({...group,items:group.items.filter(item=>!sheetQuery.trim()||item.join(' ').toLowerCase().includes(sheetQuery.trim().toLowerCase()))})).filter(group=>group.items.length>0);
  return <div className="spatial-workbench">
    <aside className="sheet-browser"><div className="panel-title"><b>Project sheets</b><button aria-label={searchOpen?'Close sheet search':'Search sheets'} aria-expanded={searchOpen} onClick={()=>{setSearchOpen(value=>!value);setSheetQuery('')}}><Search/></button></div>{searchOpen&&<label className="sheet-search"><Search/><input autoFocus value={sheetQuery} onChange={event=>setSheetQuery(event.target.value)} placeholder="Sheet or title" aria-label="Search sheet or title"/></label>}<div className="sheet-scroll">{visibleSheets.map(group=><section key={group.discipline}><h3><ChevronDown/> {group.discipline}<span>{group.items.length}</span></h3>{group.items.map(item=><button key={item[0]} onClick={()=>{const next=item[0] as keyof typeof sheetAssets;setSheet(next);setSelected(sheetAssets[next].issue)}} className={sheet===item[0]?'active':''}><b>{item[0]}</b><span>{item[1]}</span><small>{item[2]}</small></button>)}</section>)}{visibleSheets.length===0&&<p className="sheet-empty">No matching sheets</p>}</div><div className="sheet-legend"><span><i className="dot-elec"/> Coordinated set</span><span><i className="dot-issue"/> Open issue</span></div></aside>
    <section className="viewer-column">
      <div className="viewer-toolbar"><div className="view-tabs" role="tablist" aria-label="Spatial view"><button role="tab" aria-selected={mode==='2d'} className={mode==='2d'?'active':''} onClick={()=>setMode('2d')}><ScanLine/> 2D plan</button><button role="tab" aria-selected={mode==='3d'} className={mode==='3d'?'active':''} onClick={()=>setMode('3d')}><Box/> 3D context</button><button role="tab" aria-selected={mode==='split'} className={mode==='split'?'active':''} onClick={()=>setMode('split')}><SplitSquareHorizontal/> Split</button><button role="tab" aria-selected={mode==='evidence'} className={mode==='evidence'?'active':''} onClick={()=>setMode('evidence')}><Layers3/> Evidence</button></div><div className="viewer-tools"><button title="Select issue pin" aria-label="Select issue pin" onClick={()=>setSelected('BUI-1042')}><MousePointer2/></button><button title="Center view" aria-label="Center view" onClick={()=>setZoom(1)}><Crosshair/></button><button title="Zoom in" aria-label="Zoom in" disabled={zoom>=1.6} onClick={()=>setZoom(value=>Math.min(1.6,Number((value+.15).toFixed(2))))}><ZoomIn/></button><button title="Zoom out" aria-label="Zoom out" disabled={zoom<=.7} onClick={()=>setZoom(value=>Math.max(.7,Number((value-.15).toFixed(2))))}><ZoomOut/></button><button title="Fullscreen" aria-label="Open fullscreen" onClick={()=>viewerRef.current?.requestFullscreen?.()}><Maximize2/></button></div></div>
      <div ref={viewerRef} className={`viewer-canvas viewer-canvas--${mode}`}>
        <div className="viewer-stage" style={{transform:`scale(${zoom})`}}>
        {(mode==='2d'||mode==='split'||mode==='evidence') && <FloorPlan sheet={sheet as keyof typeof sheetAssets} selected={selected} onSelect={setSelected} evidence={mode==='evidence'}/>}
        {(mode==='3d'||mode==='split') && <ThreeSpatialScene selected={selected} onSelect={id=>{if(id in issueDetails)setSelected(id as keyof typeof issueDetails)}}/>}
        </div>
        <div className="viewer-compass"><span>N</span><i/></div>
        <div className="viewer-scale">Metric coordinated set · Sheet {sheet} · {selectedSheet?.[2]||'Revision unavailable'} · {Math.round(zoom*100)}%</div>
      </div>
    </section>
    <aside className="viewer-inspector"><div className="panel-title"><b>Issue inspector</b></div><div className="inspector-scroll"><p className="inspector-eyebrow">{selected} / {selectedInfo.discipline}</p><h2>{selectedInfo.title}</h2><StatusPill tone={selectedInfo.tone}>{selectedInfo.status}</StatusPill><dl><div><dt>Location</dt><dd>{selectedInfo.location}</dd></div><div><dt>Source</dt><dd>{selectedInfo.source}</dd></div><div><dt>Observed</dt><dd>{selectedInfo.observed}</dd></div><div><dt>Required</dt><dd>{selectedInfo.required}</dd></div></dl><section><h3>Spatial confidence</h3><Confidence label="Floor & room" value={99}/><Confidence label="Wall location" value={selected==='BUI-1042'?94:88}/><Confidence label="Source alignment" value={selected==='BUI-1042'?97:91}/></section><section><h3>Finding</h3><p>{selectedInfo.finding}</p></section><div className={`inspector-callout ${selectedInfo.sufficient?'':'inspector-callout--warning'}`}><b>{selectedInfo.sufficient?'Evidence sufficient':'Additional evidence required'}</b><span>{selectedInfo.sufficient?'Context, detail, measurement, time, and location are present.':'Add a measured offset and a wide context photo before routing.'}</span></div></div><div className="inspector-actions"><Link className="button button--secondary" href={`/app/issues/${selected}?demo=1`}>Open issue</Link><Link className="button button--primary" href={`/app/workflows?demo=1&action=punch&issue=${selected}`}>Start punch item</Link></div></aside>
  </div>;
}

type Scene={id:string;source_revision_id:string;version:number;status:string;confidence_json:Record<string,unknown>;created_at:string};
function LiveSpatialScenes({projectId}:{projectId:string}){const[scenes,setScenes]=useState<Scene[]>([]);const[error,setError]=useState('');useEffect(()=>{if(!projectId||['loading','none'].includes(projectId))return;let active=true;api.get<Scene[]>(`/projects/${projectId}/spatial-scenes`).then(data=>{if(active)setScenes(data)}).catch(cause=>{if(active)setError(cause instanceof Error?cause.message:'Spatial scenes could not be loaded.')});return()=>{active=false}},[projectId]);return <div className="page-pad"><PageHeader title="Drawings & 3D" description="Approved spatial scene versions generated from the project drawing record."/>{error&&<p className="inline-error">{error}</p>}<div className="table-scroll"><table className="data-table"><thead><tr><th>Scene</th><th>Source revision</th><th>Version</th><th>Status</th><th>Created</th></tr></thead><tbody>{scenes.map(scene=><tr key={scene.id}><td className="cell-id">{scene.id}</td><td className="cell-id">{scene.source_revision_id}</td><td>v{scene.version}</td><td><StatusPill tone={scene.status==='approved'?'green':scene.status==='failed'?'red':'blue'}>{scene.status}</StatusPill></td><td className="cell-muted">{new Date(scene.created_at).toLocaleString()}</td></tr>)}</tbody></table></div>{scenes.length===0&&!error&&<div className="live-placeholder"><Box/><p><b>No spatial scene is available yet.</b><span>Process a drawing revision to create a plan graph and lightweight 3D scene.</span></p></div>}</div>}

function FloorPlan({sheet,selected,onSelect,evidence}:{sheet:keyof typeof sheetAssets;selected:keyof typeof issueDetails;onSelect:(id:keyof typeof issueDetails)=>void;evidence:boolean}) {
  const asset=sheetAssets[sheet];
  const positions:Record<keyof typeof sheetAssets,{left:string;top:string}>={
    'A1.1':{left:'42%',top:'55%'},
    'E1.1':{left:'22%',top:'76%'},
    'M1.1':{left:'28%',top:'52%'},
  };
  return <div className="drawing-sheet-stage">
    <img src={asset.preview} alt={asset.alt}/>
    <button type="button" style={positions[sheet]} aria-label={`Select ${asset.issue}`} onClick={()=>onSelect(asset.issue)} className={`drawing-sheet-pin drawing-sheet-pin--${sheet[0].toLowerCase()} ${selected===asset.issue?'selected':''}`}><span/>{asset.issue}</button>
    {evidence&&<div className="drawing-evidence-badge"><Layers3/> 3 linked evidence objects</div>}
  </div>;
}
function Confidence({label,value}:{label:string;value:number}){return <div className="confidence-row"><span>{label}</span><i><b style={{width:`${value}%`}}/></i><em>{value}%</em></div>}
