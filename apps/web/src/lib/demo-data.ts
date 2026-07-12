import type { DocumentRevision, Issue, Project } from './types';

export const demoUser = { name: 'Jordan Cho', initials: 'JC', role: 'Project Manager', company: 'Northstar Builders' };

export const projects: Project[] = [
  { id: 'pioneer', name: 'Pioneer Office Renovation', code: 'NSB-2407', location: 'San Jose, CA', phase: 'Construction', progress: 64, openIssues: 18, evidenceCoverage: 87, updatedAt: '8 min ago' },
  { id: 'cooper', name: 'Cooper Residence Renovation', code: 'CR-2026-017', location: 'Santa Clara, CA', phase: 'Electrical rough-in', progress: 38, openIssues: 7, evidenceCoverage: 92, updatedAt: '24 min ago' },
  { id: 'vertex', name: 'Vertex Lab Fit-out', code: 'NSB-2414', location: 'Palo Alto, CA', phase: 'Preconstruction', progress: 12, openIssues: 3, evidenceCoverage: 71, updatedAt: 'Yesterday' }
];

export const issues: Issue[] = [
  { id: 'BUI-1042', title: 'Garage GFCI receptacle below required elevation', type: 'Punch', discipline: 'ELEC', location: 'Garage · East wall · Entry door', status: 'Ready for review', priority: 'High', assignee: 'Jordan Cho', updatedAt: '18 min ago' },
  { id: 'BUI-1038', title: 'Partition offset from A-202 layout', type: 'Punch', discipline: 'ARCH', location: 'Level 1 · West corridor', status: 'Open', priority: 'Medium', assignee: 'Daniel Ruiz', updatedAt: '1 hr ago' },
  { id: 'BUI-1033', title: 'HVAC route differs from approved RFI', type: 'Model update', discipline: 'MECH', location: 'Level 2 · Room 204', status: 'Evidence required', priority: 'High', assignee: 'Jordan Cho', updatedAt: 'Yesterday' },
  { id: 'BUI-1027', title: 'Ceiling tile damage after MEP work', type: 'Punch', discipline: 'ARCH', location: 'Level 2 · Open office', status: 'Open', priority: 'Low', assignee: 'Leo Park', updatedAt: 'Yesterday' },
  { id: 'BUI-1019', title: 'Existing plumbing conflicts with new footing', type: 'Change event', discipline: 'MECH', location: 'Level B1 · Grid D-7', status: 'Issued', priority: 'Critical', assignee: 'Jordan Cho', updatedAt: '2 days ago' }
];

export const revisions: DocumentRevision[] = [
  { id: 'e11-r3', sheet: 'E-1.1', title: 'Power & signal plan', discipline: 'Electrical', revision: '03', status: 'Current', issuedAt: 'Jul 8, 2026', linkedIssues: 4 },
  { id: 'a202-r5', sheet: 'A-202', title: 'Level 2 floor plan', discipline: 'Architectural', revision: '05', status: 'Current', issuedAt: 'Jul 7, 2026', linkedIssues: 6 },
  { id: 'm202-r3', sheet: 'M-202', title: 'Level 2 mechanical plan', discipline: 'Mechanical', revision: '03', status: 'Current', issuedAt: 'Jul 5, 2026', linkedIssues: 3 },
  { id: 'fp202-r2', sheet: 'FP-202', title: 'Level 2 sprinkler plan', discipline: 'Fire protection', revision: '02', status: 'Review required', issuedAt: 'Jul 11, 2026', linkedIssues: 2 },
  { id: 'a202-r4', sheet: 'A-202', title: 'Level 2 floor plan', discipline: 'Architectural', revision: '04', status: 'Superseded', issuedAt: 'Jun 18, 2026', linkedIssues: 1 }
];

export const demoIssue = {
  id: 'BUI-1042', title: 'Garage GFCI receptacle below required elevation', project: 'Cooper Residence Renovation', location: 'Garage · East wall · Entry door',
  observed: 'The centerline of the installed GFCI receptacle box is approximately 12 in. above finished floor.',
  expected: 'E1.1 Electrical Note 3 requires garage receptacles to be mounted at a minimum of 18 in. above finished floor.',
  difference: 'Installed box centerline appears 6 in. below the documented minimum. Stud bay remains open, so correction can occur before wall close-in.',
  classification: 'Confirmed field deviation', confidence: 94,
  source: { sheet: 'E1.1', revision: '03', detail: 'Electrical Note 3', excerpt: 'Garage receptacles: mount at 18 in. AFF minimum unless noted otherwise.' },
  transcript: 'Jordan, this is Mike at the Cooper Residence, garage east wall near the entry door. We checked the GFCI box shown on E 1.1. Its centerline is at twelve inches above the floor, but electrical note three calls for a minimum of eighteen inches in garages. I left the stud bay open and tagged the location. Please confirm whether Delta Electrical should raise the box before close-in. I uploaded the context, detail, and tape measurement photos with this note.',
  measurement: { observed: '12 in. AFF', required: '18 in. AFF min.', delta: '−6 in.' }
};
