export type ApiResult<T> = { data: T; request_id?: string; meta?: Record<string, unknown> };

export type Project = {
  id: string;
  name: string;
  code: string;
  location: string;
  phase: string;
  progress: number;
  openIssues: number;
  evidenceCoverage: number;
  updatedAt: string;
};

export type Issue = {
  id: string;
  title: string;
  type: 'RFI candidate' | 'Punch' | 'Change event' | 'Model update';
  discipline: 'ARCH' | 'MECH' | 'ELEC' | 'FP';
  location: string;
  status: 'Evidence required' | 'Ready for review' | 'Open' | 'Issued' | 'Closed';
  priority: 'Critical' | 'High' | 'Medium' | 'Low';
  assignee: string;
  updatedAt: string;
};

export type DocumentRevision = {
  id: string;
  sheet: string;
  title: string;
  discipline: string;
  revision: string;
  status: 'Current' | 'Superseded' | 'Review required' | 'Processing';
  issuedAt: string;
  linkedIssues: number;
};
