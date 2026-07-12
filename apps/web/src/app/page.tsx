import Link from 'next/link';
import type { Metadata } from 'next';
import { ArrowRight, ArrowUpRight, Check, CheckCircle2, FileCheck2, FileQuestion, FileSearch, Layers3, MapPin, Mic2, ScanLine, ShieldCheck, Sparkles } from 'lucide-react';
import { MarketingHeader } from '@/components/marketing-header';
import { Brand } from '@/components/brand';
import { PlanFieldCompare } from '@/components/plan-field-compare';
import { VerificationPanels } from '@/components/verification-panels';
import { MarketingReveal } from '@/components/marketing-reveal';

const evidenceObjects=[
  {image:'/demo/garage-east-wall-context.png',label:'CONTEXT',title:'Exact room and orientation',meta:'Garage / East wall'},
  {image:'/demo/receptacle-rough-in-detail.png',label:'DETAIL',title:'Visible installed condition',meta:'GFCI rough-in'},
  {image:'/demo/box-elevation-measurement.png',label:'MEASUREMENT',title:'Dimension that can be checked',meta:'12 in. AFF'}
];
const appOrigin=(process.env.NEXT_PUBLIC_APP_URL||'').replace(/\/$/,'');
const appHref=(path:string)=>`${appOrigin}${path}`;

export const metadata: Metadata = {
  alternates: { canonical: 'https://builiconstruction.com/' },
};

export default function HomePage(){return <main className="marketing-page buili-marketing">
  <MarketingReveal/>
  <MarketingHeader/>

  <section className="alignment-hero">
    <img src="/brand/hero-renovation-v2.webp" alt="Renovation site transitioning from project record to active field condition"/>
    <div className="alignment-hero__veil"/>
    <div className="alignment-scan" aria-hidden><i/><span>ALIGNING FIELD + RECORD</span></div>
    <div className="section-shell alignment-hero__content"><p>CONSTRUCTION VERIFICATION INTELLIGENCE</p><h1>The field changed.<br/><em>Now prove why.</em></h1><span>BUILI turns a site observation into a location-grounded, source-cited, review-ready construction action.</span><div><Link className="buili-primary-cta" href={appHref('/signup')}>REQUEST ACCESS <ArrowRight/></Link><Link className="buili-secondary-cta" href={appHref('/app/issues/BUI-1042?demo=1')}>LIVE PRODUCT DEMO <ArrowUpRight/></Link></div></div>
    <div className="hero-verification-tag"><span>BUI-1042</span><b>Field condition located</b><small>Current requirement linked / ready for review</small><CheckCircle2/></div>
  </section>

  <section className="field-record-transition" id="verification-layer" data-reveal>
    <svg className="field-record-blueprint" viewBox="0 0 1600 650" aria-hidden><g className="field-record-blueprint__plan"><path d="M70 84h362v154H70zM462 84h310v154H462zM802 84h726v154H802zM70 268h256v292H70zM356 268h416v292H356zM802 268h334v292H802zM1166 268h362v292h-362z"/><path d="M183 84v154m135-154v154M578 84v154m118-154v154m228 0V84m204 0v154M70 396h256m128-128v292m166-292v292m182-146h334m172-146v292"/><path d="M326 341h30m416-124v30m364 167h30M758 554h30"/><circle cx="356" cy="396" r="8"/><circle cx="802" cy="268" r="8"/><circle cx="1166" cy="414" r="8"/></g><g className="field-record-blueprint__axis"><path d="M36 596h1528M36 572v48m382-33v18m382-18v18m382-18v18m382-33v48"/><text x="52" y="585">0.000</text><text x="424" y="585">12.500</text><text x="806" y="585">25.000</text><text x="1188" y="585">37.500</text><text x="1470" y="585">50.000 M</text></g></svg>
    <div className="section-shell field-record-transition__inner"><header><p>BUILI / VERIFICATION LAYER</p><h2>When field and record diverge.</h2><span>Align the observation. Resolve the source. Route the right action.</span></header><div className="field-record-path"><article><ScanLine/><b>FIELD</b><small>Observed condition</small><span>PHOTO + VOICE + MEASURE</span></article><i/><article><FileSearch/><b>RECORD</b><small>Controlling requirement</small><span>MODEL + E1.1 REV 03</span></article><i/><article><FileCheck2/><b>ACTION</b><small>Human-reviewed output</small><span>PUNCH / RFI / CHANGE</span></article></div></div>
  </section>

  <section className="alignment-section" id="platform" data-reveal><div className="section-shell alignment-section__header"><div><p>01 / SPATIAL ALIGNMENT</p><h2>See the field and the record in the same place.</h2></div><p>Use the current BIM when it is reliable. Complement it when it is incomplete. Generate a lightweight spatial reference from the latest 2D set when it is missing.</p></div><div className="section-shell"><PlanFieldCompare/></div></section>

  <section className="revision-story" id="source-truth" data-reveal>
    <div className="revision-story__image"><img src="/brand/revision-table-v2.webp" alt="Construction team resolving drawing revisions and source documents"/><div className="revision-scanline"/></div>
    <div className="revision-story__content"><p>02 / SOURCE OF TRUTH</p><h2>Resolve the revision before judging the work.</h2><span>A condition can differ from the model and still match an approved RFI. BUILI follows the decision chain before it classifies the issue.</span><div className="revision-graph"><article><FileSearch/><div><b>E1.1 / REV 03</b><small>CURRENT DRAWING</small></div><strong>NOW</strong></article><i/><article><FileQuestion/><div><b>RFI-014 RESPONSE</b><small>APPROVED CHANGE</small></div><strong>LINKED</strong></article><i/><article><Layers3/><div><b>MODEL VERSION 07</b><small>UPDATE PENDING</small></div><strong>STALE</strong></article></div></div>
  </section>

  <section className="proof-story" id="evidence-proof" data-reveal>
    <img src="/brand/issue-review-v2.webp" alt="Construction team reviewing a field issue and its evidence"/>
    <div className="proof-story__overlay"/>
    <div className="section-shell proof-story__content"><div><p>03 / EVIDENCE SUFFICIENCY</p><h2>Know what proof is missing before close-in.</h2><span>BUILI checks location, context, detail, measurement, current sources, and installation state before recommending an action.</span></div><div className="proof-checks"><article><Check/><span><b>Exact location</b><small>Room + object + direction</small></span></article><article><Check/><span><b>Context and detail</b><small>Wide + close views</small></span></article><article><Check/><span><b>Measured condition</b><small>12 in. AFF</small></span></article><article><Sparkles/><span><b>Current requirement</b><small>E1.1 Rev 03 verified</small></span></article><strong>96<small>/100</small><em>SUFFICIENT TO ACT</em></strong></div></div>
  </section>

  <section className="verification-system" id="workflow" data-reveal><div className="section-shell"><header><p>04 / VERIFICATION SYSTEM</p><h2>One traceable path from observation to action.</h2></header><VerificationPanels/></div></section>

  <section className="action-story" id="action-routing" data-reveal>
    <div className="action-story__report"><img src="/demo/BUI-1042-report-preview.png" alt="BUILI source-cited issue package preview"/><span>SOURCE-CITED OUTPUT / VERSION 03</span></div>
    <div className="action-story__content"><p>05 / COMMERCIAL ACTION</p><h2>Not every observation should become an RFI.</h2><span>BUILI distinguishes a clear field correction from a design question, change event, progress record, or model update&mdash;and preserves why.</span><div className="action-routes"><article className="active"><CheckCircle2/><div><b>FIELD CORRECTION / PUNCH</b><small>Recommended / requirement is clear</small></div><strong>SELECTED</strong></article><article><FileQuestion/><div><b>CLARIFICATION RFI</b><small>Optional / if requirement is disputed</small></div></article><article><Layers3/><div><b>MODEL UPDATE</b><small>When approved field work is not reflected</small></div></article></div><Link href={appHref('/app/issues/BUI-1042?demo=1')}>OPEN THE COMPLETE ISSUE <ArrowRight/></Link></div>
  </section>

  <section className="evidence-objects" id="use-cases" data-reveal><header className="section-shell"><p>THE EVIDENCE OBJECT</p><h2>Original files remain intact. Context becomes useful.</h2></header><div className="evidence-object-strip">{evidenceObjects.map(item=><Link href={appHref('/app/issues/BUI-1042?demo=1')} key={item.label} className="evidence-object"><img src={item.image} alt={item.title}/><div><span>{item.label}</span><h3>{item.title}</h3><p><MapPin/> {item.meta}</p></div></Link>)}<Link href={appHref('/app/issues/BUI-1042?demo=1')} className="evidence-object evidence-object--voice"><Mic2/><div><span>VOICE NOTE</span><h3>The field explanation, captured hands-free.</h3><p>Mike Alvarez / Foreman / 00:32</p></div><i className="voice-wave">{Array.from({length:36}).map((_,index)=><b key={index} style={{height:`${12+(index*11)%42}px`}}/>)}</i></Link></div></section>

  <section className="buili-closing" data-reveal><img src="/brand/verified-handover-v2.webp" alt="Construction team completing a verified project handover"/><div className="closing-grid" aria-hidden><span/><span/><span/><span/></div><div className="section-shell"><p>START WITH ONE REAL ISSUE</p><h2>Bring the discrepancy.<br/><em>Leave with the proof.</em></h2><span>Use a recent field change, unresolved RFI, or model mismatch to see BUILI on the work your team already does.</span><div><Link className="buili-primary-cta" href={appHref('/signup')}>REQUEST A VALIDATION SESSION <ArrowRight/></Link><Link href="mailto:hello@builiconstruction.com">CONTACT BUILI</Link></div></div></section>

  <footer className="buili-footer"><div className="section-shell buili-footer__top"><Brand/><p>Construction verification,<br/>grounded in evidence.</p><nav><div><b>PRODUCT</b><Link href="#platform">Spatial alignment</Link><Link href="#workflow">Verification system</Link><Link href={appHref('/app/issues/BUI-1042?demo=1')}>Live demo</Link></div><div><b>ACCESS</b><Link href={appHref('/signup')}>Request access</Link><Link href={appHref('/login')}>Sign in</Link><Link href="mailto:hello@builiconstruction.com">Contact</Link></div></nav></div><div id="security-note" className="section-shell buili-footer__trust"><ShieldCheck/><span>Project-scoped access / source version history / human approval before formal export</span></div><div className="section-shell buili-footer__bottom"><span>&copy; 2026 BUILI Construction.</span><span>builiconstruction.com</span></div></footer>
</main>}
