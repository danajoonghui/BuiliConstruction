'use client';
import Link from 'next/link';
import { ArrowRight, Building2, ChevronDown, ListFilter, MapPin, Plus, Search } from 'lucide-react';
import { useEffect, useState } from 'react';
import { PageHeader } from '@/components/page-header';
import { useWorkspace } from '@/components/demo-mode';
import { projects as demoProjects } from '@/lib/demo-data';
import type { Project } from '@/lib/types';
import { api } from '@/lib/api';

export default function ProjectsPage() {
  const {demo}=useWorkspace(); const [projects,setProjects]=useState<Project[]>(demo?demoProjects:[]); const [error,setError]=useState('');
  useEffect(()=>{if(demo){setProjects(demoProjects);return}let active=true;api.get<Array<{id:string;name:string;code:string;address:string;status:string;metadata_json?:Record<string,unknown>;created_at:string}>>('/projects').then(rows=>{if(active)setProjects(rows.map(row=>({id:row.id,name:row.name,code:row.code,location:row.address,phase:row.status,progress:Number(row.metadata_json?.progress||0),openIssues:Number(row.metadata_json?.open_issues||0),evidenceCoverage:Number(row.metadata_json?.evidence_coverage||0),updatedAt:new Date(row.created_at).toLocaleDateString()})))}).catch(cause=>{if(active)setError(cause instanceof Error?cause.message:'Projects could not be loaded.')});return()=>{active=false}},[demo]);
  return <div className="page-pad"><PageHeader title="Projects" description="Manage active work, project context, members, and integrations." actions={<button className="button button--primary"><Plus size={14}/> New project</button>}/>
    <div className="filter-row"><div className="table-search"><Search/><input placeholder="Search projects" aria-label="Search projects"/></div><button className="filter-button">Active projects <ChevronDown/></button><button className="filter-button"><ListFilter/> All phases</button><span className="filter-spacer"/><button className="filter-button">Sort: Recently updated <ChevronDown/></button></div>
    <div className="project-list-head"><span>Project</span><span>Phase</span><span>Progress</span><span>Open issues</span><span>Evidence</span><span>Updated</span></div>
    {error&&<p className="inline-error">{error}</p>}<div className="project-list">{projects.map(project=><Link key={project.id} href="/app" className="project-row"><span className="project-icon"><Building2/></span><div className="project-name"><b>{project.name}</b><small><MapPin/> {project.location||'Location not set'} / {project.code}</small></div><span className="project-phase">{project.phase}</span><span className="project-progress"><i><b style={{width:`${project.progress}%`}}/></i><em>{project.progress}%</em></span><strong>{String(project.openIssues).padStart(2,'0')}</strong><strong>{project.evidenceCoverage}%</strong><span className="cell-muted">{project.updatedAt}</span><ArrowRight/></Link>)}</div>
    <section className="archived-prompt"><div><h2>Completed projects</h2><p>Retain your source record, issued reports, approvals, and audit history after closeout.</p></div><button className="button button--secondary">View archive</button></section>
  </div>;
}
