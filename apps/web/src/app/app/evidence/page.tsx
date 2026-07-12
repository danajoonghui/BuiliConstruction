'use client';
import Image from 'next/image';
import Link from 'next/link';
import { Camera, ChevronDown, FileAudio, Film, Image as ImageIcon, ListFilter, MapPin, Mic2, Plus, Search, UploadCloud } from 'lucide-react';
import { useEffect, useState } from 'react';
import { PageHeader } from '@/components/page-header';
import { useWorkspace } from '@/components/demo-mode';
import { StatusPill } from '@/components/status-pill';
import { api } from '@/lib/api';

type EvidenceCard = {id?:string;type:string;src?:string;title:string;location:string;time:string;linked:boolean;creator?:string};
const demoItems: EvidenceCard[] = [
  {type:'Photo',src:'/demo/garage-east-wall-context-thumb.webp',title:'Garage east wall context',location:'Garage · East wall',time:'18 min ago',linked:true},
  {type:'Photo',src:'/demo/receptacle-rough-in-detail-thumb.webp',title:'GFCI rough-in detail',location:'Garage · East wall',time:'18 min ago',linked:true},
  {type:'Measurement',src:'/demo/box-elevation-measurement-thumb.webp',title:'Box elevation measurement',location:'Garage · East wall',time:'17 min ago',linked:true},
  {type:'Voice note',title:'Foreman field note',location:'Garage · East wall',time:'17 min ago',linked:true},
  {type:'Photo',title:'Panel clearance overview',location:'Electrical room E-101',time:'Yesterday',linked:true},
  {type:'Video',title:'Level 2 MEP walk',location:'Level 2 · North zone',time:'Yesterday',linked:false},
  {type:'Photo',title:'Partition offset detail',location:'Level 1 · West corridor',time:'2 days ago',linked:true},
  {type:'Photo',title:'Ceiling tile condition',location:'Level 2 · Open office',time:'2 days ago',linked:false}
];

export default function EvidencePage(){const{demo,projectId}=useWorkspace();const[items,setItems]=useState<EvidenceCard[]>(demo?demoItems:[]);const[error,setError]=useState('');useEffect(()=>{if(demo){setItems(demoItems);return}if(!projectId||['loading','none'].includes(projectId))return;let active=true;api.get<Array<{id:string;kind:string;title:string;location_json:Record<string,unknown>;captured_at:string|null;created_at:string;analysis_json:Record<string,unknown>;created_by:string}>>(`/projects/${projectId}/evidence`).then(rows=>{if(active)setItems(rows.map(row=>({id:row.id,type:typeLabel(row.kind),title:row.title,location:Object.values(row.location_json||{}).filter(value=>typeof value==='string').join(' / ')||'Location needed',time:new Date(row.captured_at||row.created_at).toLocaleDateString(),linked:Object.keys(row.location_json||{}).length>0,creator:row.created_by}))) }).catch(cause=>{if(active)setError(cause instanceof Error?cause.message:'Evidence could not be loaded.')});return()=>{active=false}},[demo,projectId]);return <div className="page-pad"><PageHeader title="Field evidence" description="Photos, video, voice, and measurements—preserved with location, time, source, and chain of custody." actions={<><button className="button button--secondary"><Plus size={14}/> Import</button><Link href="/app/capture" className="button button--primary"><Camera size={14}/> Capture evidence</Link></>}/>
  <div className="evidence-summary"><span><b>{demo?'28':items.length}</b> evidence assets</span><span><b>{demo?'24':items.filter(item=>item.linked).length}</b> spatially linked</span><span><b>{demo?'03':items.filter(item=>!item.linked).length}</b> require location</span><span><b>{demo?'01':'—'}</b> awaiting analysis</span></div>
  <div className="filter-row"><div className="table-search"><Search/><input placeholder="Search evidence"/></div><button className="filter-button"><ListFilter/> All types</button><button className="filter-button">All locations <ChevronDown/></button><button className="filter-button">Any link status <ChevronDown/></button><span className="filter-spacer"/><button className="filter-button">Newest first <ChevronDown/></button></div>
  {error&&<p className="inline-error">{error}</p>}<div className="evidence-gallery">{items.map((item,index)=><Link href={demo&&index<4?'/app/issues/BUI-1042?demo=1':'/app/evidence'} key={item.id||`${item.title}-${index}`} className="evidence-card"><div className={`evidence-media ${!item.src?'evidence-media--placeholder':''}`}>{item.src?<Image src={item.src} alt={item.title} width={700} height={520}/>:<MediaIcon type={item.type}/>}<span className="media-kind"><MediaIcon type={item.type}/>{item.type}</span><i className={item.linked?'linked':'unlinked'} title={item.linked?'Spatially linked':'Location needed'}/></div><div className="evidence-card__copy"><b>{item.title}</b><span><MapPin/> {item.location}</span><small>{item.creator||'Mike Alvarez'} / {item.time}</small>{item.linked?<StatusPill tone="green">Location linked</StatusPill>:<StatusPill tone="amber">Location needed</StatusPill>}</div></Link>)}</div>
  <button className="evidence-upload-row"><UploadCloud/><span><b>Upload evidence from another device</b><small>Original files are checksum-verified and stored without modification.</small></span><strong>Choose files</strong></button>
 </div>}
function MediaIcon({type}:{type:string}){const normalized=type.toLowerCase();if(normalized==='voice note')return <Mic2/>;if(normalized==='video')return <Film/>;return <ImageIcon/>}
function typeLabel(value:string){return value.toLowerCase().replaceAll('_',' ').replace(/\b\w/g,letter=>letter.toUpperCase())}
