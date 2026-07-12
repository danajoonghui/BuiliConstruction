'use client';

import { Check, FileText, Image as ImageIcon, Mic2 } from 'lucide-react';
import { useEffect, useRef } from 'react';

export function HeroVisual() {
  const visual = useRef<HTMLDivElement>(null);
  useEffect(() => {
    const node = visual.current;
    if (!node || matchMedia('(prefers-reduced-motion: reduce)').matches) return;
    const onMove = (event: PointerEvent) => {
      const rect = node.getBoundingClientRect();
      const x = (event.clientX - rect.left) / rect.width - .5;
      const y = (event.clientY - rect.top) / rect.height - .5;
      node.style.setProperty('--mx', `${x * 10}px`);
      node.style.setProperty('--my', `${y * 8}px`);
    };
    node.addEventListener('pointermove', onMove);
    return () => node.removeEventListener('pointermove', onMove);
  }, []);

  return (
    <div className="hero-visual" ref={visual} aria-label="BUILI spatial verification workspace preview">
      <div className="hero-grid" aria-hidden />
      <svg className="hero-plan" viewBox="0 0 760 470" role="img" aria-label="Building plan connected to field evidence">
        <g className="plan-lines">
          <path d="M85 80h210v112H85zM310 80h148v112H310zM474 80h198v112H474zM85 208h151v174H85zM251 208h207v91H251zM251 315h207v67H251zM474 208h198v174H474z" />
          <path d="M118 80v20m75-20v20m117 43h20m128 104h16m104-39v20M208 382v-20m119 20v-20" />
        </g>
        <g className="plan-labels">
          <text x="102" y="106">OPEN OFFICE 201</text><text x="326" y="106">MEETING 202</text><text x="491" y="106">FIELD LAB</text>
          <text x="102" y="235">CORRIDOR</text><text x="268" y="235">ROOM 204</text><text x="491" y="235">ELECTRICAL 205</text>
        </g>
        <g className="plan-route"><path d="M127 166h261v98h147" /><circle cx="127" cy="166" r="4" /><circle cx="535" cy="264" r="5" /></g>
        <g className="plan-pin" transform="translate(535 264)"><circle r="17"/><circle r="5"/></g>
      </svg>

      <div className="hero-floating hero-floating--issue">
        <span className="hero-float-eyebrow">BUI-1042 · ELEC</span>
        <strong>Installation differs from current requirement</strong>
        <span className="hero-float-meta"><i /> Ready for review</span>
      </div>
      <div className="hero-floating hero-floating--evidence">
        <span className="hero-float-eyebrow">Evidence set</span>
        <div className="hero-evidence-icons"><span><ImageIcon size={15}/></span><span><Mic2 size={15}/></span><span><FileText size={15}/></span><b>4 linked</b></div>
      </div>
      <div className="hero-floating hero-floating--verified"><Check size={15}/><span><strong>Source verified</strong><small>E-1.1 · Rev 03 · Note 3</small></span></div>
    </div>
  );
}
