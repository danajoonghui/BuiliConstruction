import type { ApiResult } from './types';

export const API_URL = (process.env.NEXT_PUBLIC_API_URL || 'http://localhost:8000/v1').replace(/\/$/, '');

export class ApiError extends Error {
  constructor(public status: number, message: string, public code = 'API_ERROR') { super(message); }
}

let csrfToken = '';
let csrfRequest: Promise<string> | null = null;

export function csrfHeaders(): Record<string,string> {
  return csrfToken ? { 'X-CSRF-Token': csrfToken } : {};
}

function rememberCsrfToken(payload:unknown) {
  if (!payload || typeof payload !== 'object') return;
  const token = (payload as { csrf_token?:unknown }).csrf_token;
  if (typeof token === 'string' && token) csrfToken = token;
}

export async function primeCsrfToken():Promise<string> {
  if (csrfToken) return csrfToken;
  if (typeof window === 'undefined') return '';
  if (!csrfRequest) csrfRequest = fetch(`${API_URL}/auth/csrf`, { credentials:'include', headers:{Accept:'application/json'} }).then(async response=>{
    const payload:unknown=await response.json().catch(()=>({}));
    if (!response.ok) {
      const failure=payload as {error?:{message?:string;code?:string}};
      throw new ApiError(response.status,failure.error?.message||'Could not initialize the secure session.',failure.error?.code);
    }
    const data=payload&&typeof payload==='object'&&'data' in payload?(payload as ApiResult<{csrf_token:string}>).data:payload;
    rememberCsrfToken(data);
    if (!csrfToken) throw new ApiError(500,'The API did not return a CSRF token.','CSRF_TOKEN_MISSING');
    return csrfToken;
  }).finally(()=>{csrfRequest=null});
  return csrfRequest;
}

export function clearCsrfToken(){csrfToken='';csrfRequest=null}

function csrfExempt(path:string){return ['/auth/login','/auth/signup','/auth/oidc/exchange','/auth/forgot-password'].includes(path)}

async function secureHeaders(path:string,method:string,headers:Headers){
  if (['GET','HEAD','OPTIONS'].includes(method)||typeof window==='undefined'||csrfExempt(path)) return;
  if (!csrfToken) await primeCsrfToken();
  Object.entries(csrfHeaders()).forEach(([key,value])=>headers.set(key,value));
}

async function request<T>(path: string, options: RequestInit = {}): Promise<T> {
  const method = (options.method || 'GET').toUpperCase();
  const headers = new Headers({ 'Content-Type': 'application/json', ...options.headers });
  await secureHeaders(path,method,headers);
  const response = await fetch(`${API_URL}${path}`, {
    ...options,
    credentials: 'include',
    headers
  });
  const payload: unknown = await response.json().catch(() => ({}));
  if (!response.ok) {
    const failure = payload as { error?: { message?: string; code?: string } };
    throw new ApiError(response.status, failure.error?.message || 'Request failed', failure.error?.code);
  }
  const data=payload && typeof payload === 'object' && 'data' in payload ? (payload as ApiResult<T>).data : payload as T;
  rememberCsrfToken(data);
  return data;
}

export const api = {
  get: <T>(path: string, options?: RequestInit) => request<T>(path, { ...options, method: 'GET' }),
  post: <T>(path: string, body?: unknown, options?: RequestInit) => request<T>(path, { ...options, method: 'POST', body: body === undefined ? undefined : JSON.stringify(body) }),
  patch: <T>(path: string, body: unknown, options?: RequestInit) => request<T>(path, { ...options, method: 'PATCH', body: JSON.stringify(body) }),
  delete: <T>(path: string, options?: RequestInit) => request<T>(path, { ...options, method: 'DELETE' })
};

export const authApi = {
  signIn: (input: { email: string; password: string }) => api.post<{ user: unknown; csrf_token:string }>('/auth/login', input),
  signUp: (input: { display_name: string; email: string; password: string; organization_name?: string }) => api.post<{ user: unknown; csrf_token:string }>('/auth/signup', input),
  forgotPassword: (email: string) => api.post('/auth/forgot-password', { email }),
  exchangeGoogle: (idToken: string, organizationName?: string) => api.post<{ user: unknown; csrf_token:string }>('/auth/oidc/exchange', { id_token: idToken, organization_name: organizationName })
};

export async function withDemoFallback<T>(load: () => Promise<T>, fallback: T, options: { demo?: boolean } = {}): Promise<{ data: T; demo: boolean }> {
  try { return { data: await load(), demo: false }; }
  catch (error) {
    const explicitDemo = options.demo === true || process.env.NEXT_PUBLIC_DEMO_MODE === 'true';
    if (explicitDemo) return { data: fallback, demo: true };
    throw error;
  }
}
