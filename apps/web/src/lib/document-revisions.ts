import type { DocumentRevision } from './types';

export type RevisionCreationResult={revision_id:string;job_id:string|null;revision:{revision:string;status:string;sheet_number:string|null;issue_date:string|null}};

function revisionStatus(value:string):DocumentRevision['status']{const normalized=value.toLowerCase();if(normalized==='current'||normalized==='approved')return'Current';if(normalized==='review_required')return'Review required';if(normalized==='processing'||normalized==='uploaded')return'Processing';return'Superseded'}

export function uploadedRevisionRow(result:RevisionCreationResult,fileName:string):DocumentRevision{return{id:result.revision_id,sheet:result.revision.sheet_number||'--',title:fileName,discipline:'General',revision:result.revision.revision,status:result.job_id?'Processing':revisionStatus(result.revision.status),issuedAt:new Date(result.revision.issue_date||Date.now()).toLocaleDateString(),linkedIssues:0}}
