'use client';

import { FileCheck2, MapPin } from 'lucide-react';
import { useState } from 'react';

export function PlanFieldCompare(){const[split,setSplit]=useState(52);return <div className="plan-field-compare" style={{'--compare-split':`${split}%`} as React.CSSProperties}>
  <div className="compare-plan"><img src="/demo/E1.1-preview.png" alt="Current electrical drawing E1.1, revision 03"/><span>PROJECT RECORD / E1.1 REV 03</span></div>
  <div className="compare-field"><img src="/brand/capture-clearance-v2.webp" alt="Field team capturing a clearance measurement"/><span>FIELD / GARAGE EAST WALL</span></div>
  <div className="compare-divider"><i/><b>DRAG TO ALIGN</b></div>
  <input aria-label="Compare project record with field condition" type="range" min="24" max="76" value={split} onChange={event=>setSplit(Number(event.target.value))}/>
  <div className="compare-location"><MapPin/><span><b>Same location</b><small>Garage / East wall / Entry door</small></span></div>
  <div className="compare-source"><FileCheck2/><span><b>Current source found</b><small>E1.1 / Rev 03 / Note 3</small></span></div>
</div>}
