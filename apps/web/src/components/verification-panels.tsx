'use client';

import { Camera, FileCheck2, FileSearch, Layers3, ShieldCheck } from 'lucide-react';
import { useState } from 'react';

const steps=[
  {index:'01',icon:FileSearch,title:'Resolve the record',detail:'Identify the current model, drawing, RFI, submittal, and revision before comparing anything.',action:'SOURCE GRAPH READY'},
  {index:'02',icon:Camera,title:'Anchor the field',detail:'Keep photo, video, voice, location, orientation, and measurement in one evidence object.',action:'LOCATION CONFIRMED'},
  {index:'03',icon:Layers3,title:'Explain the difference',detail:'Separate approved change, deviation, existing-condition conflict, and incomplete work.',action:'CAUSE CLASSIFIED'},
  {index:'04',icon:ShieldCheck,title:'Check the proof',detail:'State the limitation and request the missing view, dimension, approval, or source.',action:'SUFFICIENCY SCORED'},
  {index:'05',icon:FileCheck2,title:'Route the action',detail:'Prepare the appropriate RFI, punch, change event, or model update for human review.',action:'DRAFT FOR REVIEW'}
];

export function VerificationPanels(){const[active,setActive]=useState<number|null>(null);return <div className="verification-panels" onKeyDown={event=>{if(event.key==='Escape')setActive(null)}}>
  <img className="verification-panel-backdrop" src="/brand/verification-flow-backdrop-v2.webp" alt="Completed atrium organized into five spatial bays"/>
  <svg className="verification-coordinate-layer" viewBox="0 0 1500 620" aria-hidden><g><path d="M70 80h420v185H70zM520 80h350v185H520zM900 80h520v185H900zM70 295h280v245H70zM380 295h490v245H380zM900 295h520v245H900z"/><path d="M140 80v185m185-185v185M650 80v185m560-185v185M70 405h280m225-110v245m185-245v245m140-115h520"/><circle cx="870" cy="295" r="9"/><circle cx="380" cy="405" r="9"/></g><text x="92" y="110">FIELD / 02</text><text x="542" y="110">SOURCE / 01</text><text x="922" y="110">CLASSIFY / 03</text><text x="92" y="325">PROOF / 04</text><text x="402" y="325">REVIEW / 05</text></svg>
  <div className="verification-panel-row" onMouseLeave={()=>setActive(null)} onBlur={event=>{if(!event.currentTarget.contains(event.relatedTarget as Node|null))setActive(null)}}>{steps.map((step,index)=>{const Icon=step.icon;const selected=index===active;return <button key={step.index} type="button" className={selected?'active':''} aria-expanded={selected} onMouseEnter={()=>setActive(index)} onFocus={()=>setActive(index)} onClick={()=>setActive(current=>current===index?null:index)}><span>{step.index}</span><Icon/><div><h3>{step.title}</h3><p>{step.detail}</p><strong>{step.action}</strong></div><i/></button>})}</div>
</div>}
