'use client';

import Link from 'next/link';
import { ArrowUpRight, Menu, X } from 'lucide-react';
import { useState } from 'react';
import { Brand } from './brand';

const links=[{href:'#platform',label:'PLATFORM'},{href:'#use-cases',label:'WHAT WE VERIFY'},{href:'#workflow',label:'PIPELINE'},{href:'#security-note',label:'SECURITY'}];
const appOrigin=(process.env.NEXT_PUBLIC_APP_URL||'').replace(/\/$/,'');
const appHref=(path:string)=>`${appOrigin}${path}`;

export function MarketingHeader(){const[open,setOpen]=useState(false);return <header className="marketing-header corporate-marketing-header"><div className="marketing-header__inner"><Brand/><nav className="marketing-nav" aria-label="Main navigation">{links.map(item=><Link key={item.href} href={item.href}>{item.label}</Link>)}</nav><div className="marketing-actions"><Link href={appHref('/login')}>SIGN IN</Link><Link href={appHref('/signup')} className="corporate-header-cta">REQUEST ACCESS <ArrowUpRight/></Link></div><button className="mobile-menu-button" onClick={()=>setOpen(!open)} aria-expanded={open} aria-label="Toggle navigation">{open?<X/>:<Menu/>}</button></div>{open&&<nav className="mobile-marketing-nav">{links.map(item=><Link key={item.href} href={item.href} onClick={()=>setOpen(false)}>{item.label}</Link>)}<Link href={appHref('/login')}>SIGN IN</Link><Link href={appHref('/signup')} className="corporate-header-cta">REQUEST ACCESS</Link></nav>}</header>}
