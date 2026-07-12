import { describe, expect, it } from 'vitest';
import { directUploadOptions, isApiUploadUrl } from './uploads';

describe('direct upload security', () => {
  it('recognizes backend upload URLs and keeps session credentials', () => {
    const url='http://localhost:8000/v1/uploads/up_123/content';
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
});
