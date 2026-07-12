'use client';

import Link from 'next/link';
import { ArrowLeft, Check, LoaderCircle, MapPin, RefreshCw, ShieldCheck, Sparkles } from 'lucide-react';
import { useSearchParams } from 'next/navigation';
import { useEffect, useState } from 'react';
import { api, ApiError } from '@/lib/api';
import { DemoIssueWorkspace } from './demo-issue-workspace';
import { useDemoMode } from './demo-mode';
import { StatusPill } from './status-pill';

type ApiIssue = {
  id:string; number:string; title:string; description:string; issue_type:string; status:string; priority:string;
  observed_condition:string; expected_condition:string; difference:string; classification:string; recommended_action:string;
  evidence_sufficiency:string; missing_evidence:string[]; location_json:Record<string,unknown>; assigned_to:string|null;
  approved_by:string|null; created_at:string; updated_at:string;
};

export function IssueDetailRouter({ id }: { id: string }) {
  const workspaceDemo = useDemoMode(); const searchParams=useSearchParams(); const demo=workspaceDemo||searchParams.get('demo')==='1'; const [issue,setIssue]=useState<ApiIssue|null>(null); const [error,setError]=useState(''); const [loading,setLoading]=useState(!demo);
  useEffect(()=>{ if(demo)return; let active=true; setLoading(true); api.get<ApiIssue>(`/issues/${encodeURIComponent(id)}`).then(data=>{if(active)setIssue(data)}).catch(cause=>{if(active)setError(cause instanceof ApiError?cause.message:'The issue could not be loaded.')}).finally(()=>{if(active)setLoading(false)});return()=>{active=false}},[demo,id]);
  if(demo && (id==='BUI-1042'||id==='demo-bui-1042')) return <DemoIssueWorkspace/>;
  if(demo) return <GenericError message="This issue is not part of the demo workspace."/>;
  if(loading) return <div className="page-loader"><span/><span/><span/></div>;
  if(error||!issue) return <GenericError message={error||'Issue not found.'}/>;
  return <GenericIssue issue={issue} onUpdate={setIssue}/>;
}

function GenericError({message}:{message:string}){return <div className="generic-issue-error"><span>Issue unavailable</span><h1>{message}</h1><Link className="button button--secondary" href="/app/issues"><ArrowLeft/> Back to issues</Link></div>}
function GenericIssue({issue,onUpdate}:{issue:ApiIssue;onUpdate:(issue:ApiIssue)=>void}){
  const [working,setWorking]=useState(false); const location=Object.values(issue.location_json||{}).filter(value=>typeof value==='string').join(' / ')||'Location not assigned';
  async function analyze(){setWorking(true);try{await api.post(`/issues/${issue.id}/analyze`,{});onUpdate(await api.get<ApiIssue>(`/issues/${issue.id}`))}finally{setWorking(false)}}
  async function approve(){setWorking(true);try{await api.post(`/issues/${issue.id}/approve`,{});onUpdate(await api.get<ApiIssue>(`/issues/${issue.id}`))}finally{setWorking(false)}}
  return <div className="generic-issue-detail"><header><Link href="/app/issues"><ArrowLeft/> Issues</Link><div><span>{issue.number} / {issue.issue_type.replaceAll('_',' ')}</span><StatusPill tone={issue.status.includes('REVIEW')?'green':'neutral'}>{issue.status.replaceAll('_',' ')}</StatusPill></div><h1>{issue.title}</h1><p><MapPin/> {location}</p></header><div className="generic-issue-actions"><button className="button button--secondary" onClick={analyze} disabled={working}>{working?<LoaderCircle className="spin"/>:<Sparkles/>} Analyze again</button><button className="button button--primary" onClick={approve} disabled={working||Boolean(issue.approved_by)}><Check/> {issue.approved_by?'Approved':'Approve issue'}</button></div><main><section><label>Observed condition</label><p>{issue.observed_condition||'No observed condition has been recorded.'}</p></section><section><label>Current requirement</label><p>{issue.expected_condition||'No controlling requirement has been linked.'}</p></section><section className="generic-difference"><label>Verified difference</label><p>{issue.difference||'Analysis has not established a difference.'}</p></section><section><label>Classification</label><h2>{issue.classification?.replaceAll('_',' ')||'Unclassified'}</h2><p>{issue.description}</p></section></main><aside><div><ShieldCheck/><span><b>Evidence sufficiency</b><small>{issue.evidence_sufficiency?.replaceAll('_',' ')||'Not assessed'}</small></span></div>{issue.missing_evidence?.length>0&&<ul>{issue.missing_evidence.map(item=><li key={item}>{item}</li>)}</ul>}<div><RefreshCw/><span><b>Recommended action</b><small>{issue.recommended_action?.replaceAll('_',' ')||'Human review required'}</small></span></div><p>Last updated {new Date(issue.updated_at).toLocaleString()}</p></aside></div>
}
