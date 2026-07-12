import { describe, expect, it } from 'vitest';
import { API_URL } from './api';
import { directUploadOptions, isApiUploadUrl, uploadIsReady } from './uploads';

describe('direct upload security', () => {
  it('recognizes backend upload URLs and keeps session credentials', () => {
    const url=`${API_URL}/uploads/up_123/content`;
    expect(isApiUploadUrl(url)).toBe(true);
    const request=directUploadOptions({upload_id:'up_123',upload_url:url},new File(['x'],'proof.jpg',{type:'image/jpeg'}),'abc');
    expect(request.credentials).toBe('include');
    expect(new Headers(request.headers).get('X-Content-SHA256')).toBe('abc');
  });

  it('never sends application cookies or CSRF headers to object storage', () => {
    const url='https://uploads.example-s3.com/signed-object';
    expect(isApiUploadUrl(url)).toBe(false);
    const request=directUploadOptions({upload_id:'up_123',upload_url:url,headers:{'x-amz-meta-id':'123'}},new File(['x'],'proof.jpg',{type:'image/jpeg'}),'abc');
    expect(request.credentials).toBe('omit');
    expect(new Headers(request.headers).get('X-CSRF-Token')).toBeNull();
    expect(new Headers(request.headers).get('x-amz-meta-id')).toBe('123');
  });

  it('does not expose an upload before its security scan is clean', () => {
    expect(uploadIsReady({id:'up_1',status:'quarantined',scan_status:'pending',original_filename:'plan.pdf',content_type:'application/pdf'})).toBe(false);
    expect(uploadIsReady({id:'up_1',status:'complete',scan_status:'clean',original_filename:'plan.pdf',content_type:'application/pdf'})).toBe(true);
  });
});
