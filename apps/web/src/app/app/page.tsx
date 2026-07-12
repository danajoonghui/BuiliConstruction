'use client';
import Image from 'next/image';
import Link from 'next/link';
import { ArrowRight, Camera, CheckCircle2, ChevronRight, Clock3, FileCheck2, MoreHorizontal, Plus, Upload } from 'lucide-react';
import { useEffect, useState } from 'react';
import { PageHeader } from '@/components/page-header';
import { useWorkspace } from '@/components/demo-mode';
import { Discipline, StatusPill } from '@/components/status-pill';
import { issues as demoIssues } from '@/lib/demo-data';
import type { Issue } from '@/lib/types';
import { api } from '@/lib/api';

export default function OverviewPage() {
  const{demo,projectId,userName}=useWorkspace();const[issues,setIssues]=useState<Array<Issue&{routeId?:string}>>(demo?demoIssues:[]);
  useEffect(()=>{if(demo){setIssues(demoIssues);return}if(!projectId||['loading','none'].includes(projectId))return;let active=true;api.get<Array<{id:string;number:string;title:string;issue_type:string;status:string;priority:string;assigned_to:string|null;location_json:Record<string,unknown>;updated_at:string}>>(`/projects/${projectId}/issues`).then(rows=>{if(active)setIssues(rows.slice(0,5).map(row=>({id:row.number,routeId:row.id,title:row.title,type:'RFI candidate',discipline:'ARCH',location:Object.values(row.location_json||{}).filter(value=>typeof value==='string').join(' / ')||'Location not assigned',status:row.status==='ready_for_review'?'Ready for review':'Open',priority:row.priority==='high'?'High':'Medium',assignee:row.assigned_to||'Unassigned',updatedAt:new Date(row.updated_at).toLocaleDateString()})))});return()=>{active=false}},[demo,projectId]);
  return (
    <div className="page-pad overview-page">
      <PageHeader eyebrow="Project workspace" title={`Good evening, ${userName.split(' ')[0]||'there'}`} description="Here is what needs attention in the current project." actions={<><Link className="button button--secondary" href="/app/documents"><Upload size={14}/> Upload</Link><Link className="button button--primary" href="/app/capture"><Camera size={14}/> Capture evidence</Link></>}/>
      <section className="metrics-strip" aria-label="Project metrics">
        <div className="metric"><label>Open issues</label><strong>{String(issues.filter(item=>item.status!=='Closed').length).padStart(2,'0')}</strong><small>{issues.filter(item=>item.status==='Ready for review').length} ready for review</small></div>
        <div className="metric"><label>Evidence coverage</label><strong>{demo?'92%':'—'}</strong><small>{demo?'+8% this week':'Calculated after verification'}</small></div>
        <div className="metric"><label>RFI drafts</label><strong>{demo?'03':'—'}</strong><small>{demo?'1 due today':'No static estimate'}</small></div>
        <div className="metric"><label>Model sync</label><strong>{demo?'2d':'—'}</strong><small>{demo?'since latest revision':'Awaiting model metadata'}</small></div>
      </section>
      <div className="workspace-grid">
        <section>
          <div className="section-heading"><h2>Issues requiring attention</h2><Link href="/app/issues">View all <ArrowRight size={12}/></Link></div>
          <div className="table-scroll"><table className="data-table"><thead><tr><th>ID</th><th>Issue</th><th>Location</th><th>Status</th><th>Owner</th></tr></thead><tbody>{issues.slice(0,4).map(issue => <tr key={issue.routeId||issue.id}><td className="cell-id">{issue.id}</td><td className="cell-title"><Link href={`/app/issues/${issue.routeId||issue.id}${demo?'?demo=1':''}`}>{issue.title}</Link><small><Discipline value={issue.discipline}/> / {issue.type}</small></td><td className="cell-muted">{issue.location}</td><td><StatusPill tone={statusTone(issue.status)}>{issue.status}</StatusPill></td><td className="cell-muted">{issue.assignee}</td></tr>)}</tbody></table></div>
          <div className="section-heading overview-gap"><h2>Drawing & model readiness</h2><Link href="/app/documents">Manage revisions <ArrowRight size={12}/></Link></div>
          {demo?<div className="readiness-list">
            <Readiness discipline="Architectural" status="Current" detail="A-202 Rev 05 · Scene synced" pct={100}/>
            <Readiness discipline="Electrical" status="Review required" detail="E-1.1 Rev 03 · 1 changed note" pct={92}/>
            <Readiness discipline="Mechanical" status="Current" detail="M-202 Rev 03 · Scene synced" pct={100}/>
            <Readiness discipline="Fire protection" status="Processing" detail="FP-202 Rev 02 · Parsing sheets" pct={68}/>
          </div>:<div className="live-placeholder"><FileCheck2/><p><b>Readiness is calculated from approved revisions.</b><span>Upload or approve a drawing revision to establish the current set.</span></p><Link href="/app/documents">Open documents</Link></div>}
        </section>
        <aside>
          <div className="section-heading"><h2>Latest field capture</h2><Link href="/app/evidence">All evidence</Link></div>
          {demo?<Link className="latest-evidence" href="/app/issues/BUI-1042?demo=1">
            <Image src="/demo/box-elevation-measurement-thumb.webp" alt="Tape measurement beside garage GFCI box" width={800} height={600}/>
            <div className="latest-evidence__overlay"><span>3 photos · 1 voice note</span><b>Garage east wall</b><small>Captured by Mike Alvarez · 18 min ago</small></div>
          </Link>:<div className="live-placeholder live-placeholder--image"><Camera/><p><b>No capture selected.</b><span>The latest spatially linked evidence will appear here.</span></p><Link href="/app/capture">Capture evidence</Link></div>}
          <div className="section-heading overview-gap"><h2>Recent activity</h2><button disabled title="Activity filters are not configured" aria-label="Additional activity actions"><MoreHorizontal/></button></div>
          {demo?<div className="activity-list">
            <Activity icon={<FileCheck2/>} title="Jordan marked BUI-1042 ready for review" time="18 min ago"/>
            <Activity icon={<Upload/>} title="Mike uploaded three field photos" time="24 min ago"/>
            <Activity icon={<CheckCircle2/>} title="E-1.1 Rev 03 source was verified" time="32 min ago"/>
            <Activity icon={<Clock3/>} title="RFI-017 response due tomorrow" time="1 hr ago"/>
          </div>:<div className="live-placeholder"><Clock3/><p><b>Activity is project-specific.</b><span>Verified events will appear as the team works.</span></p></div>}
        </aside>
      </div>
    </div>
  );
}

function Readiness({ discipline, status, detail, pct }: { discipline: string; status: string; detail: string; pct: number }) { return <div className="readiness-row"><div><b>{discipline}</b><small>{detail}</small></div><span><i style={{width:`${pct}%`}}/></span><em>{status}</em><ChevronRight/></div>; }
function Activity({icon,title,time}:{icon:React.ReactNode;title:string;time:string}) { return <div className="activity-row"><span>{icon}</span><div><b>{title}</b><small>{time}</small></div></div>; }
function statusTone(status:string): 'green'|'amber'|'blue'|'neutral' { if(status==='Ready for review')return 'green';if(status==='Evidence required')return 'amber';if(status==='Issued')return 'blue';return 'neutral'; }
