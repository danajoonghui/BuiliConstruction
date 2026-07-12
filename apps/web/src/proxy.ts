import { NextResponse } from 'next/server';
import type { NextRequest } from 'next/server';

const CANONICAL_MARKETING_HOST = 'builiconstruction.com';
const PUBLIC_HOSTS = new Set([
  CANONICAL_MARKETING_HOST,
  `www.${CANONICAL_MARKETING_HOST}`,
  `app.${CANONICAL_MARKETING_HOST}`,
]);

export function proxy(request: NextRequest) {
  const rawHost = (
    request.headers.get('x-forwarded-host') ??
    request.headers.get('host') ??
    request.nextUrl.host
  ).toLowerCase();
  const host = rawHost.split(':')[0];
  const forwardedProtocol = request.headers.get('x-forwarded-proto')?.toLowerCase();
  const insecure = request.nextUrl.protocol === 'http:' || forwardedProtocol === 'http';
  const duplicateMarketingHost = host === `www.${CANONICAL_MARKETING_HOST}`;

  if ((PUBLIC_HOSTS.has(host) && insecure) || duplicateMarketingHost) {
    const destination = request.nextUrl.clone();
    destination.protocol = 'https:';
    destination.host = duplicateMarketingHost ? CANONICAL_MARKETING_HOST : rawHost;
    return NextResponse.redirect(destination, 308);
  }

  return NextResponse.next();
}

export const config = {
  matcher: ['/((?!_next/static|_next/image|favicon.png).*)'],
};
