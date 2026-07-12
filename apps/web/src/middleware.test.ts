import { describe, expect, it } from 'vitest';
import { NextRequest } from 'next/server';
import { middleware } from './middleware';

describe('public origin middleware', () => {
  it('forces HTTPS on the product subdomain', () => {
    const response = middleware(new NextRequest('http://app.builiconstruction.com/app?demo=1'));
    expect(response.status).toBe(308);
    expect(response.headers.get('location')).toBe(
      'https://app.builiconstruction.com/app?demo=1',
    );
  });

  it('canonicalizes www to the HTTPS apex', () => {
    const response = middleware(new NextRequest('https://www.builiconstruction.com/platform'));
    expect(response.status).toBe(308);
    expect(response.headers.get('location')).toBe(
      'https://builiconstruction.com/platform',
    );
  });

  it('does not rewrite local development', () => {
    const response = middleware(new NextRequest('http://localhost:3000/app'));
    expect(response.status).toBe(200);
    expect(response.headers.get('location')).toBeNull();
  });
});

