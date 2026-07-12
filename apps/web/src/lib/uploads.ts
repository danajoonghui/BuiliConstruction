import { API_URL, api, csrfHeaders } from './api';

type UploadInit = { upload_id: string; upload_url?: string; method?: string; headers?: Record<string,string>; object_key?: string };
type UploadComplete = { id: string; status: string; scan_status?:string; scan_result_json?:Record<string,unknown>; original_filename:string; content_type:string };

async function checksum(file: File) {
  const hash = await crypto.subtle.digest('SHA-256', await file.arrayBuffer());
  return [...new Uint8Array(hash)].map(value => value.toString(16).padStart(2,'0')).join('');
}

export function isApiUploadUrl(uploadUrl:string) {
  try {
    const apiBase = new URL(`${API_URL}/`);
    const target = new URL(uploadUrl, apiBase);
    const basePath = apiBase.pathname.replace(/\/$/, '');
    return target.origin === apiBase.origin && target.pathname.startsWith(`${basePath}/uploads/`);
  } catch { return false; }
}

export function directUploadOptions(initiated:UploadInit, file:File, digest:string):RequestInit {
  const internal = Boolean(initiated.upload_url && isApiUploadUrl(initiated.upload_url));
  return {
    method: initiated.method || 'PUT',
    credentials: internal ? 'include' : 'omit',
    headers: internal
      ? { ...initiated.headers, 'Content-Type':file.type || 'application/octet-stream', 'X-Content-SHA256':digest, ...csrfHeaders() }
      : initiated.headers,
    body:file
  };
}

export function uploadIsReady(upload:UploadComplete){return upload.status==='complete'&&upload.scan_status==='clean'}

async function waitForCleanUpload(uploadId:string,initial:UploadComplete,onProgress?: (progress:number)=>void){let upload=initial;for(let attempt=0;attempt<90;attempt++){if(uploadIsReady(upload))return upload;if(upload.status==='rejected'||['infected','error'].includes(upload.scan_status||'')){const detail=typeof upload.scan_result_json?.message==='string'?upload.scan_result_json.message:'The upload failed its security scan.';throw new Error(detail)}onProgress?.(Math.min(99,90+Math.floor(attempt/10)));await new Promise(resolve=>setTimeout(resolve,1000));upload=await api.get<UploadComplete>(`/uploads/${uploadId}`)}throw new Error('The file security scan is taking longer than expected. The upload is retained; try again after the scan completes.')}

export async function uploadProjectFile(organizationId:string, projectId: string, file: File, onProgress?: (progress:number)=>void): Promise<UploadComplete> {
  const digest = await checksum(file); onProgress?.(8);
  const initiated = await api.post<UploadInit>('/uploads/init', { organization_id:organizationId, project_id: projectId, filename: file.name, content_type: file.type || 'application/octet-stream', size: file.size, sha256: digest });
  onProgress?.(18);
  if (initiated.upload_url) {
    const response = await fetch(initiated.upload_url, directUploadOptions(initiated,file,digest));
    if (!response.ok) throw new Error('Direct upload failed');
  } else {
    const response = await fetch(`${API_URL}/uploads/${initiated.upload_id}/content`, { method: 'PUT', credentials: 'include', headers: { 'Content-Type': file.type || 'application/octet-stream', 'X-Content-SHA256': digest, ...csrfHeaders() }, body: file });
    if (!response.ok) throw new Error('Upload failed');
  }
  onProgress?.(88);
  const completed = await api.post<UploadComplete>(`/uploads/${initiated.upload_id}/complete`, { sha256: digest });
  const clean=await waitForCleanUpload(initiated.upload_id,completed,onProgress);
  onProgress?.(100); return clean;
}
