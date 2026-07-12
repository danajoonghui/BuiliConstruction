import { afterEach, describe, expect, it, vi } from 'vitest';
import { api, clearCsrfToken, csrfHeaders, primeCsrfToken, withDemoFallback } from './api';

afterEach(()=>{clearCsrfToken();vi.unstubAllGlobals()});

describe('withDemoFallback', () => {
  it('does not hide production API failures behind demo data', async () => {
    await expect(
      withDemoFallback(async () => { throw new Error('offline'); }, { value: 'demo' })
    ).rejects.toThrow('offline');
  });

  it('returns demo data only when demo mode is explicit', async () => {
    await expect(
      withDemoFallback(async () => { throw new Error('offline'); }, { value: 'demo' }, { demo: true })
    ).resolves.toEqual({ data: { value: 'demo' }, demo: true });
  });

  it('loads the host-only API CSRF token into session memory',async()=>{
    vi.stubGlobal('fetch',vi.fn().mockResolvedValue(new Response(JSON.stringify({data:{csrf_token:'csrf_test_123'}}),{status:200,headers:{'Content-Type':'application/json'}})));
    await expect(primeCsrfToken()).resolves.toBe('csrf_test_123');
    expect(csrfHeaders()).toEqual({'X-CSRF-Token':'csrf_test_123'});
  });

  it('protects cookie refresh with a CSRF token', async () => {
    const fetchMock=vi.fn()
      .mockResolvedValueOnce(new Response(JSON.stringify({data:{csrf_token:'csrf_refresh_123'}}),{status:200,headers:{'Content-Type':'application/json'}}))
      .mockResolvedValueOnce(new Response(JSON.stringify({data:{user:{id:'user-1'},csrf_token:'csrf_rotated'}}),{status:200,headers:{'Content-Type':'application/json'}}));
    vi.stubGlobal('fetch',fetchMock);

    await api.post('/auth/refresh',{});

    expect(fetchMock).toHaveBeenCalledTimes(2);
    expect(fetchMock.mock.calls[0][0]).toContain('/auth/csrf');
    const refreshHeaders=new Headers(fetchMock.mock.calls[1][1]?.headers);
    expect(refreshHeaders.get('X-CSRF-Token')).toBe('csrf_refresh_123');
    expect(fetchMock.mock.calls[1][1]?.credentials).toBe('include');
  });
});
