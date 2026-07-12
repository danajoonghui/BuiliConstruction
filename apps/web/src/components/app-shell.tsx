'use client';

import Link from 'next/link';
import { usePathname, useRouter, useSearchParams } from 'next/navigation';
import { Bell, BookOpen, Building2, Camera, Check, ChevronDown, CircleHelp, ClipboardCheck, FileClock, Files, FolderKanban, Grid3X3, Home, LogOut, Menu, PanelLeftClose, Search, Settings, ShieldCheck, Sparkles, Upload, UserRound, X } from 'lucide-react';
import { useEffect, useState } from 'react';
import { Brand } from './brand';
import { DemoModeProvider } from './demo-mode';
import { demoUser, projects as demoProjects } from '@/lib/demo-data';
import { api, clearCsrfToken, primeCsrfToken } from '@/lib/api';

const primary = [
  { href: '/app', label: 'Overview', icon: Home },
  { href: '/app/projects', label: 'Projects', icon: FolderKanban },
  { href: '/app/documents', label: 'Documents', icon: Files, count: '143' },
  { href: '/app/spatial', label: 'Drawings & 3D', icon: Grid3X3 }
];
const field = [
  { href: '/app/evidence', label: 'Field evidence', icon: Camera, count: '28' },
  { href: '/app/issues', label: 'Issues', icon: ClipboardCheck, count: '7' },
  { href: '/app/capture', label: 'Capture', icon: Upload }
];
const output = [
  { href: '/app/workflows', label: 'RFI / Punch / Change', icon: BookOpen },
  { href: '/app/reports', label: 'Reports', icon: FileClock }
];

type Account = { displayName: string; email: string; initials: string; role: string; organization: string };
type ShellProject = { id: string; organizationId:string; name: string; code: string; address: string; status: string };
const demoAccount: Account = { displayName: demoUser.name, email: 'jordan@demo.builiconstruction.com', initials: demoUser.initials, role: demoUser.role, organization: demoUser.company };
const demoShellProjects: ShellProject[] = demoProjects.map(project => ({ id: project.id, organizationId:'northstar-builders', name: project.name, code: project.code, address: project.location, status: project.phase }));
const emptyAccount: Account = { displayName: 'Loading account', email: '', initials: '--', role: '', organization: '' };
const emptyProject: ShellProject = { id: 'loading', organizationId:'', name: 'Loading project', code: '--', address: '', status: '' };

export function AppShell({ children }: { children: React.ReactNode }) {
  const pathname = usePathname(); const router = useRouter(); const searchParams=useSearchParams(); const queryDemo=searchParams.get('demo')==='1';
  const [menuOpen, setMenuOpen] = useState(false); const [demo, setDemo] = useState(false); const [demoBannerVisible,setDemoBannerVisible]=useState(true); const [access, setAccess] = useState<'checking'|'allowed'>('checking');
  const [account, setAccount] = useState<Account>(emptyAccount); const [availableProjects, setAvailableProjects] = useState<ShellProject[]>([]); const [currentProject, setCurrentProject] = useState<ShellProject>(emptyProject);
  const [accountOpen,setAccountOpen]=useState(false); const [projectOpen,setProjectOpen]=useState(false);

  useEffect(() => {
    let active = true;
    const isDemo = process.env.NEXT_PUBLIC_DEMO_MODE === 'true' || queryDemo || sessionStorage.getItem('buili-demo') === '1';
    if (isDemo) {
      sessionStorage.setItem('buili-demo', '1'); setDemo(true); setAccount(demoAccount); setAvailableProjects(demoShellProjects); setCurrentProject(demoShellProjects[1]); setAccess('allowed'); return;
    }
    setDemo(false); setAccess('checking');
    Promise.all([
      api.get<{ id:string; email:string; display_name:string; avatar_url?:string }>('/auth/me'),
      api.get<Array<{id:string;name:string}>>('/organizations'),
      api.get<Array<{id:string;organization_id:string;name:string;code:string;address:string;status:string}>>('/projects'),
      primeCsrfToken()
    ]).then(([user,organizations,loadedProjects]) => {
      if (!active) return;
      const initials = user.display_name.split(/\s+/).map(part => part[0]).join('').slice(0,2).toUpperCase();
      setAccount({ displayName:user.display_name, email:user.email, initials, role:'Project member', organization:organizations[0]?.name || 'Your organization' });
      const shellProjects=loadedProjects.map(project=>({...project,organizationId:project.organization_id})); setAvailableProjects(shellProjects);
      const selectedId = localStorage.getItem('buili-current-project');
      setCurrentProject(shellProjects.find(project => project.id === selectedId) || shellProjects[0] || { id:'none',organizationId:organizations[0]?.id||'', name:'Select a project', code:'--', address:'', status:'' });
      setAccess('allowed');
    }).catch(() => { if (active) router.replace(`/login?returnTo=${encodeURIComponent(pathname)}`); });
    return () => { active = false; };
  }, [pathname, queryDemo, router]);

  function chooseProject(project: ShellProject) { setCurrentProject(project); localStorage.setItem('buili-current-project',project.id); setProjectOpen(false); router.push('/app'); }
  async function signOut() { try { await api.post('/auth/logout', {}); } finally { clearCsrfToken(); sessionStorage.removeItem('buili-demo'); router.replace('/login'); router.refresh(); } }
  const activeDemo=demo||queryDemo||process.env.NEXT_PUBLIC_DEMO_MODE==='true';
  const visibleAccount=activeDemo&&account===emptyAccount?demoAccount:account;
  const visibleProjects=activeDemo&&availableProjects.length===0?demoShellProjects:availableProjects;
  const visibleProject=activeDemo&&currentProject.id==='loading'?demoShellProjects[1]:currentProject;
  const projectInitials = visibleProject.code === '--' ? 'PR' : visibleProject.code.slice(0,2).toUpperCase();

  return (
    <DemoModeProvider demo={activeDemo} organizationId={visibleProject.organizationId} projectId={visibleProject.id} projectName={visibleProject.name} userName={visibleAccount.displayName}>
      <div className="product-shell">
        <a href="#workspace" className="skip-link">Skip to workspace</a>
        <header className="global-bar">
          <div className="global-left"><Brand compact href="/app"/><span className="global-product">BUILI</span><span className="global-divider">/</span><button className="global-project" onClick={()=>{setProjectOpen(!projectOpen);setAccountOpen(false)}} aria-expanded={projectOpen}><b>{visibleProject.name}</b><ChevronDown size={13}/></button></div>
          <div className="global-actions"><button aria-label="App switcher"><Grid3X3/></button><button aria-label="Help"><CircleHelp/></button><button aria-label="Notifications" className="notification-button"><Bell/><i/></button><button onClick={()=>{setAccountOpen(!accountOpen);setProjectOpen(false)}} className="avatar-button" aria-label="Open account menu" aria-expanded={accountOpen}>{visibleAccount.initials}</button></div>
          {projectOpen && <ProjectMenu projects={visibleProjects} current={visibleProject.id} choose={chooseProject}/>}
          {accountOpen && <AccountMenu account={visibleAccount} signOut={signOut}/>}
        </header>
        {activeDemo && demoBannerVisible && <div className="demo-banner"><Sparkles size={14}/><b>Demo workspace</b><span>You are exploring a representative project as {demoUser.name}.</span><Link href="/signup">Create your own workspace</Link><button aria-label="Dismiss demo notice" onClick={() => setDemoBannerVisible(false)}><X size={14}/></button></div>}
        <div className={`shell-body ${activeDemo && demoBannerVisible ? 'shell-body--demo' : ''}`}>
          <aside className={`app-sidebar ${menuOpen ? 'app-sidebar--open' : ''}`}>
            <button className="sidebar-project" onClick={()=>setProjectOpen(!projectOpen)} aria-expanded={projectOpen}><span>{projectInitials}</span><div><b>{visibleProject.name}</b><small>{visibleProject.address || 'No project location'} / {visibleProject.status || 'Setup'}</small></div><ChevronDown size={14}/></button>
            <NavGroup label="Workspace" items={primary} pathname={pathname} close={() => setMenuOpen(false)} showCounts={activeDemo}/><NavGroup label="Field" items={field} pathname={pathname} close={() => setMenuOpen(false)} showCounts={activeDemo}/><NavGroup label="Actions" items={output} pathname={pathname} close={() => setMenuOpen(false)} showCounts={activeDemo}/>
            <div className="sidebar-spacer"/><Link className={pathname.startsWith('/app/audit') ? 'side-link active' : 'side-link'} href="/app/audit"><ShieldCheck/><span>Audit trail</span></Link><Link className={pathname.startsWith('/app/settings') ? 'side-link active' : 'side-link'} href="/app/settings"><Settings/><span>Settings</span></Link>
            <button className="sidebar-user" onClick={()=>setAccountOpen(!accountOpen)}><span>{visibleAccount.initials}</span><div><b>{visibleAccount.displayName}</b><small>{visibleAccount.role}</small></div><PanelLeftClose size={15}/></button>
          </aside>
          <div className="workspace-column"><div className="workspace-topbar"><button className="mobile-nav-trigger" onClick={() => setMenuOpen(!menuOpen)} aria-expanded={menuOpen} aria-label="Open navigation"><Menu/></button><div className="breadcrumbs"><span>{visibleProject.name}</span><b>/</b><strong>{currentLabel(pathname)}</strong></div><div className="workspace-tools"><button className="global-search"><Search/><span>Search project</span><kbd>Ctrl K</kbd></button><button className="icon-button"><Bell/></button></div></div><main id="workspace" className="workspace-main">{access==='allowed'||activeDemo?children:<div className="session-check" role="status" aria-label="Checking your session"/>}</main></div>
        </div>
        {menuOpen && <button className="sidebar-scrim" onClick={() => setMenuOpen(false)} aria-label="Close navigation"/>}
        <nav className="mobile-bottom-nav" aria-label="Mobile navigation"><MobileLink href="/app" label="Home" icon={Home} pathname={pathname}/><MobileLink href="/app/evidence" label="Evidence" icon={Camera} pathname={pathname}/><Link href="/app/capture" className="capture-fab" aria-label="Capture field evidence"><Upload/></Link><MobileLink href="/app/issues" label="Issues" icon={ClipboardCheck} pathname={pathname}/><MobileLink href="/app/projects" label="Projects" icon={Building2} pathname={pathname}/></nav>
      </div>
    </DemoModeProvider>
  );
}

function ProjectMenu({projects,current,choose}:{projects:ShellProject[];current:string;choose:(project:ShellProject)=>void}) { return <div className="shell-popover project-popover"><p>Switch project</p>{projects.map(project=><button key={project.id} onClick={()=>choose(project)}><span>{project.code.slice(0,2)}</span><div><b>{project.name}</b><small>{project.code} / {project.status}</small></div>{project.id===current&&<Check/>}</button>)}<Link href="/app/projects">View all projects</Link></div>; }
function AccountMenu({account,signOut}:{account:Account;signOut:()=>void}) { return <div className="shell-popover account-popover"><header><span>{account.initials}</span><div><b>{account.displayName}</b><small>{account.email}</small></div></header><p>{account.role} / {account.organization}</p><Link href="/app/settings"><Settings/> Settings</Link><button onClick={signOut}><LogOut/> Sign out</button></div>; }
function NavGroup({ label, items, pathname, close, showCounts }: { label: string; items: typeof primary; pathname: string; close: () => void; showCounts:boolean }) { return <div className="nav-group"><p>{label}</p>{items.map(({ href, label: itemLabel, icon: Icon, count }) => { const active = href === '/app' ? pathname === href : pathname.startsWith(href); return <Link onClick={close} className={`side-link ${active ? 'active' : ''}`} key={href} href={href}><Icon/><span>{itemLabel}</span>{showCounts&&count&&<small>{count}</small>}</Link>; })}</div>; }
function MobileLink({ href, label, icon: Icon, pathname }: { href: string; label: string; icon: typeof Home; pathname: string }) { const active = href === '/app' ? pathname === href : pathname.startsWith(href); return <Link href={href} className={active ? 'active' : ''}><Icon/><span>{label}</span></Link>; }
function currentLabel(pathname: string) { const match = [...primary,...field,...output].find(({ href }) => href === '/app' ? pathname === href : pathname.startsWith(href)); if (pathname.includes('/audit')) return 'Audit trail'; if (pathname.includes('/settings')) return 'Settings'; return match?.label || 'Workspace'; }
