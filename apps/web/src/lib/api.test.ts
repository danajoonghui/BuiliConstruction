import { afterEach, describe, expect, it, vi } from 'vitest';
import { clearCsrfToken, csrfHeaders, primeCsrfToken, withDemoFallback } from './api';

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
});
